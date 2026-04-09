"""
test_search_user_tags.py — Search 頁 user_tags 資料流整合測試 (41b-T3)

DoD 要求的 2 個測試：
- test_search_user_tags_persist：加 tag → API response 含 tag → GET 確認 DB 持久化
- test_search_user_tags_no_file_path：無 file_path 的 POST → success=false
"""

import sqlite3
import pytest
from fastapi.testclient import TestClient
from core.database import init_db


TEST_FILE_URI = "file:///C:/AVtest/SONE-205.mp4"
NONEXISTENT_URI = "file:///C:/AVtest/NONEXISTENT.mp4"


@pytest.fixture
def tmp_db(tmp_path):
    """建立臨時測試資料庫，插入一筆測試影片"""
    db_path = tmp_path / "test_search_user_tags.db"
    init_db(db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        INSERT INTO videos (path, number, title, actresses, maker, tags, user_tags, duration, size_bytes)
        VALUES (?, 'SONE-205', 'Test Movie', '["明日花キララ"]', 'Sony', '["巨乳"]', '[]', 7200, 4000000000)
    """, (TEST_FILE_URI,))
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def client(tmp_db, monkeypatch):
    """TestClient，monkeypatch get_db_path 指向 tmp DB"""
    monkeypatch.setattr("web.routers.collection.get_db_path", lambda: tmp_db)
    from web.app import app
    return TestClient(app)


class TestSearchUserTagsPersist:
    """
    test_search_user_tags_persist:
    加 tag → API response 含 tag → GET 確認 DB 持久化
    """

    def test_add_tag_response_contains_tag(self, client):
        """POST 新增 tag → response success=True 且 user_tags 含該 tag"""
        resp = client.post("/api/user-tags", json={
            "file_path": TEST_FILE_URI,
            "add": ["★5"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "★5" in data["user_tags"]

    def test_add_tag_db_persisted(self, tmp_db, monkeypatch):
        """POST 新增 tag → GET 確認 DB 已持久化"""
        monkeypatch.setattr("web.routers.collection.get_db_path", lambda: tmp_db)
        from web.app import app
        test_client = TestClient(app)

        # 加 tag
        post_resp = test_client.post("/api/user-tags", json={
            "file_path": TEST_FILE_URI,
            "add": ["持久化標籤"],
        })
        assert post_resp.json()["success"] is True

        # 重新 GET 確認 DB 持久化
        get_resp = test_client.get("/api/user-tags", params={"file_path": TEST_FILE_URI})
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert "持久化標籤" in get_data["user_tags"]

    def test_add_then_remove_tag_persisted(self, tmp_db, monkeypatch):
        """POST add tag → POST remove tag → GET 確認移除已持久化"""
        monkeypatch.setattr("web.routers.collection.get_db_path", lambda: tmp_db)
        from web.app import app
        test_client = TestClient(app)

        # 先加
        test_client.post("/api/user-tags", json={
            "file_path": TEST_FILE_URI,
            "add": ["暫時標籤"],
        })

        # 再刪
        remove_resp = test_client.post("/api/user-tags", json={
            "file_path": TEST_FILE_URI,
            "remove": ["暫時標籤"],
        })
        assert remove_resp.json()["success"] is True
        assert "暫時標籤" not in remove_resp.json()["user_tags"]

        # GET 確認
        get_resp = test_client.get("/api/user-tags", params={"file_path": TEST_FILE_URI})
        assert "暫時標籤" not in get_resp.json()["user_tags"]


class TestSearchUserTagsNoFilePath:
    """
    test_search_user_tags_no_file_path:
    無 file_path 或 file_path 不存在於 DB → success=false
    """

    def test_post_without_file_path_returns_422(self, client):
        """POST 完全省略 file_path → Pydantic 422（必填欄位缺失）"""
        resp = client.post("/api/user-tags", json={
            "add": ["★5"],
        })
        assert resp.status_code == 422

    def test_post_nonexistent_file_path_returns_success_false(self, client):
        """POST file_path 不在 DB → success=False"""
        resp = client.post("/api/user-tags", json={
            "file_path": NONEXISTENT_URI,
            "add": ["★5"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "error" in data

    def test_post_empty_file_path_returns_422_or_false(self, client):
        """POST file_path 為空字串 → 422 或 success=False（視 validator 行為）"""
        resp = client.post("/api/user-tags", json={
            "file_path": "",
            "add": ["★5"],
        })
        # 可接受 422（Pydantic min_length validation）或 200 success=False
        assert resp.status_code in (200, 422)
        if resp.status_code == 200:
            assert resp.json()["success"] is False

    def test_get_nonexistent_file_path_returns_empty_tags(self, client):
        """GET 不存在的 file_path → user_tags=[]（不 crash）"""
        resp = client.get("/api/user-tags", params={"file_path": NONEXISTENT_URI})
        assert resp.status_code == 200
        assert resp.json()["user_tags"] == []
