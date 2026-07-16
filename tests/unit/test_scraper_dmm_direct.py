"""
Tests for Phase 37d T3 — Proxy `direct` 模式

覆蓋 _is_dmm_enabled() / _dmm_proxy_url() helpers 和 DMMScraper 行為。
"""
import json
import os

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
        assert scraper._session.trust_env is True, \
            "direct 模式下 DMMScraper 尊重系統代理（CD-134-6 反轉 4ee0baa2 的舊契約）"

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


# ── TestDmmRespectsSystemProxy ───────────────────────────────────────────────

_PROXY_ENVS = (
    "HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy",
    "NO_PROXY", "no_proxy", "ALL_PROXY", "all_proxy",
)


@pytest.fixture
def clean_proxy_env(monkeypatch):
    for name in _PROXY_ENVS:
        monkeypatch.delenv(name, raising=False)
    # urllib 的 getproxies_environment（requests 經 get_environ_proxies 走它）掃的是
    # **任何以 `_proxy` 結尾**的變數，不只上面那 8 個——開發機上若有 ftp_proxy /
    # socks_proxy 之類殘留，「無代理」那支會假紅。清乾淨這一整類。
    for name in [n for n in os.environ if n.lower().endswith("_proxy")]:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def _resolved_proxies(scraper, url="https://api.video.dmm.co.jp/graphql"):
    """把 requests 對環境變數的解析結果變成可斷言的具體值。"""
    return scraper._session.merge_environment_settings(url, {}, None, None, None)["proxies"]


