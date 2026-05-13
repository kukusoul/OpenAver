"""
test_tag_alias_api.py — Tag 別名 API 整合測試

端點：
    GET    /api/tag-aliases                   列出所有別名組
    POST   /api/tag-aliases                   新增別名組
    GET    /api/tag-aliases/{name}            查單一別名組（primary 或 alias 查）
    DELETE /api/tag-aliases/{name}            刪除別名組
    POST   /api/tag-aliases/{name}/alias      為 group 新增 alias
    DELETE /api/tag-aliases/{name}/alias/{a}  移除單一 alias

策略：TestClient + mock TagAliasRepository（monkeypatch）。不使用真實 DB。
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers — 建立測試用 TagAliasRecord-like object
# ---------------------------------------------------------------------------

def _make_record(primary_name, aliases=None, source="manual",
                 created_at=None, updated_at=None):
    """建立符合 TagAliasRecord 介面的 MagicMock"""
    record = MagicMock()
    record.primary_name = primary_name
    record.aliases = aliases or []
    record.source = source
    record.created_at = created_at or datetime(2026, 4, 13)
    record.updated_at = updated_at
    return record


# ---------------------------------------------------------------------------
# Fixture: client with mocked TagAliasRepository
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_repo():
    """回傳一個 MagicMock TagAliasRepository"""
    return MagicMock()


@pytest.fixture
def client(mock_repo, monkeypatch):
    """
    TestClient — monkeypatch TagAliasRepository constructor 回傳 mock_repo。
    """
    monkeypatch.setattr(
        "web.routers.tag_alias.TagAliasRepository",
        lambda *args, **kwargs: mock_repo,
    )
    monkeypatch.setattr(
        "web.routers.tag_alias.init_db",
        lambda *args, **kwargs: None,
    )
    from web.app import app
    return TestClient(app)


# ===========================================================================
# TestTagAliasListAndCreate
# ===========================================================================

class TestTagAliasListAndCreate:
    """GET /api/tag-aliases 及 POST /api/tag-aliases"""

    # --- GET --- list

    def test_list_empty(self, client, mock_repo):
        """空表 → {success: true, groups: [], total: 0}"""
        mock_repo.get_all.return_value = []
        resp = client.get("/api/tag-aliases")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["groups"] == []
        assert data["total"] == 0

    def test_list_returns_all_records(self, client, mock_repo):
        """兩筆資料 → total=2，每筆含 primary_name / aliases / source"""
        records = [
            _make_record("美少女", ["kawaii", "loli"]),
            _make_record("巨乳", ["big-boobs"]),
        ]
        mock_repo.get_all.return_value = records
        resp = client.get("/api/tag-aliases")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["groups"]) == 2
        names = [g["primary_name"] for g in data["groups"]]
        assert "美少女" in names
        assert "巨乳" in names

    # --- POST --- create

    def test_create_success_with_aliases(self, client, mock_repo):
        """成功建立 group → 200 + {success: true, group: {...}}"""
        record = _make_record("美少女", ["kawaii"])
        mock_repo.add.return_value = record
        resp = client.post("/api/tag-aliases", json={
            "primary_name": "美少女",
            "aliases": ["kawaii"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["group"]["primary_name"] == "美少女"

    def test_create_success_without_aliases(self, client, mock_repo):
        """aliases 省略 → 等同空 list，建立只有 primary 的空 group"""
        record = _make_record("美少女", [])
        mock_repo.add.return_value = record
        resp = client.post("/api/tag-aliases", json={"primary_name": "美少女"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_create_empty_primary_name_returns_422(self, client, mock_repo):
        """primary_name 空字串 → 422"""
        resp = client.post("/api/tag-aliases", json={"primary_name": ""})
        assert resp.status_code == 422

    def test_create_conflict_returns_409(self, client, mock_repo):
        """primary_name 已存在 → repo.add raises ValueError → 409（不是 400）"""
        mock_repo.add.side_effect = ValueError("primary_name '美少女' 已被使用")
        resp = client.post("/api/tag-aliases", json={"primary_name": "美少女"})
        assert resp.status_code == 409
        data = resp.json()
        assert data["success"] is False
        assert "error" in data

    def test_create_conflict_fixed_message(self, client, mock_repo):
        """衝突 error 固定中文訊息，不 leak str(exc)"""
        mock_repo.add.side_effect = ValueError("這是 repo 內部訊息")
        resp = client.post("/api/tag-aliases", json={"primary_name": "美少女"})
        assert resp.status_code == 409
        error_msg = resp.json()["error"]
        assert error_msg == "Tag 別名衝突（名字已屬其他組）"
        assert "這是 repo 內部訊息" not in error_msg

    def test_create_internal_error_returns_500(self, client, mock_repo):
        """repo.add raises unexpected Exception → 500 + 固定訊息，不 leak"""
        mock_repo.add.side_effect = RuntimeError("DB connection lost")
        resp = client.post("/api/tag-aliases", json={"primary_name": "美少女"})
        assert resp.status_code == 500
        data = resp.json()
        assert data["success"] is False
        assert data["error"] == "操作失敗"
        assert "DB connection lost" not in str(data)


# ===========================================================================
# TestTagAliasGetByName
# ===========================================================================

class TestTagAliasGetByName:
    """GET /api/tag-aliases/{name}"""

    def test_primary_hit(self, client, mock_repo):
        """name = primary_name → 直接回傳"""
        record = _make_record("美少女", ["kawaii"])
        mock_repo.get_by_primary.return_value = record
        resp = client.get("/api/tag-aliases/美少女")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["group"]["primary_name"] == "美少女"
        assert "kawaii" in data["group"]["aliases"]

    def test_alias_hit(self, client, mock_repo):
        """name = alias → get_by_primary miss → find_by_alias hit"""
        record = _make_record("美少女", ["kawaii"])
        mock_repo.get_by_primary.return_value = None
        mock_repo.find_by_alias.return_value = record
        resp = client.get("/api/tag-aliases/kawaii")
        assert resp.status_code == 200
        data = resp.json()
        assert data["group"]["primary_name"] == "美少女"

    def test_not_found(self, client, mock_repo):
        """primary 和 alias 都查無 → 404"""
        mock_repo.get_by_primary.return_value = None
        mock_repo.find_by_alias.return_value = None
        resp = client.get("/api/tag-aliases/不存在的tag")
        assert resp.status_code == 404
        assert resp.json()["error"] == "not_found"

    def test_created_at_serialized(self, client, mock_repo):
        """created_at datetime → isoformat string"""
        record = _make_record("美少女", [], created_at=datetime(2026, 4, 13, 0, 0, 0))
        mock_repo.get_by_primary.return_value = record
        resp = client.get("/api/tag-aliases/美少女")
        assert resp.status_code == 200
        group = resp.json()["group"]
        assert group["created_at"] == "2026-04-13T00:00:00"

    def test_updated_at_none(self, client, mock_repo):
        """updated_at=None → response 也是 null"""
        record = _make_record("美少女", [], updated_at=None)
        mock_repo.get_by_primary.return_value = record
        resp = client.get("/api/tag-aliases/美少女")
        assert resp.json()["group"]["updated_at"] is None

    def test_internal_error_returns_500(self, client, mock_repo):
        """repo raises Exception → 500 + 固定訊息"""
        mock_repo.get_by_primary.side_effect = RuntimeError("unexpected")
        resp = client.get("/api/tag-aliases/美少女")
        assert resp.status_code == 500
        data = resp.json()
        assert data["error"] == "操作失敗"
        assert "unexpected" not in str(data)


# ===========================================================================
# TestTagAliasDelete
# ===========================================================================

class TestTagAliasDelete:
    """DELETE /api/tag-aliases/{name}"""

    def test_delete_by_primary(self, client, mock_repo):
        """name = primary → repo.delete 回 True → 200"""
        mock_repo.delete.return_value = True
        resp = client.delete("/api/tag-aliases/美少女")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_delete_by_alias(self, client, mock_repo):
        """name = alias → repo.delete 內部 resolve → True → 200"""
        mock_repo.delete.return_value = True
        resp = client.delete("/api/tag-aliases/kawaii")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_delete_not_found(self, client, mock_repo):
        """不存在 → repo.delete 回 False → 404"""
        mock_repo.delete.return_value = False
        resp = client.delete("/api/tag-aliases/不存在")
        assert resp.status_code == 404
        assert "error" in resp.json()

    def test_delete_internal_error_returns_500(self, client, mock_repo):
        """repo raises Exception → 500 + 固定訊息"""
        mock_repo.delete.side_effect = RuntimeError("unexpected")
        resp = client.delete("/api/tag-aliases/美少女")
        assert resp.status_code == 500
        data = resp.json()
        assert data["error"] == "操作失敗"
        assert "unexpected" not in str(data)


# ===========================================================================
# TestTagAliasAddRemoveAlias
# ===========================================================================

class TestTagAliasAddRemoveAlias:
    """POST /api/tag-aliases/{name}/alias 及 DELETE /api/tag-aliases/{name}/alias/{alias}"""

    # --- POST --- add alias

    def test_add_alias_success(self, client, mock_repo):
        """成功新增 → 200 + {success: true, group: {...}}"""
        record = _make_record("美少女", ["kawaii"])
        mock_repo.get_by_primary.side_effect = [
            record,   # 第一次：確認 group 存在
            _make_record("美少女", ["kawaii", "loli"]),  # 第二次：re-read
        ]
        mock_repo.add_alias.return_value = (True, None)
        resp = client.post("/api/tag-aliases/美少女/alias", json={"alias": "loli"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "group" in data

    def test_add_alias_empty_returns_422(self, client, mock_repo):
        """alias 空字串 → 422"""
        resp = client.post("/api/tag-aliases/美少女/alias", json={"alias": ""})
        assert resp.status_code == 422

    def test_add_alias_group_not_found_returns_404(self, client, mock_repo):
        """{name} group 不存在 → 404"""
        mock_repo.get_by_primary.return_value = None
        resp = client.post("/api/tag-aliases/不存在的tag/alias", json={"alias": "loli"})
        assert resp.status_code == 404

    def test_add_alias_conflict_returns_409(self, client, mock_repo):
        """alias 已屬其他 group → add_alias 回 (False, msg) → 409（不是 400）"""
        record = _make_record("美少女", [])
        mock_repo.get_by_primary.return_value = record
        mock_repo.add_alias.return_value = (False, "alias 'loli' 已屬於其他 group")
        resp = client.post("/api/tag-aliases/美少女/alias", json={"alias": "loli"})
        assert resp.status_code == 409
        data = resp.json()
        assert data["success"] is False

    def test_add_alias_conflict_fixed_message(self, client, mock_repo):
        """衝突 error 固定中文訊息，不 leak repo 的 msg"""
        record = _make_record("美少女", [])
        mock_repo.get_by_primary.return_value = record
        internal_msg = "alias 'loli' 已屬於其他 group 這是內部訊息"
        mock_repo.add_alias.return_value = (False, internal_msg)
        resp = client.post("/api/tag-aliases/美少女/alias", json={"alias": "loli"})
        assert resp.status_code == 409
        error_msg = resp.json()["error"]
        assert error_msg == "Tag 別名衝突（名字已屬其他組）"
        assert internal_msg not in error_msg

    def test_add_alias_internal_error_returns_500(self, client, mock_repo):
        """repo raises Exception → 500 + 固定訊息"""
        record = _make_record("美少女", [])
        mock_repo.get_by_primary.side_effect = [record, RuntimeError("unexpected")]
        mock_repo.add_alias.side_effect = RuntimeError("unexpected")
        resp = client.post("/api/tag-aliases/美少女/alias", json={"alias": "loli"})
        assert resp.status_code == 500
        data = resp.json()
        assert data["error"] == "操作失敗"

    # --- DELETE --- remove alias

    def test_remove_alias_success(self, client, mock_repo):
        """成功移除 → 200 + {success: true}"""
        record = _make_record("美少女", ["kawaii"])
        mock_repo.get_by_primary.return_value = record
        mock_repo.remove_alias.return_value = True
        resp = client.delete("/api/tag-aliases/美少女/alias/kawaii")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_remove_alias_group_not_found_returns_404(self, client, mock_repo):
        """{name} primary 不存在 → 404"""
        mock_repo.get_by_primary.return_value = None
        resp = client.delete("/api/tag-aliases/不存在/alias/kawaii")
        assert resp.status_code == 404

    def test_remove_alias_not_found_returns_404(self, client, mock_repo):
        """alias 不在 group → remove_alias 回 False → 404 error=alias_not_found"""
        record = _make_record("美少女", [])
        mock_repo.get_by_primary.return_value = record
        mock_repo.remove_alias.return_value = False
        resp = client.delete("/api/tag-aliases/美少女/alias/不存在的alias")
        assert resp.status_code == 404
        assert resp.json()["error"] == "alias_not_found"

    def test_remove_alias_internal_error_returns_500(self, client, mock_repo):
        """repo raises Exception → 500 + 固定訊息"""
        mock_repo.get_by_primary.side_effect = RuntimeError("unexpected")
        resp = client.delete("/api/tag-aliases/美少女/alias/kawaii")
        assert resp.status_code == 500
        data = resp.json()
        assert data["error"] == "操作失敗"


# ===========================================================================
# TestTagAliasErrorMasking — CD-58-14：驗證 error response 不含 str(exc) leak
# ===========================================================================

class TestTagAliasErrorMasking:
    """CD-58-14：所有端點 error 訊息不 leak 內部 exception 訊息"""

    def test_create_409_does_not_leak_exc_message(self, client, mock_repo):
        """
        POST /api/tag-aliases：repo.add raises ValueError("這是 repo 內部訊息")
        → response["error"] 固定中文，不包含 repo 訊息
        """
        internal_msg = "這是 repo 內部訊息"
        mock_repo.add.side_effect = ValueError(internal_msg)
        resp = client.post("/api/tag-aliases", json={"primary_name": "美少女"})
        assert resp.status_code == 409
        error_val = resp.json()["error"]
        assert error_val == "Tag 別名衝突（名字已屬其他組）"
        assert internal_msg not in error_val
        assert "repo" not in error_val.lower()

    def test_add_alias_409_does_not_leak_repo_msg(self, client, mock_repo):
        """
        POST /api/tag-aliases/{name}/alias：add_alias 回 (False, internal_msg)
        → response["error"] 固定中文，不包含 repo 的內部 msg
        """
        internal_msg = "這是 repo 內部訊息，不應回給前端"
        record = _make_record("美少女", [])
        mock_repo.get_by_primary.return_value = record
        mock_repo.add_alias.return_value = (False, internal_msg)
        resp = client.post("/api/tag-aliases/美少女/alias", json={"alias": "loli"})
        assert resp.status_code == 409
        error_val = resp.json()["error"]
        assert error_val == "Tag 別名衝突（名字已屬其他組）"
        assert internal_msg not in error_val

    def test_500_does_not_leak_exception_message(self, client, mock_repo):
        """
        各端點 except Exception → 500 response["error"] == "操作失敗"，不含 Python exception 訊息
        """
        internal_msg = "internal DB error XYZ-secret"
        mock_repo.get_all.side_effect = RuntimeError(internal_msg)
        resp = client.get("/api/tag-aliases")
        assert resp.status_code == 500
        data = resp.json()
        assert data["error"] == "操作失敗"
        assert internal_msg not in str(data)
        assert "XYZ-secret" not in str(data)
