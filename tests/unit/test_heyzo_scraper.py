"""
test_heyzo_scraper.py - HEYZO 爬蟲單元測試（TASK-36-T9）

測試策略：
- 全 mock，不連網
- Mock scraper._session.get 回傳 inline HTML + JSON-LD fixture
- rate_limit 也 mock 掉（避免 sleep）
"""

import json
import pytest
from unittest.mock import patch, MagicMock


# ============================================================
# JSON-LD base (embedded in HTML)
# ============================================================

BASE_JSON_LD = {
    "@context": "http://schema.org",
    "@type": "Movie",
    "name": "テストタイトル",
    "dateCreated": "2023-01-17T00:00:00+09:00",
    "image": "//www.heyzo.com/contents/3000/0783/images/player_thumbnail.jpg",
    "actor": {"@type": "Person", "name": "Test Actress"},
    "aggregateRating": {"ratingValue": "4.2", "reviewCount": "100"},
}


def make_html(json_ld: dict, table_extra: str = "", gallery_html: str = "") -> bytes:
    """Build an en.heyzo.com-like HTML page with JSON-LD and optional table rows.

    The Series cell uses plain text (no <a>) to match the actual HEYZO English page,
    which is what the existing XPath '...td[1]/text()' expects.
    """
    json_str = json.dumps(json_ld)
    html = f"""\
<html><head>
<meta charset="utf-8">
<script type="application/ld+json">{json_str}</script>
</head><body>
<table class="movieInfo">
  <tbody>
    <tr><th>Series</th><td>テストシリーズ</td></tr>
    <tr><th>Type</th><td><a href="/type/1">美乳</a></td></tr>
    {table_extra}
  </tbody>
</table>
{gallery_html}
</body></html>
"""
    return html.encode("utf-8")


GALLERY_HTML = """\
<div class="movie-gallery">
  <a href="/contents/3000/0783/gallery/001.jpg"><img src="/contents/3000/0783/gallery/001s.jpg"></a>
  <a href="/contents/3000/0783/gallery/002.jpg"><img src="/contents/3000/0783/gallery/002s.jpg"></a>
</div>
"""

FULL_FIELDS_CONTENT = make_html(
    BASE_JSON_LD,
    table_extra='<tr><th>Duration</th><td>01:07:57</td></tr>',
    gallery_html=GALLERY_HTML,
)

NO_DURATION_CONTENT = make_html(
    BASE_JSON_LD,
    table_extra='',
    gallery_html=GALLERY_HTML,
)

INVALID_DURATION_CONTENT = make_html(
    BASE_JSON_LD,
    table_extra='<tr><th>Duration</th><td>--:--:--</td></tr>',
    gallery_html=GALLERY_HTML,
)

NO_SERIES_CONTENT = make_html(
    {**BASE_JSON_LD},
    table_extra='<tr><th>Duration</th><td>01:07:57</td></tr>',
    gallery_html=GALLERY_HTML,
)
# Override series row to show "-----"
NO_SERIES_CONTENT = (
    b'<html><head><meta charset="utf-8">'
    b'<script type="application/ld+json">'
    + json.dumps(BASE_JSON_LD).encode()
    + b"</script></head><body>"
    b'<table class="movieInfo"><tbody>'
    b"<tr><th>Series</th><td>-----</td></tr>"
    b"<tr><th>Type</th><td></td></tr>"
    b"<tr><th>Duration</th><td>01:07:57</td></tr>"
    b"</tbody></table>"
    + GALLERY_HTML.encode()
    + b"</body></html>"
)

NO_GALLERY_CONTENT = make_html(
    BASE_JSON_LD,
    table_extra='<tr><th>Duration</th><td>01:07:57</td></tr>',
    gallery_html="",
)


# ============================================================
# Helpers
# ============================================================

def make_response(content: bytes, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.text = content.decode("utf-8")
    resp.url = "https://en.heyzo.com/moviepages/0783/index.html"
    return resp


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def scraper():
    from core.scrapers.heyzo import HEYZOScraper
    with patch("core.scrapers.heyzo.rate_limit"):
        s = HEYZOScraper()
        yield s


# ============================================================
# Tests
# ============================================================

class TestFullFields:
    """happy path: series, duration, sample_images all correct"""

    def test_series(self, scraper):
        scraper._session.get = MagicMock(return_value=make_response(FULL_FIELDS_CONTENT))
        video = scraper.search("HEYZO-0783")
        assert video is not None
        assert video.series == "テストシリーズ"

    def test_duration_hhmm_ss_to_minutes(self, scraper):
        """01:07:57 → 67 分鐘（1*60 + 7）"""
        scraper._session.get = MagicMock(return_value=make_response(FULL_FIELDS_CONTENT))
        video = scraper.search("HEYZO-0783")
        assert video is not None
        assert video.duration == 67
        assert isinstance(video.duration, int)

    def test_sample_images_absolute_url(self, scraper):
        scraper._session.get = MagicMock(return_value=make_response(FULL_FIELDS_CONTENT))
        video = scraper.search("HEYZO-0783")
        assert video is not None
        assert len(video.sample_images) == 2
        for url in video.sample_images:
            assert url.startswith("https://")


class TestNoDuration:
    """Duration 欄位缺失 → duration=None"""

    def test_duration_none(self, scraper):
        scraper._session.get = MagicMock(return_value=make_response(NO_DURATION_CONTENT))
        video = scraper.search("HEYZO-0783")
        assert video is not None
        assert video.duration is None


class TestInvalidDuration:
    """Duration 格式異常（--:--:--）→ duration=None"""

    def test_invalid_duration_none(self, scraper):
        scraper._session.get = MagicMock(return_value=make_response(INVALID_DURATION_CONTENT))
        video = scraper.search("HEYZO-0783")
        assert video is not None
        assert video.duration is None


class TestNoGallery:
    """無 gallery → sample_images=[]"""

    def test_no_gallery_empty_list(self, scraper):
        scraper._session.get = MagicMock(return_value=make_response(NO_GALLERY_CONTENT))
        video = scraper.search("HEYZO-0783")
        assert video is not None
        assert video.sample_images == []


class TestNoSeries:
    """Series 欄位顯示 '-----' placeholder → series 應為空字串"""

    def test_series_placeholder_is_empty(self, scraper):
        scraper._session.get = MagicMock(return_value=make_response(NO_SERIES_CONTENT))
        video = scraper.search("HEYZO-0783")
        assert video is not None
        assert video.series == ""