class TestDmmRespectsSystemProxy:
    """CD-134-6／F4：direct 模式尊重系統代理（環境變數，三象限，斷言值互不相同）"""

    def test_empty_proxy_url_trust_env_true(self):
        """proxy_url='' → trust_env=True（尊重系統代理，CD-134-6／F4 反轉後的新契約）"""
        scraper = DMMScraper(ScraperConfig(proxy_url=''))
        assert scraper._session.trust_env is True, \
            "proxy_url='' 時 trust_env 必須為 True（尊重系統代理，見 spec-134 F4）"

    def test_empty_proxy_url_proxies_empty(self):
        """proxy_url='' → session.proxies 為空（交由 requests 依系統環境決定）"""
        scraper = DMMScraper(ScraperConfig(proxy_url=''))
        assert not scraper._session.proxies, \
            "proxy_url='' 時 session.proxies 必須為空"

    def test_explicit_proxy_url_proxies_set(self):
        """明確設定 proxy_url → session.proxies 包含 http/https 代理"""
        scraper = DMMScraper(ScraperConfig(proxy_url='http://x:1'))
        assert scraper._session.proxies == {
            'http': 'http://x:1',
            'https': 'http://x:1',
        }

    def test_env_https_proxy_is_respected(self, clean_proxy_env):
        """HTTPS_PROXY 有設 → 解析結果含該 proxy"""
        clean_proxy_env.setenv("HTTPS_PROXY", "http://env-proxy:1")
        scraper = DMMScraper(ScraperConfig(proxy_url=''))
        assert _resolved_proxies(scraper)["https"] == "http://env-proxy:1"

    def test_env_no_proxy_excludes_dmm_host(self, clean_proxy_env):
        """HTTPS_PROXY 有設 + NO_PROXY 命中 DMM API host → 代理被排除"""
        clean_proxy_env.setenv("HTTPS_PROXY", "http://env-proxy:1")
        clean_proxy_env.setenv("NO_PROXY", "api.video.dmm.co.jp")
        scraper = DMMScraper(ScraperConfig(proxy_url=''))
        assert _resolved_proxies(scraper) == {}

    def test_env_no_proxy_vars_is_clean_direct(self, clean_proxy_env):
        """無任何代理環境變數 → 解析結果無代理"""
        scraper = DMMScraper(ScraperConfig(proxy_url=''))
        assert _resolved_proxies(scraper) == {}


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
    def dmm_scraper(self, monkeypatch):
        """DMM scraper fixture"""
        import core.scrapers.dmm as dmm_module
        monkeypatch.setattr(dmm_module, "_shipped_table_cache", {})
        config = ScraperConfig(proxy_url="http://test-proxy:8080")
        return DMMScraper(config)

    def test_dmm_no_proxy_session_proxies_not_set(self):
        """無 proxy_url 時 session.proxies 不被設定（直連模式）"""
        scraper = DMMScraper()  # 無 proxy_url → 直連模式
        assert not scraper._session.proxies, \
            "proxy_url='' 時 session.proxies 不應被設定"

    def test_dmm_cache_hit(self, dmm_scraper):
        """前綴表命中時不呼叫 search query（detail query + probe query，不超過 2 次）"""
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
            _make_mock_resp(status_code=404),  # 補零第一試 → _fetch_by_id → 404
            _make_mock_resp(status_code=404),  # 不補零第二試 → _fetch_by_id → 404
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

    def test_dmm_search_content_id_query_word_order(self, dmm_scraper):
        """查詢式順序：'PFX NUM'（主）→ 'BZ-01'（帶 hyphen）→ 'BZ01'（壓縮）。

        主查詢式是 TASK-134a-T4 的 DoD，不得被擠掉；帶 hyphen／壓縮形是舊式短番號
        （BZ-01 用 'BZ 01' 搜不到）的補救，只在前面查不到時才發。
        """
        empty_resp = _make_mock_resp(status_code=200, json_data={
            "data": {"legacySearchPPV": {"result": {"contents": []}}}
        })

        with patch.object(dmm_scraper._session, 'post', return_value=empty_resp) as mock_post:
            assert dmm_scraper._search_content_id("BZ-01") is None

        sent = [c.kwargs['json']['variables']['queryWord'] for c in mock_post.call_args_list]
        assert sent == ["BZ 01", "BZ-01", "BZ01"]

    def test_dmm_search_content_id_stops_at_first_exact_hit(self, dmm_scraper):
        """主查詢式就命中時不再發後續查詢（省一次往返）。"""
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
        assert mock_post.call_count == 1
        assert mock_post.call_args.kwargs['json']['variables']['queryWord'] == "BZ 01"

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

        with patch.object(dmm_scraper._session, 'post', side_effect=[empty_resp, broad_resp, empty_resp]):
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

        with patch.object(dmm_scraper._session, 'post', side_effect=[empty_resp, sibling_resp, empty_resp]):
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

    def test_dmm_result_number_uses_canonical_for_padded_content_id_input(self, dmm_scraper):
        """ebvr00104 類 content_id 輸入不應覆蓋 DMM canonical 番號 EBVR-104。"""
        video = DMM_DETAIL_RESPONSE["data"]["ppvContent"].copy()
        video.update({
            "id": "ebvr00104",
            "title": "【VR】テスト",
            "makerReleasedAt": "2024-11-30T15:00:00Z",
            "makerContentId": "EBVR-104",
        })
        detail_response = {"data": {"ppvContent": video}}

        with patch.object(dmm_scraper, '_convert_with_hints', return_value='ebvr00104'), \
             patch.object(dmm_scraper._session, 'post', return_value=_make_mock_resp(status_code=200, json_data=detail_response)), \
             patch.object(dmm_scraper, '_fetch_tags_from_html', return_value=[]):
            result = dmm_scraper.search("ebvr00104")

        assert result is not None
        assert result.number == "EBVR-104"

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
        empty_mono_search_resp = _make_mock_resp(status_code=200, content=b"<html></html>")
        empty_mono_search_resp.url = "https://www.dmm.co.jp/mono/dvd/-/search/=/searchstr=MXGS-791/"
        mono_resp = _make_mock_resp(status_code=200, content=mono_html)
        mono_resp.url = "https://www.dmm.co.jp/mono/dvd/-/detail/=/cid=h_068mxgs791/"

        # POST 依 payload 分派而非固定清單——步驟 1 的補零／不補零兩試、
        # _search_content_id 的三個查詢式都會發 POST，寫死次數會隨流程微調就碎。
        def _post(url, json=None, **kwargs):
            query_word = ((json or {}).get('variables') or {}).get('queryWord')
            if query_word is None:
                return null_detail_resp              # ppvContent 詳情：查無此片
            if query_word == "MXGS":
                return prefix_search_resp            # _fetch_mono_by_number 的前綴搜尋
            return empty_search_resp                 # _search_content_id 的各查詢式

        with patch.object(dmm_scraper._session, 'post', side_effect=_post), \
             patch.object(dmm_scraper._session, 'get', side_effect=[
                 empty_mono_search_resp,
                 not_found_resp,
                 not_found_resp,
                 mono_resp,
             ]) as mock_get:
            result = dmm_scraper.search("MXGS-791")

        assert result is not None
        assert result.number == "MXGS-791"
        assert result.title == "テスト mono タイトル"
        assert [a.name for a in result.actresses] == ["女優A", "女優B"]
        assert result.date == "2015-01-01"
        assert result.duration == 120
        assert result.maker == "マキシング"
        assert result.tags == ["単体作品", "巨乳"]
        assert any(call.args[0].endswith('/cid=h_068mxgs791/') for call in mock_get.call_args_list)

    def test_dmm_search_falls_back_to_mono_search_result(self, dmm_scraper):
        """ABW-256 類 prefix 不在 PPV API 時，從 mono search detail link 取得 cid。"""
        null_detail_resp = _make_mock_resp(status_code=200, json_data={"data": {"ppvContent": None}})
        empty_search_resp = _make_mock_resp(status_code=200, json_data={
            "data": {
                "legacySearchPPV": {
                    "result": {"contents": []}
                }
            }
        })
        mono_search_html = '''
        <html><body>
          <a href="https://www.dmm.co.jp/mono/dvd/-/detail/=/cid=118abw256/">
            <span class="txt">夢の快楽射精 誘惑メンズエステ</span>
          </a>
        </body></html>
        '''.encode()
        mono_detail_html = """
        <html><head>
          <title>夢の快楽射精 誘惑メンズエステ - アダルトDVD通販 - FANZA</title>
        </head><body>
          <h1>夢の快楽射精 誘惑メンズエステ</h1>
          <table>
            <tr><td class="nw">出演者：</td><td><a>河合あすな</a></td></tr>
            <tr><td class="nw">発売日：</td><td>2018/01/01</td></tr>
            <tr><td class="nw">収録時間：</td><td>120分</td></tr>
            <tr><td class="nw">メーカー：</td><td>プレステージ</td></tr>
            <tr><td class="nw">ジャンル：</td><td><a>エステ</a></td></tr>
          </table>
          <ul id="sample-image-block">
            <li><a name="package-image"><img data-lazy="https://pics.dmm.co.jp/mono/movie/adult/118abw256/118abw256ps.jpg"></a></li>
            <li><a name="sample-image"><img data-lazy="https://pics.dmm.co.jp/digital/video/118abw256/118abw256-1.jpg"></a></li>
            <li><a name="sample-image"><img data-lazy="//pics.dmm.co.jp/digital/video/118abw256/118abw256-2.jpg"></a></li>
          </ul>
        </body></html>
        """.encode()
        not_found_resp = _make_mock_resp(status_code=404, content=b"not found")
        not_found_resp.url = "https://www.dmm.co.jp/mono/dvd/-/detail/=/cid=abw256/"
        mono_search_resp = _make_mock_resp(status_code=200, content=mono_search_html)
        mono_search_resp.url = "https://www.dmm.co.jp/mono/dvd/-/search/=/searchstr=ABW-256/"
        mono_detail_resp = _make_mock_resp(status_code=200, content=mono_detail_html)
        mono_detail_resp.url = "https://www.dmm.co.jp/mono/dvd/-/detail/=/cid=118abw256/"

        with patch.object(dmm_scraper._session, 'post', side_effect=[
            null_detail_resp,
            empty_search_resp,
            empty_search_resp,
            empty_search_resp,
        ]), \
             patch.object(dmm_scraper._session, 'get', side_effect=[
                 mono_search_resp,
                 not_found_resp,
                 not_found_resp,
                 mono_detail_resp,
             ]) as mock_get:
            result = dmm_scraper.search("ABW-256")

        assert result is not None
        assert result.number == "ABW-256"
        assert result.title == "夢の快楽射精 誘惑メンズエステ"
        assert result.date == "2018-01-01"
        assert [a.name for a in result.actresses] == ["河合あすな"]
        assert result.tags == ["エステ"]
        assert result.sample_images == [
            "https://pics.dmm.co.jp/digital/video/118abw256/118abw256jp-1.jpg",
            "https://pics.dmm.co.jp/digital/video/118abw256/118abw256jp-2.jpg",
        ]
        assert mock_get.call_args_list[-1].args[0].endswith('/cid=118abw256/')

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

    def test_dmm_search_success_writes_no_files(self, dmm_scraper, tmp_path, monkeypatch):
        """搜尋**成功**之後，專案根不得多出任何 DMM 資料檔（T12 DoD 2/3 的成功路徑那一半）。

        ⚠️ 2026-08-29 兩位 reviewer 各自指出：本測試改名前的斷言
        ``assert not (tmp_path / "dmm_content_ids.json").exists()`` **是恆真的**——
        沒有任何東西被指到 ``tmp_path``，就算有人把「寫快取」加回專案根，它也不會紅。

        姊妹測試 ``test_poisoned_local_files_do_not_affect_search`` 把 ``_fetch_by_id``
        mock 成恆回 ``None`` ⇒ 它只走得到**失敗**路徑，踩不到「搜尋成功後寫檔」那一段。
        ⇒ **成功路徑的「不寫檔」必須由這一支扛**，所以這裡把 ``PROJECT_ROOT`` 真的
        monkeypatch 到 ``tmp_path``，讓「有人把寫檔加回來」這件事在這裡看得見。
        """
        import core.scrapers.dmm as dmm_module
        monkeypatch.setattr(dmm_module, "PROJECT_ROOT", tmp_path)

        detail_resp = _make_mock_resp(status_code=200, json_data=DMM_DETAIL_RESPONSE)

        with patch.object(dmm_scraper._session, 'post', return_value=detail_resp), \
             patch.object(dmm_scraper, '_fetch_tags_from_html', return_value=[]), \
             patch('core.scrapers.dmm.rate_limit'):
            video = dmm_scraper.search("SONE-205")

        # 正向：這一輪真的成功了（否則下面的反向斷言會恆真）
        assert video is not None
        assert video.number == "SONE-205"

        # 反向：成功路徑一個檔都沒寫
        assert list(tmp_path.iterdir()) == [], (
            f"搜尋成功後 PROJECT_ROOT 多出檔案：{[p.name for p in tmp_path.iterdir()]}"
        )
