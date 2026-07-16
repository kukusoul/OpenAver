"""
DMMScraper 舊片／DVD 補救路徑（fork 專屬）：多查詢式、同系列鄰居推 cid、
保留請求端前導零、makerContentId／makerReleasedAt 缺值退路、mono 商品頁 fallback。

獨立成檔（不放進上游的 test_scraper_dmm_direct.py），rebase 上游時不會撞到。
"""
from unittest.mock import MagicMock, patch

import pytest

from core.proxy_policy import ProxySettings
from core.scrapers.dmm import DMMScraper
from core.scrapers.models import ScraperConfig


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


class TestDMMLegacyFallbacks:
    """DMM 舊片補救路徑"""

    @pytest.fixture(autouse=True)
    def _no_rate_limit(self, monkeypatch):
        """跳過 rate_limit sleep，加速測試"""
        monkeypatch.setattr("core.scrapers.dmm.rate_limit", lambda *a, **kw: None)

    @pytest.fixture
    def dmm_scraper(self, monkeypatch):
        import core.scrapers.dmm as dmm_module
        monkeypatch.setattr(dmm_module, "_shipped_table_cache", {})
        return DMMScraper(ScraperConfig(proxy_settings=ProxySettings(url="")))

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
             patch.object(dmm_scraper, '_fetch_mono_by_number', return_value=None), \
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
