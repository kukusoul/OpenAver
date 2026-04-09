"""
test_user_tags_api.py — POST/GET /api/user-tags 端點整合測試

使用 FastAPI TestClient + 真實 SQLite DB（tmp_path）。
TDD-lite：先從邊界條件 E1–E9 提取 RED 測試 → 實作 GREEN。
"""

import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from core.database import init_db


# ── Fixtures ──────────────────────────────────────────────────────────────────

TEST_FILE_URI = "file:///test/SONE-205.mp4"
TEST_FILE_URI2 = "file:///test/ABW-001.mp4"
NONEXISTENT_URI = "file:///test/NONEXISTENT.mp4"


@pytest.fixture
def tmp_db(tmp_path):
    """建立臨時測試資料庫，插入少量測試資料"""
    db_path = tmp_path / "test_user_tags.db"
    init_db(db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    # 插入測試影片（含 user_tags）
    conn.execute("""
        INSERT INTO videos (path, number, title, actresses, maker, tags, user_tags, duration, size_bytes)
        VALUES
        (?, 'SONE-205', 'Test Title 1', '["明日花キララ"]', 'Sony', '["巨乳","中出"]', '["★4"]', 7200, 4000000000),
        (?, 'ABW-001', 'Test Title 2', '["葵つかさ"]', 'ABC', '["女教師"]', '[]', 6000, 3500000000)
    """, (TEST_FILE_URI, TEST_FILE_URI2))

    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def client(tmp_db, monkeypatch):
    """TestClient，monkeypatch get_db_path 指向 tmp DB"""
    monkeypatch.setattr("web.routers.collection.get_db_path", lambda: tmp_db)

    from web.app import app
    return TestClient(app)


# ── E1: file_path 不在 DB ─────────────────────────────────────────────────────

class TestE1FilePathNotInDB:
    """E1: file_path 不在 DB → success=false, error 存在"""

    def test_post_nonexistent_returns_success_false(self, client):
        """POST 不存在的 file_path → success=False，包含 error"""
        resp = client.post("/api/user-tags", json={
            "file_path": NONEXISTENT_URI,
            "add": ["★5"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "error" in data
        assert data["error"]

    def test_post_nonexistent_no_crash(self, client):
        """POST 不存在的 file_path → 不 crash（HTTP 200）"""
        resp = client.post("/api/user-tags", json={
            "file_path": NONEXISTENT_URI,
        })
        assert resp.status_code == 200


# ── E2: add 包含已存在的 tag（idempotent）─────────────────────────────────────

class TestE2AddExistingTag:
    """E2: add 包含已存在的 tag → 去重，不重複加入"""

    def test_add_existing_tag_no_duplicate(self, client):
        """add 包含已存在的 '★4' → 最終 user_tags 只有一個 '★4'"""
        resp = client.post("/api/user-tags", json={
            "file_path": TEST_FILE_URI,
            "add": ["★4"],  # 已存在
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        tags = data["user_tags"]
        assert tags.count("★4") == 1

    def test_add_existing_tag_idempotent(self, client):
        """多次 add 同一 tag → 結果相同，不累積"""
        # 第一次
        resp1 = client.post("/api/user-tags", json={
            "file_path": TEST_FILE_URI,
            "add": ["新標"],
        })
        tags1 = resp1.json()["user_tags"]

        # 第二次（重複 add）
        resp2 = client.post("/api/user-tags", json={
            "file_path": TEST_FILE_URI,
            "add": ["新標"],
        })
        tags2 = resp2.json()["user_tags"]

        assert tags1.count("新標") == 1
        assert tags2.count("新標") == 1
        assert tags1 == tags2


# ── E3: remove 包含不存在的 tag（靜默忽略）───────────────────────────────────

class TestE3RemoveNonexistentTag:
    """E3: remove 包含不存在的 tag → 靜默忽略，不報錯"""

    def test_remove_nonexistent_tag_no_error(self, client):
        """remove 不存在的 tag → success=True，不報錯"""
        resp = client.post("/api/user-tags", json={
            "file_path": TEST_FILE_URI,
            "remove": ["不存在的標籤"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_remove_nonexistent_tag_original_tags_intact(self, client):
        """remove 不存在的 tag → 原有 tags 不受影響"""
        resp = client.post("/api/user-tags", json={
            "file_path": TEST_FILE_URI,
            "remove": ["不存在的標籤"],
        })
        data = resp.json()
        assert "★4" in data["user_tags"]  # 原有 ★4 仍保留


# ── E4: add 和 remove 同時含相同 tag（remove 優先）───────────────────────────

class TestE4AddRemoveConflict:
    """E4: add 和 remove 同時包含相同 tag → remove 優先"""

    def test_remove_wins_over_add(self, client):
        """add=['足'] 且 remove=['足'] → 最終不含 '足'"""
        resp = client.post("/api/user-tags", json={
            "file_path": TEST_FILE_URI,
            "add": ["足"],
            "remove": ["足"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "足" not in data["user_tags"]


# ── E5: add=[], remove=[]（純查詢式 POST）────────────────────────────────────

class TestE5EmptyAddRemove:
    """E5: add=[], remove=[] → DB 更新、NFO 重寫仍執行（user_tags 不變）"""

    def test_empty_add_remove_success(self, client):
        """add=[], remove=[] → success=True，user_tags 不變"""
        resp = client.post("/api/user-tags", json={
            "file_path": TEST_FILE_URI,
            "add": [],
            "remove": [],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["user_tags"] == ["★4"]  # 不變

    def test_empty_request_returns_nfo_updated_field(self, client):
        """add=[], remove=[] → 回應含 nfo_updated 欄位"""
        resp = client.post("/api/user-tags", json={
            "file_path": TEST_FILE_URI,
        })
        data = resp.json()
        assert "nfo_updated" in data


# ── E6: NFO 寫入失敗 ──────────────────────────────────────────────────────────

class TestE6NfoWriteFailure:
    """E6: NFO 寫入失敗 → success=True, nfo_updated=False（DB 已更新）"""

    def test_nfo_write_fail_exception(self, client, monkeypatch):
        """mock generate_nfo 拋出 OSError → success=True, nfo_updated=False"""
        with patch("web.routers.collection.generate_nfo", side_effect=OSError("Permission denied")):
            resp = client.post("/api/user-tags", json={
                "file_path": TEST_FILE_URI,
                "add": ["★5"],
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["nfo_updated"] is False

    def test_nfo_write_fail_returns_false(self, client, monkeypatch):
        """mock generate_nfo 回傳 False（靜默失敗）→ success=True, nfo_updated=False"""
        with patch("web.routers.collection.generate_nfo", return_value=False):
            resp = client.post("/api/user-tags", json={
                "file_path": TEST_FILE_URI,
                "add": ["★5"],
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["nfo_updated"] is False

    def test_nfo_write_fail_db_still_updated(self, tmp_db, monkeypatch):
        """mock generate_nfo 拋出 OSError → DB 仍然更新"""
        monkeypatch.setattr("web.routers.collection.get_db_path", lambda: tmp_db)

        with patch("web.routers.collection.generate_nfo", side_effect=OSError("Permission denied")):
            from web.app import app
            test_client = TestClient(app)
            resp = test_client.post("/api/user-tags", json={
                "file_path": TEST_FILE_URI,
                "add": ["★5"],
            })

        assert resp.json()["success"] is True

        # 確認 DB 已更新
        from core.database import VideoRepository
        repo = VideoRepository(tmp_db)
        video = repo.get_by_path(TEST_FILE_URI)
        assert "★5" in video.user_tags


# ── E7: add 含重複 tag ─────────────────────────────────────────────────────────

class TestE7AddDuplicatesInRequest:
    """E7: add 含重複 tag（["★5", "★5"]）→ 去重，結果只有一個 "★5"""""

    def test_add_duplicate_tags_in_request(self, client):
        """add=['★5', '★5'] → 結果只有一個 '★5'"""
        resp = client.post("/api/user-tags", json={
            "file_path": TEST_FILE_URI2,  # ABW-001，初始 user_tags=[]
            "add": ["★5", "★5"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["user_tags"].count("★5") == 1


# ── E8: user_tags 為空，remove 含任意 tag ────────────────────────────────────

class TestE8EmptyTagsRemove:
    """E8: user_tags 為空 list，remove 含任意 tag → 回傳空 list，不報錯"""

    def test_empty_tags_remove_returns_empty(self, client):
        """ABW-001 user_tags=[], remove=['任意'] → [] 不報錯"""
        resp = client.post("/api/user-tags", json={
            "file_path": TEST_FILE_URI2,  # 初始 user_tags=[]
            "remove": ["任意標籤"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["user_tags"] == []


# ── E9: GET 查詢不存在的 file_path ────────────────────────────────────────────

class TestE9GetNonexistent:
    """E9: GET 查詢不存在的 file_path → 200 + {user_tags: [], file_path: ...}"""

    def test_get_nonexistent_returns_empty_list(self, client):
        """GET 不存在的 file_path → 200，user_tags=[]"""
        resp = client.get("/api/user-tags", params={"file_path": NONEXISTENT_URI})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_tags"] == []
        assert data["file_path"] == NONEXISTENT_URI

    def test_get_nonexistent_no_crash(self, client):
        """GET 不存在的 file_path → 不 crash"""
        resp = client.get("/api/user-tags", params={"file_path": NONEXISTENT_URI})
        assert resp.status_code == 200


# ── Happy Path ────────────────────────────────────────────────────────────────

class TestHappyPath:
    """Happy path：正常操作流程"""

    def test_post_add_new_tag(self, client):
        """add 新 tag → success=True，tag 在 user_tags"""
        resp = client.post("/api/user-tags", json={
            "file_path": TEST_FILE_URI2,
            "add": ["★5"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "★5" in data["user_tags"]
        assert "nfo_updated" in data

    def test_post_remove_existing_tag(self, client):
        """remove 已存在的 tag → tag 不在 user_tags"""
        resp = client.post("/api/user-tags", json={
            "file_path": TEST_FILE_URI,
            "remove": ["★4"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "★4" not in data["user_tags"]

    def test_post_response_structure(self, client):
        """POST 回應含 success, user_tags, nfo_updated"""
        resp = client.post("/api/user-tags", json={
            "file_path": TEST_FILE_URI,
        })
        data = resp.json()
        assert "success" in data
        assert "user_tags" in data
        assert "nfo_updated" in data

    def test_get_existing_file_path(self, client):
        """GET 已存在的 file_path → 回傳現有 user_tags"""
        resp = client.get("/api/user-tags", params={"file_path": TEST_FILE_URI})
        assert resp.status_code == 200
        data = resp.json()
        assert data["file_path"] == TEST_FILE_URI
        assert "★4" in data["user_tags"]

    def test_get_response_structure(self, client):
        """GET 回應含 user_tags, file_path"""
        resp = client.get("/api/user-tags", params={"file_path": TEST_FILE_URI})
        data = resp.json()
        assert "user_tags" in data
        assert "file_path" in data

    def test_post_add_and_remove_combined(self, client):
        """同時 add 新 tag 和 remove 舊 tag"""
        # 先確認初始狀態（★4 存在）
        resp = client.post("/api/user-tags", json={
            "file_path": TEST_FILE_URI,
            "add": ["足"],
            "remove": ["★4"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "足" in data["user_tags"]
        assert "★4" not in data["user_tags"]

    def test_post_db_persists(self, tmp_db, monkeypatch):
        """POST 後再 GET → DB 已持久化"""
        monkeypatch.setattr("web.routers.collection.get_db_path", lambda: tmp_db)

        from web.app import app
        test_client = TestClient(app)

        # POST 添加 tag
        test_client.post("/api/user-tags", json={
            "file_path": TEST_FILE_URI2,
            "add": ["持久化測試"],
        })

        # GET 查詢
        resp = test_client.get("/api/user-tags", params={"file_path": TEST_FILE_URI2})
        data = resp.json()
        assert "持久化測試" in data["user_tags"]

    def test_post_missing_file_path_returns_422(self, client):
        """file_path 缺失 → Pydantic 422"""
        resp = client.post("/api/user-tags", json={
            "add": ["★5"],
        })
        assert resp.status_code == 422

    def test_get_missing_file_path_returns_422(self, client):
        """GET 缺少 file_path → 422"""
        resp = client.get("/api/user-tags")
        assert resp.status_code == 422
