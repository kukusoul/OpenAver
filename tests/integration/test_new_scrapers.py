"""
Integration tests for scraper-related API endpoints (TestClient).

Covers:
- Proxy test endpoint (success / 403 / timeout / config persistence)
- Exact mode passes primary_source to search_jav
- Unknown source returns HTTP 400
"""
import pytest
import requests
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from web.app import app


# ============================================================
# TestProxyAPI — proxy test endpoint via TestClient
# ============================================================

class TestProxyAPI:
    """Proxy 測試 API 端點測試"""

    def test_proxy_test_endpoint_success(self, client):
        """Proxy 回傳 200 → success=True, reason='ok'"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("requests.post", return_value=mock_resp):
            resp = client.post("/api/proxy/test", json={"proxy_url": "http://test:8080"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["reason"] == "ok"

    def test_proxy_test_endpoint_403(self, client):
        """Proxy 回傳 403 → success=False, reason='non_jp'"""
        mock_resp = MagicMock()
        mock_resp.status_code = 403

        with patch("requests.post", return_value=mock_resp):
            resp = client.post("/api/proxy/test", json={"proxy_url": "http://test:8080"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["reason"] == "non_jp"

    def test_proxy_test_endpoint_timeout(self, client):
        """ConnectionError → success=False, reason='unreachable'"""
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError):
            resp = client.post("/api/proxy/test", json={"proxy_url": "http://bad:9999"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["reason"] == "unreachable"

    def test_config_proxy_url_persistence(self, client, temp_config_path):
        """proxy_url 寫入 config 後可讀回"""
        # 先取得當前 config，修改 proxy_url，再用 PUT 寫入
        get_resp = client.get("/api/config")
        cfg = get_resp.json()["data"]
        cfg["search"]["proxy_url"] = "http://jp-proxy:8080"
        client.put("/api/config", json=cfg)

        resp = client.get("/api/config")

        assert resp.status_code == 200
        assert resp.json()["data"]["search"]["proxy_url"] == "http://jp-proxy:8080"


# ============================================================
# TestPipeline — exact mode integration (creates own TestClient)
# ============================================================

class TestPipeline:
    """Pipeline integration test — exact mode passes primary_source via REST."""

    def test_exact_mode_passes_primary_source(self):
        """REST mode=exact → search_jav() 收到 primary_source（不再被忽略）"""
        client = TestClient(app)

        captured_kwargs = {}

        def fake_search_jav(number, source='auto', proxy_url='', primary_source='javbus'):
            captured_kwargs['primary_source'] = primary_source
            captured_kwargs['proxy_url'] = proxy_url
            return None  # no result needed; we only check kwargs

        with patch('core.config.load_config', return_value={
            'search': {
                'proxy_url': 'http://test-proxy:8080',
                'primary_source': 'dmm',
                'uncensored_mode_enabled': False,
            }
        }):
            with patch('web.routers.search.search_jav', side_effect=fake_search_jav):
                client.get("/api/search", params={"q": "SONE-205", "mode": "exact"})

        assert captured_kwargs.get('primary_source') == 'dmm', (
            "mode=exact branch must pass primary_source to search_jav(); "
            f"got {captured_kwargs.get('primary_source')!r}"
        )


# ============================================================
# TestUnknownSource — unknown source returns HTTP 400
# ============================================================

class TestUnknownSource:
    """未知 source 驗證測試 — API 層回傳 HTTP 400"""

    def test_api_unknown_source_returns_400(self):
        """GET /api/search?q=SONE-205&source=javguru → HTTP 400"""
        client = TestClient(app)
        resp = client.get("/api/search", params={"q": "SONE-205", "source": "javguru"})

        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data
        assert "javguru" in data["error"]
