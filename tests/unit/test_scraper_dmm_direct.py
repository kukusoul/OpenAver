"""
Tests for Phase 37d T3 — Proxy `direct` 模式

覆蓋 _is_dmm_enabled() / _dmm_proxy_url() helpers 和 DMMScraper 行為。
"""
import json
import pytest
from unittest.mock import patch, MagicMock

from core.scrapers.dmm import DMMScraper
from core.scrapers.models import ScraperConfig


# ── TestIsDmmEnabled ──────────────────────────────────────────────────────────

class TestIsDmmEnabled:
    """_is_dmm_enabled() helper 邊界條件"""

    def test_empty_string_returns_false(self):
        from core.scraper import _is_dmm_enabled
        assert _is_dmm_enabled('') is False

    def test_whitespace_only_returns_false(self):
        from core.scraper import _is_dmm_enabled
        assert _is_dmm_enabled('  ') is False

    def test_direct_lowercase_returns_true(self):
        from core.scraper import _is_dmm_enabled
        assert _is_dmm_enabled('direct') is True

    def test_direct_uppercase_returns_true(self):
        from core.scraper import _is_dmm_enabled
        assert _is_dmm_enabled('DIRECT') is True

    def test_real_proxy_url_returns_true(self):
        from core.scraper import _is_dmm_enabled
        assert _is_dmm_enabled('http://192.168.1.1:8888') is True


# ── TestDmmProxyUrl ───────────────────────────────────────────────────────────

class TestDmmProxyUrl:
    """_dmm_proxy_url() helper 邊界條件"""

    def test_direct_lowercase_returns_empty(self):
        from core.scraper import _dmm_proxy_url
        assert _dmm_proxy_url('direct') == ''

    def test_direct_uppercase_returns_empty(self):
        from core.scraper import _dmm_proxy_url
        assert _dmm_proxy_url('DIRECT') == ''

    def test_real_proxy_url_returns_original(self):
        from core.scraper import _dmm_proxy_url
        url = 'http://192.168.1.1:8888'
        assert _dmm_proxy_url(url) == url


# ── TestDmmScraperDirect ──────────────────────────────────────────────────────

class TestDmmScraperDirect:
    """DMMScraper session.proxies 行為"""

    def test_empty_proxy_url_trust_env_false(self):
        """proxy_url='' → trust_env=False（不吃環境 proxy，直連模式）"""
        from core.scrapers import DMMScraper, ScraperConfig
        scraper = DMMScraper(ScraperConfig(proxy_url=''))
        assert scraper._session.trust_env is False, \
            "proxy_url='' 時 trust_env 必須為 False（阻止環境 proxy 介入）"

    def test_real_proxy_url_proxies_set(self):
        """proxy_url='http://...' → session.proxies 已設定"""
        from core.scrapers import DMMScraper, ScraperConfig
        proxy = 'http://192.168.1.1:8888'
        scraper = DMMScraper(ScraperConfig(proxy_url=proxy))
        assert scraper._session.proxies.get('http') == proxy
        assert scraper._session.proxies.get('https') == proxy


# ── TestSearchDirect ──────────────────────────────────────────────────────────

