"""
tests/unit/test_notifications.py — 通知 buffer 純函式邏輯測試（53b）

全 mock，不啟動 FastAPI。依 CLAUDE.md 測試分層：純邏輯 → unit/。
"""
import pytest


@pytest.fixture(autouse=True)
def reset_buffer():
    """每個 test 前後清空 buffer，防止狀態污染。"""
    import web.routers.notifications as notif_mod
    notif_mod._notifications.clear()
    notif_mod._read_ids.clear()
    yield
    notif_mod._notifications.clear()
    notif_mod._read_ids.clear()


def test_emit_notification_basic():
    from web.routers.notifications import emit_notification, _notifications
    emit_notification("info", "notif.scanner_started", task_type="scanner_generate")
    assert len(_notifications) == 1
    assert _notifications[0]["level"] == "info"
    assert _notifications[0]["title_key"] == "notif.scanner_started"
    assert _notifications[0]["task_type"] == "scanner_generate"
    assert "id" in _notifications[0]
    assert "timestamp" in _notifications[0]


def test_buffer_max_10():
    from web.routers.notifications import emit_notification, _notifications
    for i in range(11):
        emit_notification("info", f"notif.test_{i}")
    assert len(_notifications) == 10
    assert _notifications[0]["title_key"] == "notif.test_10"
    keys = [n["title_key"] for n in _notifications]
    assert "notif.test_0" not in keys


def test_newest_first():
    from web.routers.notifications import emit_notification, _notifications
    emit_notification("info", "notif.first")
    emit_notification("error", "notif.second")
    assert _notifications[0]["title_key"] == "notif.second"
    assert _notifications[1]["title_key"] == "notif.first"


def test_emit_evicts_orphan_read_id():
    """F2 設計驗證：buffer 滿時 emit 新筆，被擠出筆的 read_id 同步從 _read_ids 清掉。"""
    from web.routers.notifications import emit_notification, _notifications, _read_ids
    for i in range(10):
        emit_notification("info", f"notif.test_{i}")
    oldest_id = _notifications[-1]["id"]
    _read_ids.add(oldest_id)
    emit_notification("info", "notif.test_10")
    assert oldest_id not in _read_ids


def test_calc_highest_unread_level_priority():
    """直接 unit-test helper 函式，不經 API。"""
    from web.routers.notifications import _calc_highest_unread_level
    items = [
        {"id": "a", "level": "info"},
        {"id": "b", "level": "error"},
        {"id": "c", "level": "warn"},
    ]
    assert _calc_highest_unread_level(items, set()) == "error"
    assert _calc_highest_unread_level(items, {"b"}) == "warn"
    assert _calc_highest_unread_level(items, {"a", "b", "c"}) is None
