"""
tests/unit/test_clip_disable.py
TDD-lite RED tests for VideoRepository.clear_all_clip_embeddings (56d T1a).
"""
import sqlite3
from pathlib import Path

import pytest


def _make_db_with_clips(db_path: Path) -> None:
    """建立測試用 DB，插入帶 clip_embedding 的影片資料。"""
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
        conn.commit()
    finally:
        conn.close()


class TestClearAllClipEmbeddings:
    def test_returns_correct_rowcount(self, tmp_path):
        """clear_all_clip_embeddings() 回傳被清除的列數（只清有 embedding 的）"""
        from core.database import VideoRepository

        db_path = tmp_path / "test.db"
        _make_db_with_clips(db_path)

        repo = VideoRepository(db_path)
        count = repo.clear_all_clip_embeddings()

        assert count == 2  # 只有 2 筆有 clip_embedding

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