class TestSearchDirect:
    """search_jav() 整合測試 — 確認 direct 模式正確路由"""

    def test_search_jav_direct_includes_dmm(self):
        """proxy_url='direct' → dmm_config 非 None → DMM 進入 scrapers 列表"""
        from core.scraper import _is_dmm_enabled, _dmm_proxy_url
        proxy_url = 'direct'
        assert _is_dmm_enabled(proxy_url) is True
        assert _dmm_proxy_url(proxy_url) == ''

        # 驗證傳給 DMMScraper 的 proxy_url 是空字串（直連）
        from core.scrapers import DMMScraper, ScraperConfig
        dmm_config = ScraperConfig(proxy_url=_dmm_proxy_url(proxy_url))
        scraper = DMMScraper(dmm_config)
        assert scraper._session.trust_env is False, \
            "direct 模式下 DMMScraper 的 trust_env 必須為 False（不走環境 proxy）"

    def test_search_jav_direct_dmm_config_not_none(self):
        """proxy_url='direct' → _is_dmm_enabled=True → dmm_config 建立（非 None）"""
        from core.scraper import _is_dmm_enabled, _dmm_proxy_url
        from core.scrapers import ScraperConfig
        proxy_url = 'direct'
        dmm_config = ScraperConfig(proxy_url=_dmm_proxy_url(proxy_url)) \
            if _is_dmm_enabled(proxy_url) else None
        assert dmm_config is not None, \
            "proxy_url='direct' 時 dmm_config 不應為 None"

    def test_empty_proxy_url_dmm_config_is_none(self):
        """proxy_url='' → _is_dmm_enabled=False → dmm_config 為 None

        關鍵邊界：空字串不可被誤判為 direct，DMM 不得啟用。
        """
        from core.scraper import _is_dmm_enabled, _dmm_proxy_url
        from core.scrapers import ScraperConfig
        proxy_url = ''
        # 1. _is_dmm_enabled 必須為 False
        assert _is_dmm_enabled(proxy_url) is False, \
            "proxy_url='' 時 _is_dmm_enabled 必須為 False"
        # 2. dmm_config 必須為 None
        dmm_config = ScraperConfig(proxy_url=_dmm_proxy_url(proxy_url)) \
            if _is_dmm_enabled(proxy_url) else None
        assert dmm_config is None, \
            "proxy_url='' 時 dmm_config 必須為 None（不得啟用 DMM）"


# ============================================================
# Mock Data (from test_new_scrapers.py)
# ============================================================

DMM_SEARCH_RESPONSE = {
    "data": {
        "legacySearchPPV": {
            "result": {
                "contents": [{"id": "sone00205"}]
            }
        }
    }
}

DMM_DETAIL_RESPONSE = {
    "data": {
        "ppvContent": {
            "id": "sone00205",
            "title": "成人への卒業",
            "description": "テスト",
            "packageImage": {"largeUrl": "https://pics.dmm.co.jp/sone205pl.jpg"},
            "makerReleasedAt": "2024-03-19T00:00:00+09:00",
            "duration": 120,
            "actresses": [{"name": "Nana Miho"}],
            "directors": [],
            "series": {"name": ""},
            "maker": {"name": "S1 NO.1 STYLE"},
            "makerContentId": "SONE-205",
        }
    }
}


