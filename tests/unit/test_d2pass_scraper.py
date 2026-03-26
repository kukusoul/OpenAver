"""
test_d2pass_scraper.py - D2Pass 爬蟲單元測試（TASK-36-T9）

測試策略：
- 全 mock，不連網
- Mock scraper._session.get 回傳 JSON
- rate_limit 也 mock 掉（避免 sleep）
"""

import json
import pytest
from unittest.mock import patch, MagicMock


# ============================================================
# JSON Fixtures
# ============================================================

FULL_FIELDS_JSON = {
    "Status": True,
    "Title": "テストタイトル",
    "TitleEn": "Test Title",
    "ActressesJa": ["テスト女優"],
    "ActressesEn": ["Test Actress"],
    "ActressesList": {},
    "ThumbHigh": "https://www.1pondo.tv/assets/sample/120415_201/str.jpg",
    "MovieThumb": "",
    "UCNAME": ["フェラ", "ハメ撮り"],
    "UCNAMEEn": [],
    "Release": "2023-04-15",
    "AvgRating": "4.5",
    "Series": "テストシリーズ",
    "Duration": 3661,
    "SampleImages": [
        "https://www.1pondo.tv/assets/sample/120415_201/gallery/001.jpg",
        "https://www.1pondo.tv/assets/sample/120415_201/gallery/002.jpg",
    ],
}

NO_EXTRA_FIELDS_JSON = {
    "Status": True,
    "Title": "テストタイトル",
    "TitleEn": "Test Title",
    "ActressesJa": ["テスト女優"],
    "ActressesEn": [],
    "ActressesList": {},
    "ThumbHigh": "https://www.1pondo.tv/assets/sample/120415_201/str.jpg",
    "MovieThumb": "",
    "UCNAME": ["フェラ"],
    "UCNAMEEn": [],
    "Release": "2023-04-15",
    "AvgRating": None,
    # No Series, Duration, SampleImages keys
}

SERIES_EN_ONLY_JSON = {
    "Status": True,
    "Title": "テストタイトル",
    "TitleEn": "Test Title",
    "ActressesJa": ["テスト女優"],
    "ActressesEn": ["Test Actress"],
    "ActressesList": {},
    "ThumbHigh": "https://www.1pondo.tv/assets/sample/120415_201/str.jpg",
    "MovieThumb": "",
    "UCNAME": [],
    "UCNAMEEn": [],
    "Release": "2023-04-15",
    "AvgRating": None,
    "SeriesEn": "Test Series En",  # Only SeriesEn; no Series or SeriesJa
    "Duration": 3661,
    "SampleImages": [],
}

DURATION_STRING_JSON = {
    "Status": True,
    "Title": "テストタイトル",
    "ActressesJa": ["テスト女優"],
    "ActressesEn": [],
    "ActressesList": {},
    "ThumbHigh": "https://www.1pondo.tv/assets/sample/120415_201/str.jpg",
    "MovieThumb": "",
    "UCNAME": [],
    "UCNAMEEn": [],
    "Release": "2023-04-15",
    "AvgRating": None,
    "Series": "",
    "Duration": "3661",  # Duration as string
    "SampleImages": None,  # null in JSON
}


# ============================================================
# Helpers
# ============================================================

def make_json_response(data: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    return resp


def run_search(scraper, json_data: dict, number: str = "120415_201"):
    scraper._session.get = MagicMock(return_value=make_json_response(json_data))
    return scraper.search(number)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def scraper():
    from core.scrapers.d2pass import D2PassScraper
    with patch("core.scrapers.d2pass.rate_limit"):
        s = D2PassScraper()
        yield s


# ============================================================
# Tests
# ============================================================

class TestFullFields:
    """happy path: JSON has Series/Duration/SampleImages"""

    def test_series(self, scraper):
        video = run_search(scraper, FULL_FIELDS_JSON)
        assert video is not None
        assert video.series == "テストシリーズ"

    def test_duration_seconds_to_minutes(self, scraper):
        """3661 秒 → 61 分鐘（3661 // 60）"""
        video = run_search(scraper, FULL_FIELDS_JSON)
        assert video is not None
        assert video.duration == 61
        assert isinstance(video.duration, int)

    def test_sample_images(self, scraper):
        video = run_search(scraper, FULL_FIELDS_JSON)
        assert video is not None
        assert len(video.sample_images) == 2
        assert all(url.startswith("https://") for url in video.sample_images)


class TestNoExtraFields:
    """JSON 無 Series/Duration/SampleImages → 預設值"""

    def test_series_empty(self, scraper):
        video = run_search(scraper, NO_EXTRA_FIELDS_JSON)
        assert video is not None
        assert video.series == ""

    def test_duration_none(self, scraper):
        video = run_search(scraper, NO_EXTRA_FIELDS_JSON)
        assert video is not None
        assert video.duration is None

    def test_sample_images_empty(self, scraper):
        video = run_search(scraper, NO_EXTRA_FIELDS_JSON)
        assert video is not None
        assert video.sample_images == []


class TestDurationString:
    """Duration 為字串 → 正確轉換；SampleImages 為 null → []"""

    def test_duration_string_to_int(self, scraper):
        video = run_search(scraper, DURATION_STRING_JSON)
        assert video is not None
        assert video.duration == 61

    def test_sample_images_null_to_empty(self, scraper):
        video = run_search(scraper, DURATION_STRING_JSON)
        assert video is not None
        assert video.sample_images == []


class TestSeriesEnOnly:
    """JSON 只有 SeriesEn（無 Series/SeriesJa）→ series 正確讀取"""

    def test_series_en_fallback(self, scraper):
        video = run_search(scraper, SERIES_EN_ONLY_JSON)
        assert video is not None
        assert video.series == "Test Series En"
