"""
tests/unit/test_javlibrary_scraper.py
──────────────────────────────────────
mock transport 驗 search 流程（TDD-lite RED → GREEN）

情境 a–g：
  a) single-hit 302 → detail page 直接 parse（fetch 呼叫一次）
  b) multi-result → 兩次 fetch
  c) not-found：_extract_detail_url 回 None
  d) not-found：title + cover 同時空
  e) transport None → CfTransportUnavailable
  f) fetch 回 CF challenge HTML → CfChallengeRequired
  g) search_by_keyword 回空 list
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.cf_transport import CfChallengeRequired, CfTransportUnavailable
from core.scrapers.javlibrary import JavLibraryScraper
from core.scrapers.models import Video

# ──────────────────────────────────────
# 共用 fixture HTML
# ──────────────────────────────────────

DETAIL_HTML = """\
<html><head><title>TCD-332 恥辱の映像</title></head><body>
  <h3 class="post-title">TCD-332　恥辱の映像 鈴白めいか</h3>
  <div id="video_id"><table><tr><td class="text">TCD-332</td></tr></table></div>
  <div id="video_date"><table><tr><td class="text">2026-05-12</td></tr></table></div>
  <div id="video_length"><table><tr><td class="text"><span>126</span></td></tr></table></div>
  <div id="video_director"><table><tr><td class="text"><span><a>監督名</a></span></td></tr></table></div>
  <div id="video_maker"><table><tr><td class="text"><span><a>TRANS CLUB</a></span></td></tr></table></div>
  <div id="video_label"><table><tr><td class="text"><span><a>----</a></span></td></tr></table></div>
  <div id="video_review"><span>(8.50)</span></div>
  <img id="video_jacket_img" src="//pics.dmm.co.jp/mono/tcd332pl.jpg" />
  <div id="video_genres"><a>変性者</a><a>単体作品</a></div>
  <div id="video_cast"><span class="star"><a>鈴白めいか</a></span></div>
  <div class="previewthumbs">
    <a href="//pics.dmm.co.jp/s1.jpg"><img></a>
  </div>
</body></html>"""

SEARCH_RESULT_HTML = """\
<html><head><title>Search Results</title></head><body>
  <div class="video"><a href="./javmezzbqu.html" title="TCD-332 恥辱...">TCD-332 恥辱...</a></div>
</body></html>"""

EMPTY_DETAIL_HTML = """\
<html><head><title>TCD-332</title></head><body>
  <div id="video_id"><table><tr><td class="text">TCD-332</td></tr></table></div>
</body></html>"""

CF_CHALLENGE_HTML = """\
<html><head><title>Just a moment...</title></head><body>
  <form id="challenge-form"></form>
</body></html>"""

NO_RESULT_HTML = """\
<html><head><title>No Results</title></head><body>
  <p>No results.</p>
</body></html>"""

PATCH_TARGET = "core.scrapers.javlibrary.get_cf_transport"


def _make_transport(*html_responses: str) -> MagicMock:
    """建立回傳依序 HTML 的 mock transport"""
    transport = MagicMock()
    transport.fetch.side_effect = list(html_responses)
    return transport


# ──────────────────────────────────────
# (a) single-hit 302 → detail page 直接 parse
# ──────────────────────────────────────

def test_search_single_hit_returns_video():
    """mock transport fetch 一次回傳含 #video_id 的 HTML，結果應回傳 Video"""
    transport = _make_transport(DETAIL_HTML)
    with patch(PATCH_TARGET, return_value=transport):
        scraper = JavLibraryScraper()
        result = scraper.search("TCD-332")
    assert isinstance(result, Video)
    assert result.source == "javlibrary"


def test_search_single_hit_detail_url_is_empty():
    """FIX-4：single-hit 302 路徑 detail_url 應為空字串（非 search-php URL）"""
    transport = _make_transport(DETAIL_HTML)
    with patch(PATCH_TARGET, return_value=transport):
        scraper = JavLibraryScraper()
        result = scraper.search("TCD-332")
    assert result is not None
    assert result.detail_url == "", (
        f"single-hit 的 detail_url 應為空字串（非 search-php URL），got: {result.detail_url!r}"
    )


def test_search_single_hit_fetch_called_once():
    """single-hit 路徑 fetch 只應呼叫一次"""
    transport = _make_transport(DETAIL_HTML)
    with patch(PATCH_TARGET, return_value=transport):
        scraper = JavLibraryScraper()
        scraper.search("TCD-332")
    assert transport.fetch.call_count == 1


def test_search_single_hit_title_not_empty():
    transport = _make_transport(DETAIL_HTML)
    with patch(PATCH_TARGET, return_value=transport):
        scraper = JavLibraryScraper()
        result = scraper.search("TCD-332")
    assert result is not None
    assert result.title != ""


def test_search_single_hit_tags():
    transport = _make_transport(DETAIL_HTML)
    with patch(PATCH_TARGET, return_value=transport):
        scraper = JavLibraryScraper()
        result = scraper.search("TCD-332")
    assert result is not None
    assert "変性者" in result.tags


