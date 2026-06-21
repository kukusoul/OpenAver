from unittest.mock import MagicMock
from pathlib import Path

import pytest

from windows.tray import (
    CLOSE_ASK,
    CLOSE_CANCEL,
    CLOSE_EXIT,
    CLOSE_TRAY,
    CMD_CLOSE_ASK,
    CMD_CLOSE_EXIT,
    CMD_CLOSE_TRAY,
    CMD_CONFIRM,
    CMD_OPEN,
    CMD_QUIT,
    IDCANCEL,
    NIF_SHOWTIP,
    TRAY_OPEN_EVENTS,
    CloseDecision,
    DesktopLifecycle,
    _OpenEventDebouncer,
    _map_dialog_result,
    load_desktop_texts,
)


@pytest.fixture
def desktop():
    window = MagicMock()
    jl_window = MagicMock()
    tray = MagicMock()
    saved = []
    state = {
        "width": 1200,
        "height": 800,
        "x": None,
        "y": None,
        "maximized": False,
        "close_action": CLOSE_ASK,
    }
    lifecycle = DesktopLifecycle(window, jl_window, state, lambda value: saved.append(dict(value)))
    lifecycle.attach_tray(tray)
    tray.start.return_value = True
    lifecycle.start_tray()
    return lifecycle, window, jl_window, tray, saved


def test_prompt_tray_remember_hides_and_cancels_close(desktop):
    lifecycle, window, jl_window, tray, saved = desktop
    lifecycle.prompt = lambda: CloseDecision(CLOSE_TRAY, remember=True)

    assert lifecycle.on_window_closing() is False
    window.hide.assert_called_once_with()
    jl_window.destroy.assert_not_called()
    tray.stop.assert_not_called()
    assert lifecycle.get_close_action() == CLOSE_TRAY
    assert saved[-1]["close_action"] == CLOSE_TRAY


def test_prompt_cancel_keeps_window_open(desktop):
    lifecycle, window, jl_window, tray, saved = desktop
    lifecycle.prompt = lambda: CloseDecision(CLOSE_CANCEL, remember=True)

    assert lifecycle.on_window_closing() is False
    window.hide.assert_not_called()
    jl_window.destroy.assert_not_called()
    assert lifecycle.get_close_action() == CLOSE_ASK
    assert saved == []


def test_remembered_tray_skips_prompt(desktop):
    lifecycle, window, _jl_window, _tray, _saved = desktop
    lifecycle.state["close_action"] = CLOSE_TRAY
    lifecycle.prompt = MagicMock(side_effect=AssertionError("prompt must not run"))

    assert lifecycle.on_window_closing() is False
    window.hide.assert_called_once_with()
    lifecycle.prompt.assert_not_called()


def test_remembered_exit_stops_tray_and_allows_close(desktop):
    lifecycle, _window, jl_window, tray, saved = desktop
    lifecycle.state["close_action"] = CLOSE_EXIT

    assert lifecycle.on_window_closing() is None
    assert lifecycle.quitting is True
    tray.stop.assert_called_once_with()
    jl_window.destroy.assert_called_once_with()
    assert saved


def test_tray_commands_open_change_preference_and_quit(desktop):
    lifecycle, window, jl_window, tray, saved = desktop

    lifecycle.handle_tray_command(CMD_OPEN)
    window.show.assert_called_once_with()

    lifecycle.handle_tray_command(CMD_CLOSE_TRAY)
    assert lifecycle.get_close_action() == CLOSE_TRAY
    lifecycle.handle_tray_command(CMD_CLOSE_EXIT)
    assert lifecycle.get_close_action() == CLOSE_EXIT
    lifecycle.handle_tray_command(CMD_CLOSE_ASK)
    assert lifecycle.get_close_action() == CLOSE_ASK
    assert [item["close_action"] for item in saved[:3]] == [CLOSE_TRAY, CLOSE_EXIT, CLOSE_ASK]

    lifecycle.handle_tray_command(CMD_QUIT)
    assert lifecycle.quitting is True
    tray.stop.assert_called_once_with()
    jl_window.destroy.assert_called_once_with()
    window.destroy.assert_called_once_with()


