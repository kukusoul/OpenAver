"""
TDD-lite 測試 — help_page() context 注入 lan_ip + port
Phase 38b T3b
"""
import socket
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


def _make_client():
    from web.app import app
    return TestClient(app, raise_server_exceptions=True)


class TestHelpPageContext:
    """help_page() 必須注入 lan_ip 和 port 到 template context"""

    def test_help_page_context_has_lan_ip(self):
        """context 含 lan_ip 字串"""
        client = _make_client()
        response = client.get("/help")
        assert response.status_code == 200
        # lan_ip 注入後應出現在 HTML 中（SSR 渲染到 Terminal box）
        # 驗證 HTML 中有 IP 格式字串出現在 curl 指令附近
        html = response.text
        # 檢查 curl 指令存在（表示 lan_ip 被渲染）
        assert "curl -s http://" in html, \
            "help.html 應含有 SSR 渲染的 curl 指令（lan_ip 未注入）"

    def test_help_page_context_has_port(self):
        """context 含 port 整數（渲染到 curl 指令中）"""
        client = _make_client()
        response = client.get("/help")
        assert response.status_code == 200
        html = response.text
        # port 應出現在 curl 指令中
        assert "/api/capabilities" in html, \
            "help.html 應含有 /api/capabilities 端點（port 未注入或 template 未渲染）"

    def test_help_page_context_lan_ip_fallback(self):
        """mock socket 失敗時 lan_ip 應 fallback 為 127.0.0.1"""
        # patch _get_lan_ip 在 web.app module 中
        with patch("web.app._get_lan_ip", return_value="127.0.0.1"):
            client = _make_client()
            response = client.get("/help")
            assert response.status_code == 200
            html = response.text
            assert "127.0.0.1" in html, \
                "socket 失敗時 lan_ip 應 fallback 127.0.0.1 並渲染到 HTML"
