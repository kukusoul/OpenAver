"""
tests/integration/test_notifications_api.py — 通知中心 API 端點測試（53b）

用 FastAPI TestClient 打 GET / POST / DELETE。依 CLAUDE.md 測試分層：API 端點 → integration/。
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def reset_buffer():
    import web.routers.notifications as notif_mod
    notif_mod._notifications.clear()
    notif_mod._read_ids.clear()
    yield
    notif_mod._notifications.clear()
    notif_mod._read_ids.clear()


@pytest.fixture
def client():
    from web.app import app
    return TestClient(app)


def test_get_empty(client):
    """無 emit 時 GET 回空 buffer + 0 unread + null highest。"""
    res = client.get("/api/notifications")
    body = res.json()
    assert body["items"] == []
    assert body["unread_count"] == 0
    assert body["highest_unread_level"] is None


def test_get_with_items(client):
    """emit 2 筆後 GET 回最新在前 + 全部未讀。"""
    from web.routers.notifications import emit_notification
    emit_notification("info", "notif.scanner_started")
    emit_notification("warn", "notif.scanner_done_with_errors")
    body = client.get("/api/notifications").json()
    assert len(body["items"]) == 2
    assert body["items"][0]["title_key"] == "notif.scanner_done_with_errors"
    assert body["unread_count"] == 2
    assert body["highest_unread_level"] == "warn"


def test_post_read_marks_all(client):
    """POST /read 後 GET 顯示全部已讀。"""
    from web.routers.notifications import emit_notification
    emit_notification("info", "notif.scanner_started")
    emit_notification("warn", "notif.batch_enrich_done_with_errors")

    res = client.post("/api/notifications/read")
    assert res.json() == {"ok": True, "marked_count": 2}

    body = client.get("/api/notifications").json()
    assert body["unread_count"] == 0
    assert all(item["is_read"] is True for item in body["items"])


def test_delete_clears_all(client):
    """DELETE 後 buffer 跟 _read_ids 都清空。"""
    from web.routers.notifications import emit_notification, _read_ids
    emit_notification("info", "notif.scanner_started")
    client.post("/api/notifications/read")
    assert len(_read_ids) > 0

    res = client.delete("/api/notifications")
    assert res.json()["ok"] is True
    assert res.json()["cleared_count"] >= 1

    body = client.get("/api/notifications").json()
    assert body["items"] == []
    assert len(_read_ids) == 0


def test_highest_unread_level_priority(client):
    """info + error 未讀 → highest = error；標已讀後新 warn → highest = warn。"""
    from web.routers.notifications import emit_notification
    emit_notification("info", "notif.scanner_started")
    emit_notification("error", "notif.scanner_failed")
    assert client.get("/api/notifications").json()["highest_unread_level"] == "error"

    client.post("/api/notifications/read")
    emit_notification("warn", "notif.scanner_done_with_errors")
    assert client.get("/api/notifications").json()["highest_unread_level"] == "warn"


def test_scanner_no_directory_emits_no_started(client):
    """scanner_started 在無 directories 時不應 emit（P2-2 regression guard）。

    沒有 scannerRouter 可以直接呼叫 scanner_generate，用 mock config 驗證 emit 邏輯：
    當 directories 為空時，emit_notification 不應被呼叫（不殘留 scanner_started）。
    """
    import unittest.mock as mock
    from web.routers.notifications import _notifications

    # 模擬 directories 為空的 config
    empty_config = {"gallery": {"directories": [], "output_dir": "output", "output_filename": "gallery_output.html", "path_mappings": {}, "min_size_mb": 0, "default_mode": "image", "default_sort": "date", "default_order": "descending", "items_per_page": 90}, "general": {"theme": "light"}}

    with mock.patch("web.routers.scanner.load_config", return_value=empty_config):
        from web.routers.scanner import generate_avlist
        # 消費完 generator（否則 yield 不執行）
        events = list(generate_avlist())

    # 驗證：沒有 scanner_started 通知（early return path 不應 emit started）
    notif_keys = [n["title_key"] for n in _notifications]
    assert "notif.scanner_started" not in notif_keys, f"scanner_started 不應在 no-directory 路徑出現，但找到：{notif_keys}"
    # 驗證：SSE stream 包含 error 事件
    assert any("error" in e for e in events), "no-directory 路徑應產生 SSE error 事件"
