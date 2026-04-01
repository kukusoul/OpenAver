"""
TestExtractNumber — extract_number 和 normalize_number 單元測試
（搬自 tests/integration/test_new_scrapers.py TestExtractNumber）

純邏輯測試，不需 mock
"""
from core.scrapers.utils import extract_number
from core.scrapers.d2pass import D2PassScraper


class TestExtractNumber:
    """extract_number 和 normalize_number 單元測試"""

    def test_extract_number_underscore_3digit(self):
        """底線格式 3-digit suffix 正確提取"""
        result = extract_number("120415_201.mp4")
        assert result == "120415_201"

    def test_extract_number_underscore_2digit(self):
        """底線格式 2-digit suffix 正確提取"""
        result = extract_number("082912_01.mp4")
        assert result == "082912_01"

    def test_normalize_number_preserves_underscore(self):
        """D2PassScraper.normalize_number 不破壞底線格式番號"""
        scraper = D2PassScraper()
        result = scraper.normalize_number("120415_201")
        assert result == "120415_201"

    def test_extract_number_hyphen_2digit(self):
        """hyphen 格式 2-digit suffix 正確提取（T6b regex 修正）"""
        result = extract_number("041417-41.mp4")
        assert result == "041417-41"
