"""
tests/unit/test_clip_disable.py
TDD-lite RED tests for VideoRepository.clear_all_clip_embeddings (56d T1a).
Codex-56D-P2: SQL OR clause 確保孤兒 row（只有 clip_model_id，無 embedding）也被清除。
"""
import sqlite3
from pathlib import Path

import pytest


def _make_db_with_clips(db_path: Path) -> None:
    """建立測試用 DB，插入帶 clip_embedding 的影片資料。

    包含三類 row：
    - v1, v2: clip_embedding + clip_model_id 都有值（正常已索引）
    - v3: 兩欄皆 NULL（純淨 row）
    - v4: 只有 clip_model_id，clip_embedding=NULL（OR clause 應抓到的孤兒 row）
    """
    from core.database import init_db

    init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        # 插入兩筆有 clip embedding 的影片
        conn.execute(
            "INSERT INTO videos (path, number, clip_embedding, clip_model_id) "
            "VALUES (?, ?, ?, ?)",
            ("/v1.mp4", "TEST-001", b"\x00\x01\x02", "clip-vit-b32-int8-xenova-v1"),
        )
        conn.execute(
            "INSERT INTO videos (path, number, clip_embedding, clip_model_id) "
            "VALUES (?, ?, ?, ?)",
            ("/v2.mp4", "TEST-002", b"\x03\x04\x05", "clip-vit-b32-int8-xenova-v1"),
        )
        # 插入一筆沒有 clip embedding 的影片
        conn.execute(
            "INSERT INTO videos (path, number) VALUES (?, ?)",
            ("/v3.mp4", "TEST-003"),
        )
        # 孤兒 row：只有 clip_model_id，clip_embedding=NULL（Codex-56D-P2 OR clause 測試）
        conn.execute(
            "INSERT INTO videos (path, number, clip_embedding, clip_model_id) "
            "VALUES (?, ?, ?, ?)",
            ("/v4.mp4", "TEST-004", None, "clip-vit-b32-int8-xenova-v1"),
        )
        conn.commit()
    finally:
        conn.close()


class TestClearAllClipEmbeddings:
    def test_returns_correct_rowcount(self, tmp_path):
        """clear_all_clip_embeddings() 回傳被清除的列數（OR clause：含孤兒 row 共 3 筆）"""
        from core.database import VideoRepository

        db_path = tmp_path / "test.db"
        _make_db_with_clips(db_path)

        repo = VideoRepository(db_path)
        count = repo.clear_all_clip_embeddings()

        # v1, v2 有 embedding；v4 只有 model_id（孤兒 row）→ OR clause 抓到 3 筆
        assert count == 3

    def test_clears_embedding_and_model_id_columns(self, tmp_path):
        """clear_all_clip_embeddings() 後所有影片的 clip_embedding 和 clip_model_id 為 NULL"""
        from core.database import VideoRepository

        db_path = tmp_path / "test.db"
        _make_db_with_clips(db_path)

        repo = VideoRepository(db_path)
        repo.clear_all_clip_embeddings()

        # 確認所有影片的 clip 欄位都為 NULL
        conn = sqlite3.connect(str(db_path))
        try:
            rows = conn.execute(
                "SELECT clip_embedding, clip_model_id FROM videos"
            ).fetchall()
        finally:
            conn.close()

        for row in rows:
            assert row[0] is None, "clip_embedding 應為 NULL"
            assert row[1] is None, "clip_model_id 應為 NULL"

    def test_orphan_row_with_model_id_only_is_cleared(self, tmp_path):
        """Codex-56D-P2: 只有 clip_model_id 設值、clip_embedding=NULL 的孤兒 row 也被 OR clause 抓到清除"""
        from core.database import VideoRepository

        db_path = tmp_path / "test.db"

        # 建立最簡單的場景：一筆孤兒 row + 一筆純淨 row
        from core.database import init_db
        init_db(db_path)
        conn = sqlite3.connect(str(db_path))
        try:
            # 孤兒 row：只有 model_id，無 embedding
            conn.execute(
                "INSERT INTO videos (path, number, clip_embedding, clip_model_id) "
                "VALUES (?, ?, ?, ?)",
                ("/orphan.mp4", "ORPHAN-001", None, "clip-vit-b32-int8-xenova-v1"),
            )
            # 純淨 row：兩欄皆 NULL
            conn.execute(
                "INSERT INTO videos (path, number) VALUES (?, ?)",
                ("/clean.mp4", "CLEAN-001"),
            )
            conn.commit()
        finally:
            conn.close()

        repo = VideoRepository(db_path)
        count = repo.clear_all_clip_embeddings()

        # OR clause 應抓到孤兒 row（rowcount=1），不抓純淨 row
        assert count == 1, f"OR clause 應清除 1 筆孤兒 row，但 rowcount={count}"
