"""
test_avsox_scraper.py - AVSOX 爬蟲單元測試（TASK-36-T9）

測試策略：
- 全 mock，不連網
- Mock scraper._session.get 回傳 inline HTML fixture
- rate_limit 也 mock 掉（避免 sleep）
"""

import pytest
from unittest.mock import patch, MagicMock


# ============================================================
# HTML Fixtures
# ============================================================

FULL_FIELDS_HTML = """\
<html><head><meta charset="utf-8"></head><body>
<div class="container"><h3>012523-001 タイトル</h3></div>
<div class="col-md-3 info">
  <p><span style="color:#CC0000;">012523-001</span></p>
  <p><span>发行时间:</span> 2023-01-25</p>
  <p><span>长度:</span> 60分钟</p>
  <p><a href="/studio/testmaker">TestMaker</a></p>
  <p><a href="/series/testseries">テストシリーズ</a></p>
</div>
<div id="avatar-waterfall">
  <a href="/actress/1"><span>テスト女優</span></a>
</div>
<a class="bigImage" href="https://pics.example.com/cover.jpg"></a>
</body></html>
"""

NO_DURATION_HTML = """\
<html><head><meta charset="utf-8"></head><body>
<div class="container"><h3>012523-001 タイトル</h3></div>
<div class="col-md-3 info">
  <p><span style="color:#CC0000;">012523-001</span></p>
  <p><span>发行时间:</span> 2023-01-25</p>
  <p><a href="/studio/testmaker">TestMaker</a></p>
  <p><a href="/series/testseries">テストシリーズ</a></p>
</div>
<div id="avatar-waterfall">
  <a href="/actress/1"><span>テスト女優</span></a>
</div>
<a class="bigImage" href="https://pics.example.com/cover.jpg"></a>
</body></html>
"""

NO_SERIES_HTML = """\
<html><head><meta charset="utf-8"></head><body>
<div class="container"><h3>012523-001 タイトル</h3></div>
<div class="col-md-3 info">
  <p><span style="color:#CC0000;">012523-001</span></p>
  <p><span>发行时间:</span> 2023-01-25</p>
  <p><span>长度:</span> 60分钟</p>
  <p><a href="/studio/testmaker">TestMaker</a></p>
</div>
<div id="avatar-waterfall">
  <a href="/actress/1"><span>テスト女優</span></a>
</div>
<a class="bigImage" href="https://pics.example.com/cover.jpg"></a>
</body></html>
"""

# Search result page with one result
SEARCH_HTML = """\
<html><body>
<div id="waterfall">
  <div>
    <a href="//avsox.click/cn/movie/012523001">
      <div class="photo-info"><span><date>012523-001</date><date>2023-01-25</date></span></div>
      <div class="photo-frame"><img src="//pics.example.com/poster.jpg"></div>
    </a>
  </div>
</div>
</body></html>
"""


# ============================================================
# Helpers
# ============================================================

def make_response(html: str, status_code: int = 200, content: bytes = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = html
    resp.content = content if content is not None else html.encode("utf-8")
    return resp


def run_search(scraper, detail_html: str, number: str = "012523-001"):
    """
    Mock _search_and_get_url to bypass the search page,
    then mock the detail page GET to return detail_html.
    """
    detail_resp = make_response(detail_html)
    with patch.object(
        scraper,
        "_search_and_get_url",
        return_value=("https://avsox.click/cn/movie/012523001", ""),
    ):
        scraper._session.get = MagicMock(return_value=detail_resp)
        return scraper.search(number)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def scraper():
    from core.scrapers.avsox import AVSOXScraper
    with patch("core.scrapers.avsox.rate_limit"):
        s = AVSOXScraper()
        yield s


# ============================================================
# Tests
# ============================================================

class TestFullFields:
    """happy path: duration=60 (int), series 正確"""

    def test_duration_is_int(self, scraper):
        video = run_search(scraper, FULL_FIELDS_HTML)
        assert video is not None
        assert video.duration == 60
        assert isinstance(video.duration, int)

    def test_series_present(self, scraper):
        video = run_search(scraper, FULL_FIELDS_HTML)
        assert video is not None
        assert video.series == "テストシリーズ"


class TestNoDuration:
    """页面無長度欄位 → duration=None"""

    def test_duration_none(self, scraper):
        video = run_search(scraper, NO_DURATION_HTML)
        assert video is not None
        assert video.duration is None


class TestNoSeries:
    """页面無系列欄位 → series=''"""

    def test_series_empty(self, scraper):
        video = run_search(scraper, NO_SERIES_HTML)
        assert video is not None
        assert video.series == ""
