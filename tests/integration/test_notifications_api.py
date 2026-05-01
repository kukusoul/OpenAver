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