def test_search_single_hit_rating():
    transport = _make_transport(DETAIL_HTML)
    with patch(PATCH_TARGET, return_value=transport):
        scraper = JavLibraryScraper()
        result = scraper.search("TCD-332")
    assert result is not None
    assert result.rating == 8.5


# ──────────────────────────────────────
# (b) multi-result → 兩次 fetch
# ──────────────────────────────────────

def test_search_multi_result_returns_video():
    """第一次 fetch 搜尋列表，第二次 fetch 詳情頁，應回傳 Video"""
    transport = _make_transport(SEARCH_RESULT_HTML, DETAIL_HTML)
    with patch(PATCH_TARGET, return_value=transport):
        scraper = JavLibraryScraper()
        result = scraper.search("TCD-332")
    assert isinstance(result, Video)


def test_search_multi_result_fetch_called_twice():
    """multi-result 路徑 fetch 應呼叫兩次"""
    transport = _make_transport(SEARCH_RESULT_HTML, DETAIL_HTML)
    with patch(PATCH_TARGET, return_value=transport):
        scraper = JavLibraryScraper()
        scraper.search("TCD-332")
    assert transport.fetch.call_count == 2


# ──────────────────────────────────────
# (c) not-found：_extract_detail_url 回 None
# ──────────────────────────────────────

def test_search_not_found_no_video_links():
    """搜尋頁無 .video a，應回傳 None 不拋例外"""
    transport = _make_transport(NO_RESULT_HTML)
    with patch(PATCH_TARGET, return_value=transport):
        scraper = JavLibraryScraper()
        result = scraper.search("TCD-332")
    assert result is None


# ──────────────────────────────────────
# (d) not-found：title + cover 同時空
# ──────────────────────────────────────

def test_search_not_found_empty_title_and_cover():
    """parse 出的 title/cover 均空，應回傳 None"""
    transport = _make_transport(EMPTY_DETAIL_HTML)
    with patch(PATCH_TARGET, return_value=transport):
        scraper = JavLibraryScraper()
        result = scraper.search("TCD-332")
    assert result is None


# ──────────────────────────────────────
# (e) transport None → CfTransportUnavailable
# ──────────────────────────────────────

def test_search_no_transport_raises_unavailable():
    """get_cf_transport() 回傳 None 應拋 CfTransportUnavailable"""
    with patch(PATCH_TARGET, return_value=None):
        scraper = JavLibraryScraper()
        with pytest.raises(CfTransportUnavailable):
            scraper.search("TCD-332")


# ──────────────────────────────────────
# (f) fetch 回 CF challenge HTML → CfChallengeRequired
# ──────────────────────────────────────

def test_search_cf_challenge_raises_required():
    """fetch 回 CF challenge page 應拋 CfChallengeRequired"""
    transport = _make_transport(CF_CHALLENGE_HTML)
    with patch(PATCH_TARGET, return_value=transport):
        scraper = JavLibraryScraper()
        with pytest.raises(CfChallengeRequired):
            scraper.search("TCD-332")


# ──────────────────────────────────────
# (g) search_by_keyword 回空 list
# ──────────────────────────────────────

def test_search_by_keyword_returns_empty_list():
    """search_by_keyword 一律回傳空 list，不拋例外"""
    transport = MagicMock()
    with patch(PATCH_TARGET, return_value=transport):
        scraper = JavLibraryScraper()
        result = scraper.search_by_keyword("葵つかさ")
    assert result == []
    # transport.fetch 不應被呼叫
    transport.fetch.assert_not_called()


def test_search_by_keyword_no_transport_still_returns_empty():
    """即使 transport=None，search_by_keyword 仍回傳空 list"""
    with patch(PATCH_TARGET, return_value=None):
        scraper = JavLibraryScraper()
        result = scraper.search_by_keyword("keyword")
    assert result == []


# ──────────────────────────────────────
# (h) 回歸：footer 含 利用規約/18歳 不誤判 age gate
# ──────────────────────────────────────

# 有效詳情頁 HTML — 含 #video_id / h3.post-title / img#video_jacket_img，
# 同時在 footer 放了 「利用規約」與「18歳以上」字串（真實 javlibrary 頁面的樣貌）。
# 修正前：_is_age_gate 命中 footer → search() 誤拋 CfChallengeRequired。
# 修正後：search() 正常解析，回傳 Video。
DETAIL_HTML_WITH_TERMS_FOOTER = """\
<html><head><title>TCD-332 恥辱の映像</title></head><body>
  <h3 class="post-title">TCD-332　恥辱の映像 鈴白めいか</h3>
  <div id="video_id"><table><tr><td class="text">TCD-332</td></tr></table></div>
  <div id="video_date"><table><tr><td class="text">2026-05-12</td></tr></table></div>
  <div id="video_length"><table><tr><td class="text"><span>126</span></td></tr></table></div>
  <div id="video_maker"><table><tr><td class="text"><span><a>TRANS CLUB</a></span></td></tr></table></div>
  <div id="video_label"><table><tr><td class="text"><span><a>----</a></span></td></tr></table></div>
  <div id="video_review"><span>(8.50)</span></div>
  <img id="video_jacket_img" src="//pics.dmm.co.jp/mono/tcd332pl.jpg" />
  <div id="video_genres"><a>変性者</a></div>
  <div id="video_cast"><span class="star"><a>鈴白めいか</a></span></div>
  <footer>
    <a href="/ja/agreement.php">利用規約</a>
    本サービスは18歳以上の方のみご利用いただけます。
    <a href="/ja/index.php?mode=over18">18歳以上</a>
  </footer>
</body></html>"""