def test_quit_cleanup_is_idempotent(desktop):
    lifecycle, _window, jl_window, tray, _saved = desktop
    lifecycle.handle_tray_command(CMD_QUIT)
    lifecycle.shutdown_after_loop()
    assert tray.stop.call_count == 1
    assert jl_window.destroy.call_count == 1


def test_dialog_result_mapping():
    assert _map_dialog_result(CMD_CONFIRM, CMD_CLOSE_TRAY, True) == CloseDecision(CLOSE_TRAY, True)
    assert _map_dialog_result(CMD_CONFIRM, CMD_CLOSE_EXIT, False) == CloseDecision(CLOSE_EXIT, False)
    assert _map_dialog_result(IDCANCEL, CMD_CLOSE_TRAY, True) == CloseDecision(CLOSE_CANCEL, False)
    assert _map_dialog_result(CMD_CONFIRM, 9999, True) == CloseDecision(CLOSE_CANCEL, False)


@pytest.mark.parametrize("locale", ["zh-TW", "zh-CN", "ja", "en"])
def test_desktop_texts_are_complete_for_every_supported_locale(monkeypatch, locale):
    monkeypatch.setattr("windows.tray.load_config", lambda: {"general": {"locale": locale}})

    texts = load_desktop_texts()

    assert texts.locale == locale
    for name, value in vars(texts).items():
        if name != "locale":
            assert value
            assert not value.startswith("[desktop.")


def test_desktop_texts_follow_runtime_locale_change(monkeypatch):
    current = {"locale": "zh-TW"}
    monkeypatch.setattr(
        "windows.tray.load_config",
        lambda: {"general": {"locale": current["locale"]}},
    )

    assert load_desktop_texts().minimize_to_tray == "最小化到系統匣"
    current["locale"] = "zh-CN"
    assert load_desktop_texts().minimize_to_tray == "最小化到系统托盘"


def test_open_event_debouncer_collapses_single_double_click_burst():
    now = [10.0]
    debouncer = _OpenEventDebouncer(interval=0.5, clock=lambda: now[0])

    assert debouncer.accept() is True
    now[0] += 0.1
    assert debouncer.accept() is False
    now[0] += 0.5
    assert debouncer.accept() is True


def test_tray_contract_supports_hover_single_and_double_click():
    assert NIF_SHOWTIP == 0x0080
    assert {0x0202, 0x0203, 0x0400}.issubset(TRAY_OPEN_EVENTS)


def test_unavailable_tray_never_hides_window(desktop, monkeypatch):
    lifecycle, window, _jl_window, tray, _saved = desktop
    tray.start.return_value = False
    lifecycle.start_tray()
    lifecycle.state["close_action"] = CLOSE_TRAY
    unavailable = MagicMock()
    monkeypatch.setattr("windows.tray.show_tray_unavailable", unavailable)

    assert lifecycle.on_window_closing() is False
    window.hide.assert_not_called()
    unavailable.assert_called_once_with(window)


def test_native_tray_contract_restores_after_explorer_restart():
    source = (Path(__file__).parents[2] / "windows" / "tray.py").read_text(encoding="utf-8")
    assert 'RegisterWindowMessageW("TaskbarCreated")' in source
    assert "if message == wm_taskbar_created" in source
    assert "add_icon()" in source
    assert "NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_SHOWTIP" in source
    assert 'notify_data.szTip = "OpenAver"' in source


def test_task_dialog_common_controls_manifest_is_packaged_with_windows_sources():
    manifest = Path(__file__).parents[2] / "windows" / "common-controls.manifest"
    source = manifest.read_text(encoding="utf-8")
    assert "Microsoft.Windows.Common-Controls" in source
    assert 'version="6.0.0.0"' in source

    tray_source = (manifest.parent / "tray.py").read_text(encoding="utf-8")
    assert tray_source.count("_pack_ = 1") >= 2


def test_standalone_wires_windows_tray_and_shutdown_backstop():
    source = (Path(__file__).parents[2] / "windows" / "standalone.py").read_text(encoding="utf-8")
    assert "if sys.platform == 'win32':" in source
    assert "NativeTrayIcon(" in source
    assert "lifecycle.start_tray()" in source
    assert "lifecycle.shutdown_after_loop()" in source