def _make_mock_resp(status_code=200, json_data=None, content=None):
    """Build a MagicMock that mimics requests.Response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    if json_data is not None:
        mock_resp.json = lambda: json_data
    if content is not None:
        mock_resp.content = content
    return mock_resp


# ============================================================
# Tests merged from integration/test_new_scrapers.py TestDMMScraper
# ============================================================

class TestDMMScraperIntegration:
    """DMM scraper tests (merged from test_new_scrapers.py)"""

    @pytest.fixture(autouse=True)
    def _no_rate_limit(self, monkeypatch):
        """跳過 rate_limit sleep，加速測試"""
        monkeypatch.setattr("core.scrapers.dmm.rate_limit", lambda *a, **kw: None)

    @pytest.fixture
    def dmm_scraper(self, tmp_path, monkeypatch):
        """DMM scraper with isolated cache files"""
        import core.scrapers.dmm as dmm_module
        monkeypatch.setattr(dmm_module, "CACHE_FILE", tmp_path / "dmm_content_ids.json")
        monkeypatch.setattr(dmm_module, "PREFIX_FILE", tmp_path / "dmm_prefix_hints.json")
        config = ScraperConfig(proxy_url="http://test-proxy:8080")
        return DMMScraper(config)

    def test_dmm_no_proxy_session_proxies_not_set(self):
        """無 proxy_url 時 session.proxies 不被設定（直連模式）"""
        scraper = DMMScraper()  # 無 proxy_url → 直連模式
        assert not scraper._session.proxies, \
            "proxy_url='' 時 session.proxies 不應被設定"

    def test_dmm_cache_hit(self, dmm_scraper, tmp_path, monkeypatch):
        """快取命中時不呼叫 search query（detail query + probe query，不超過 2 次）"""
        import core.scrapers.dmm as dmm_module
        cache_path = tmp_path / "dmm_content_ids.json"
        cache_path.write_text('{"SONE-205": "sone00205"}', encoding='utf-8')

        detail_resp = _make_mock_resp(status_code=200, json_data=DMM_DETAIL_RESPONSE)

        with patch.object(dmm_scraper._session, 'post', return_value=detail_resp) as mock_post, \
             patch.object(dmm_scraper, '_fetch_tags_from_html', return_value=[]), \
             patch('core.scrapers.dmm.rate_limit'):
            video = dmm_scraper.search("SONE-205")

        assert video is not None
        assert video.title == "成人への卒業"
        assert video.number == "SONE-205"
        for call_args in mock_post.call_args_list:
            payload = call_args[1].get('json', {}) if call_args[1] else {}
            query_str = payload.get('query', '')
            assert 'legacySearchPPV' not in query_str, "Cache hit should not trigger search query"

    def test_dmm_graphql_success(self, dmm_scraper):
        """無快取時依次呼叫 search query + detail query，成功返回 Video"""
        search_resp = _make_mock_resp(status_code=200, json_data=DMM_SEARCH_RESPONSE)
        detail_resp = _make_mock_resp(status_code=200, json_data=DMM_DETAIL_RESPONSE)

        with patch.object(dmm_scraper._session, 'post', side_effect=[
            _make_mock_resp(status_code=404),  # _convert_with_hints → _fetch_by_id → 404
            search_resp,                        # _search_content_id
            detail_resp,                        # _fetch_by_id(discovered_cid)
        ]), \
             patch.object(dmm_scraper, '_fetch_tags_from_html', return_value=[]), \
             patch('core.scrapers.dmm.rate_limit'):
            video = dmm_scraper.search("SONE-205")

        assert video is not None
        assert video.number == "SONE-205"
        assert video.title == "成人への卒業"
        assert video.source == "dmm"
        assert "dmm.co.jp" in video.detail_url
        assert video.date == "2024-03-19"
        assert len(video.actresses) == 1
        assert video.actresses[0].name == "Nana Miho"
        assert video.maker == "S1 NO.1 STYLE"

    def test_dmm_search_content_id_prefers_hyphenated_exact_query(self, dmm_scraper):
        """BZ-01 需優先用含 hyphen 查詢，避免 BZ01 命中 PBZ 系列。"""
        search_resp = _make_mock_resp(status_code=200, json_data={
            "data": {
                "legacySearchPPV": {
                    "result": {"contents": [{"id": "61bz01"}]}
                }
            }
        })

        with patch.object(dmm_scraper._session, 'post', return_value=search_resp) as mock_post:
            content_id = dmm_scraper._search_content_id("BZ-01")

        assert content_id == "61bz01"
        payload = mock_post.call_args.kwargs['json']
        assert payload['variables']['queryWord'] == "BZ-01"

    def test_dmm_search_content_id_rejects_substring_prefix_match(self, dmm_scraper):
        """BZ-01 不應因 content_id 內含 bz 而誤選 PBZ-016。"""
        empty_resp = _make_mock_resp(status_code=200, json_data={
            "data": {
                "legacySearchPPV": {
                    "result": {"contents": []}
                }
            }
        })
        broad_resp = _make_mock_resp(status_code=200, json_data={
            "data": {
                "legacySearchPPV": {
                    "result": {"contents": [{"id": "33pbz016"}]}
                }
            }
        })

        with patch.object(dmm_scraper._session, 'post', side_effect=[empty_resp, broad_resp]):
            content_id = dmm_scraper._search_content_id("BZ-01")

        assert content_id is None

    def test_dmm_search_content_id_derives_target_from_same_prefix_sibling(self, dmm_scraper):
        """BZ-01 搜尋只回 BZ-016 sibling 時，可推導 DMM content_id=61bz01。"""
        empty_resp = _make_mock_resp(status_code=200, json_data={
            "data": {
                "legacySearchPPV": {
                    "result": {"contents": []}
                }
            }
        })
        sibling_resp = _make_mock_resp(status_code=200, json_data={
            "data": {
                "legacySearchPPV": {
                    "result": {"contents": [{"id": "61bz016"}]}
                }
            }
        })

        with patch.object(dmm_scraper._session, 'post', side_effect=[empty_resp, sibling_resp]):
            content_id = dmm_scraper._search_content_id("BZ-01")

        assert content_id == "61bz01"

    def test_dmm_result_number_preserves_requested_leading_zero(self, dmm_scraper):
        """DMM 回 BZ-1 時，精確搜尋結果應保留請求番號 BZ-01。"""
        video = DMM_DETAIL_RESPONSE["data"]["ppvContent"].copy()
        video.update({
            "id": "61bz01",
            "title": "エロ乳 とってもボインざんすの巻",
            "makerReleasedAt": None,
            "makerContentId": "BZ-1",
        })
        detail_response = {"data": {"ppvContent": video}}

        with patch.object(dmm_scraper, '_convert_with_hints', return_value='61bz01'), \
             patch.object(dmm_scraper._session, 'post', return_value=_make_mock_resp(status_code=200, json_data=detail_response)), \
             patch.object(dmm_scraper, '_fetch_tags_from_html', return_value=[]):
            result = dmm_scraper.search("BZ-01")

        assert result is not None
        assert result.number == "BZ-01"

    def test_dmm_result_number_rejects_different_prefix(self, dmm_scraper):
        """舊快取若把 BZ-01 指到 PBZ-016，不可視為同一番號。"""
        video = DMM_DETAIL_RESPONSE["data"]["ppvContent"].copy()
        video.update({"makerContentId": "PBZ-016"})
        detail_response = {"data": {"ppvContent": video}}

        with patch.object(dmm_scraper, '_convert_with_hints', return_value='33pbz016'), \
             patch.object(dmm_scraper, '_search_content_id', return_value=None), \
             patch.object(dmm_scraper._session, 'post', return_value=_make_mock_resp(status_code=200, json_data=detail_response)), \
             patch.object(dmm_scraper, '_fetch_tags_from_html', return_value=[]):
            result = dmm_scraper.search("BZ-01")

        assert result is None

    def test_dmm_search_falls_back_to_mono_dvd_page(self, dmm_scraper):
        """MXGS-791 類 DVD/mono 商品不在 PPV API 時，fallback 解析 mono 頁。"""
        null_detail_resp = _make_mock_resp(status_code=200, json_data={"data": {"ppvContent": None}})
        empty_search_resp = _make_mock_resp(status_code=200, json_data={
            "data": {
                "legacySearchPPV": {
                    "result": {"contents": []}
                }
            }
        })
        prefix_search_resp = _make_mock_resp(status_code=200, json_data={
            "data": {
                "legacySearchPPV": {
                    "result": {"contents": [{"id": "ipmxgs01432"}, {"id": "h_068mxgs01432"}]}
                }
            }
        })
        mono_html = """
        <html><head>
          <title>テスト mono タイトル - アダルトDVD通販 - FANZA</title>
          <meta property="og:image" content="https://pics.dmm.co.jp/mono/movie/adult/mxgs791/mxgs791pl.jpg">
        </head><body>
          <h1>テスト mono タイトル</h1>
          <table>
            <tr><td class="nw">出演者：</td><td><a>女優A</a><a>女優B</a></td></tr>
            <tr><td class="nw">発売日：</td><td>2015/01/01</td></tr>
            <tr><td class="nw">収録時間：</td><td>120分</td></tr>
            <tr><td class="nw">メーカー：</td><td>マキシング</td></tr>
            <tr><td class="nw">レーベル：</td><td>MAXING</td></tr>
            <tr><td class="nw">シリーズ：</td><td>テストシリーズ</td></tr>
            <tr><td class="nw">ジャンル：</td><td><a>単体作品</a><a>巨乳</a></td></tr>
          </table>
        </body></html>
        """.encode()
        not_found_resp = _make_mock_resp(status_code=404, content=b"not found")
        not_found_resp.url = "https://www.dmm.co.jp/mono/dvd/-/detail/=/cid=mxgs791/"
        mono_resp = _make_mock_resp(status_code=200, content=mono_html)
        mono_resp.url = "https://www.dmm.co.jp/mono/dvd/-/detail/=/cid=h_068mxgs791/"

        with patch.object(dmm_scraper._session, 'post', side_effect=[
            null_detail_resp,
            empty_search_resp,
            empty_search_resp,
            prefix_search_resp,
        ]), \
             patch.object(dmm_scraper._session, 'get', side_effect=[not_found_resp, not_found_resp, mono_resp]) as mock_get:
            result = dmm_scraper.search("MXGS-791")

        assert result is not None
        assert result.number == "MXGS-791"
        assert result.title == "テスト mono タイトル"
        assert [a.name for a in result.actresses] == ["女優A", "女優B"]
        assert result.date == "2015-01-01"
        assert result.duration == 120
        assert result.maker == "マキシング"
        assert result.tags == ["単体作品", "巨乳"]
        assert mock_get.call_args_list[-1].args[0].endswith('/cid=h_068mxgs791/')

    def test_dmm_detail_allows_missing_release_date(self, dmm_scraper):
        """DMM 部分舊片 makerReleasedAt=null，仍應回傳結果而非被 date 驗證丟棄。"""
        detail_response = {
            "data": {
                "ppvContent": {
                    "id": "h_208top001",
                    "title": "AYUNA 麻美あゆな",
                    "description": "テスト",
                    "packageImage": {"largeUrl": "https://pics.dmm.co.jp/top001pl.jpg"},
                    "makerReleasedAt": None,
                    "duration": 7140,
                    "actresses": [{"name": "麻美あゆな"}],
                    "directors": [],
                    "series": None,
                    "maker": {"name": "NEXT GROUP"},
                    "makerContentId": "TOP-001",
                }
            }
        }

        with patch.object(dmm_scraper._session, 'post', return_value=_make_mock_resp(status_code=200, json_data=detail_response)), \
             patch.object(dmm_scraper, '_fetch_tags_from_html', return_value=[]):
            video = dmm_scraper._fetch_by_id("h_208top001")

        assert video is not None
        assert video.number == "TOP-001"
        assert video.date == ""

    def test_dmm_detail_uses_delivery_start_date_when_release_date_missing(self, dmm_scraper):
        """KA-1897 類 PPV 作品 makerReleasedAt=null 時，使用 deliveryStartDate。"""
        detail_response = {
            "data": {
                "ppvContent": {
                    "id": "53ka1897",
                    "title": "FOREVER【坂本リナ】",
                    "description": "テスト",
                    "packageImage": {"largeUrl": "https://pics.dmm.co.jp/53ka01897pl.jpg"},
                    "makerReleasedAt": None,
                    "deliveryStartDate": "2004-07-17T01:00:01Z",
                    "duration": 5400,
                    "actresses": [{"name": "坂本リナ"}],
                    "directors": [],
                    "series": {"name": "FOREVER"},
                    "maker": {"name": "アリスJAPAN"},
                    "makerContentId": None,
                }
            }
        }

        with patch.object(dmm_scraper._session, 'post', return_value=_make_mock_resp(status_code=200, json_data=detail_response)), \
             patch.object(dmm_scraper, '_fetch_tags_from_html', return_value=[]):
            video = dmm_scraper._fetch_by_id("53ka1897")

        assert video is not None
        assert video.number == "KA-1897"
        assert video.date == "2004-07-17"

    def test_dmm_detail_falls_back_when_maker_content_id_missing(self, dmm_scraper):
        """DMM 部分舊片 makerContentId=null，應由 content_id 反推番號。"""
        detail_response = {
            "data": {
                "ppvContent": {
                    "id": "61ih90",
                    "title": "爆乳パパイヤ 結城かのん",
                    "description": "テスト",
                    "packageImage": {"largeUrl": "https://pics.dmm.co.jp/61ih00090pl.jpg"},
                    "makerReleasedAt": None,
                    "duration": 3600,
                    "actresses": [{"name": "結城かのん"}],
                    "directors": [],
                    "series": None,
                    "maker": {"name": "宇宙企画"},
                    "makerContentId": None,
                }
            }
        }

        with patch.object(dmm_scraper._session, 'post', return_value=_make_mock_resp(status_code=200, json_data=detail_response)), \
             patch.object(dmm_scraper, '_fetch_tags_from_html', return_value=[]):
            video = dmm_scraper._fetch_by_id("61ih90")

        assert video is not None
        assert video.number == "IH-90"
        assert video.date == ""

    def test_dmm_cache_isolation(self, dmm_scraper, tmp_path):
        """搜尋成功後 cache 寫入 tmp_path，不污染 project root"""
        detail_resp = _make_mock_resp(status_code=200, json_data=DMM_DETAIL_RESPONSE)

        with patch.object(dmm_scraper._session, 'post', return_value=detail_resp), \
             patch.object(dmm_scraper, '_fetch_tags_from_html', return_value=[]), \
             patch('core.scrapers.dmm.rate_limit'):
            video = dmm_scraper.search("SONE-205")

        # cache 應寫入 tmp_path 而非 project root
        assert (tmp_path / "dmm_content_ids.json").exists()