def test_search_valid_page_with_terms_footer_does_not_raise():
    """
    回歸：有效詳情頁 footer 含「利用規約」「18歳以上」字串，
    search() 不應拋 CfChallengeRequired，應正常回傳 Video
    且 title / cover 正確。
    （修正前此測試 FAIL；修正後 PASS）
    """
    transport = _make_transport(DETAIL_HTML_WITH_TERMS_FOOTER)
    with patch(PATCH_TARGET, return_value=transport):
        scraper = JavLibraryScraper()
        result = scraper.search("TCD-332")

    assert isinstance(result, Video), "應回傳 Video，不應拋例外或回傳 None"
    assert "恥辱" in result.title, f"title 應含番號後標題，got: {result.title!r}"
    assert result.cover_url.startswith("https://"), f"cover_url 應補全 https:，got: {result.cover_url!r}"


# ──────────────────────────────────────
# duration int 轉換明確斷言
# ──────────────────────────────────────

def test_search_single_hit_duration_is_int():
    """single-hit 路徑 duration 應解析為 int 126（不是 str 或 None）"""
    transport = _make_transport(DETAIL_HTML)
    with patch(PATCH_TARGET, return_value=transport):
        scraper = JavLibraryScraper()
        result = scraper.search("TCD-332")
    assert result is not None
    assert result.duration == 126, f"duration 應為 int 126，got: {result.duration!r}"
    assert isinstance(result.duration, int), f"duration 型別應為 int，got: {type(result.duration)}"


# ──────────────────────────────────────
# FIX-5：number guard — fallback 回錯片守衛
# ──────────────────────────────────────

# 詳情頁 HTML，番號為 ABW-001（與請求 TCD-332 不符）
WRONG_NUMBER_DETAIL_HTML = """\
<html><head><title>ABW-001 別の映像</title></head><body>
  <h3 class="post-title">ABW-001　別の映像 テスト女優</h3>
  <div id="video_id"><table><tr><td class="text">ABW-001</td></tr></table></div>
  <div id="video_date"><table><tr><td class="text">2026-01-10</td></tr></table></div>
  <div id="video_maker"><table><tr><td class="text"><span><a>テストメーカー</a></span></td></tr></table></div>
  <img id="video_jacket_img" src="//pics.dmm.co.jp/mono/abw001pl.jpg" />
  <div id="video_genres"><a>単体作品</a></div>
</body></html>"""

# 多命中搜尋結果頁（番號 TCD-332 無精確比對，fallback 到第一個連結）
SEARCH_RESULT_MISMATCH_HTML = """\
<html><head><title>Search Results</title></head><body>
  <div class="video"><a href="./javabwxxx.html" title="ABW-001 別の映像">ABW-001 別の映像</a></div>
  <div class="video"><a href="./javother.html" title="ZZZ-999 他の映像">ZZZ-999 他の映像</a></div>
</body></html>"""


def test_search_multi_result_number_mismatch_returns_none():
    """
    FIX-5：多命中 fallback 到 links[0]，parse 出的番號與請求番號不符
    → search() 應回 None（誠實 miss，不回錯片資料）。
    """
    # 第一次 fetch 回搜尋列表（無 TCD-332 精確比對，fallback links[0] = ABW-001 頁）
    # 第二次 fetch 回 ABW-001 詳情頁（番號不符）
    transport = _make_transport(SEARCH_RESULT_MISMATCH_HTML, WRONG_NUMBER_DETAIL_HTML)
    with patch(PATCH_TARGET, return_value=transport):
        scraper = JavLibraryScraper()
        result = scraper.search("TCD-332")

    assert result is None, (
        f"fallback 回錯番號（ABW-001 ≠ TCD-332）時應回 None，got: {result!r}"
    )


def test_search_multi_result_correct_number_returns_video():
    """
    FIX-5 正常路徑：多命中，links[0] parse 出的番號與請求番號相符
    → search() 仍應回 Video（守衛不誤殺合法命中）。
    """
    transport = _make_transport(SEARCH_RESULT_HTML, DETAIL_HTML)
    with patch(PATCH_TARGET, return_value=transport):
        scraper = JavLibraryScraper()
        result = scraper.search("TCD-332")

    assert isinstance(result, Video), (
        f"number 相符的多命中路徑應回 Video，got: {result!r}"
    )
    assert result.number == "TCD-332"
