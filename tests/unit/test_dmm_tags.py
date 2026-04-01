"""
TestDMMTags — DMM Tags GraphQL probe + HTML fallback fail-open 測試
（搬自 tests/integration/test_new_scrapers.py TestDMMTags）

全 mock，不發外部 request
"""
import pytest
from unittest.mock import patch, MagicMock

from core.scrapers.dmm import DMMScraper
from core.scrapers.models import ScraperConfig


# ============================================================
# Mock Data
# ============================================================

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
# Tests
# ============================================================

class TestDMMTags:
    """DMM Tags — GraphQL probe + HTML fallback fail-open 測試"""

    @pytest.fixture
    def dmm_scraper(self, tmp_path, monkeypatch):
        """DMM scraper with isolated cache + reset _genres_supported + _sample_images_supported"""
        import core.scrapers.dmm as dmm_module
        monkeypatch.setattr(dmm_module, "CACHE_FILE", tmp_path / "dmm_content_ids.json")
        monkeypatch.setattr(dmm_module, "PREFIX_FILE", tmp_path / "dmm_prefix_hints.json")
        monkeypatch.setattr(dmm_module, "_genres_supported", None)
        monkeypatch.setattr(dmm_module, "_sample_images_supported", None)
        config = ScraperConfig(proxy_url="http://test-proxy:8080")
        return DMMScraper(config)

    def test_dmm_probe_schema_error(self, dmm_scraper, monkeypatch):
        """GraphQL schema error → _genres_supported=False（永久停用）"""
        import core.scrapers.dmm as dmm_module

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'errors': [{'message': "Unknown field 'genres' on type 'PpvContent'"}]
        }

        with patch.object(dmm_scraper._session, 'post', return_value=mock_resp):
            tags, label = dmm_scraper._probe_genres("sone00205")

        assert tags == []
        assert label == ''
        assert dmm_module._genres_supported is False

    def test_dmm_probe_schema_error_cannot_query(self, dmm_scraper, monkeypatch):
        """GraphQL 'Cannot query field' 變體 → 同樣永久停用"""
        import core.scrapers.dmm as dmm_module

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'errors': [{'message': "Cannot query field 'genres' on type 'PpvContent'"}]
        }

        with patch.object(dmm_scraper._session, 'post', return_value=mock_resp):
            tags, label = dmm_scraper._probe_genres("sone00205")

        assert tags == []
        assert label == ''
        assert dmm_module._genres_supported is False

    def test_dmm_probe_timeout_keeps_none(self, dmm_scraper, monkeypatch):
        """網路錯誤 → _genres_supported 維持 None（暫時性，可重試）"""
        import core.scrapers.dmm as dmm_module

        with patch.object(dmm_scraper._session, 'post', side_effect=Exception("connection timeout")):
            tags, label = dmm_scraper._probe_genres("sone00205")

        assert tags == []
        assert label == ''
        assert dmm_module._genres_supported is None

    def test_dmm_probe_empty_tags_sets_true(self, dmm_scraper, monkeypatch):
        """GraphQL 正常回應但 genres 為空 → _genres_supported=True（schema 支援）"""
        import core.scrapers.dmm as dmm_module

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'data': {'ppvContent': {'genres': [], 'label': None}}
        }

        with patch.object(dmm_scraper._session, 'post', return_value=mock_resp):
            tags, label = dmm_scraper._probe_genres("sone00205")

        assert tags == []
        assert label == ''
        assert dmm_module._genres_supported is True

    def test_dmm_html_fallback_error(self, dmm_scraper):
        """HTML fallback HTTP 500 → 回傳 []，不 crash"""
        mock_resp = MagicMock()
        mock_resp.status_code = 500

        with patch.object(dmm_scraper._session, 'get', return_value=mock_resp):
            tags = dmm_scraper._fetch_tags_from_html("sone00205")

        assert tags == []

    def test_dmm_both_fail_video_intact(self, dmm_scraper, monkeypatch):
        """probe + HTML 都失敗 → Video 仍完整，tags=[]"""
        detail_resp = _make_mock_resp(status_code=200, json_data=DMM_DETAIL_RESPONSE)

        with patch.object(dmm_scraper, '_probe_genres', return_value=([], '')), \
             patch.object(dmm_scraper, '_fetch_tags_from_html', return_value=[]), \
             patch.object(dmm_scraper, '_probe_sample_images', return_value=[]), \
             patch.object(dmm_scraper._session, 'post', return_value=detail_resp), \
             patch('core.scrapers.dmm.rate_limit'):
            video = dmm_scraper.search("SONE-205")

        assert video is not None
        assert video.title == "成人への卒業"
        assert video.cover_url == "https://pics.dmm.co.jp/sone205pl.jpg"
        assert video.source == 'dmm'
        assert video.tags == []

    def test_dmm_probe_cache_false_skip(self, dmm_scraper, monkeypatch):
        """_genres_supported=False → 直接跳過，不發 HTTP request"""
        import core.scrapers.dmm as dmm_module
        monkeypatch.setattr(dmm_module, '_genres_supported', False)

        with patch.object(dmm_scraper._session, 'post') as mock_post:
            tags, label = dmm_scraper._probe_genres("sone00205")

        assert tags == []
        assert label == ''
        mock_post.assert_not_called()

    def test_dmm_probe_cache_true_still_query(self, dmm_scraper, monkeypatch):
        """_genres_supported=True → 仍發 HTTP 查詢（該片可能有 tags）"""
        import core.scrapers.dmm as dmm_module
        monkeypatch.setattr(dmm_module, '_genres_supported', True)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'data': {
                'ppvContent': {
                    'genres': [{'name': '美少女'}, {'name': 'ハイビジョン'}],
                    'label': {'name': 'S1 NO.1 STYLE'}
                }
            }
        }

        with patch.object(dmm_scraper._session, 'post', return_value=mock_resp) as mock_post:
            tags, label = dmm_scraper._probe_genres("sone00205")

        mock_post.assert_called_once()
        assert tags == ['美少女', 'ハイビジョン']
        assert label == 'S1 NO.1 STYLE'
        assert dmm_module._genres_supported is True

    def test_sample_images_probe_schema_error(self, dmm_scraper, monkeypatch):
        """sampleImages schema error (HTTP 200) → 永久停用 sampleImages，但 genres 不受影響"""
        import core.scrapers.dmm as dmm_module
        monkeypatch.setattr(dmm_module, '_sample_images_supported', None)
        monkeypatch.setattr(dmm_module, '_genres_supported', True)

        # GraphQL schema errors come as HTTP 200 with errors in the body
        error_resp = _make_mock_resp(status_code=200, json_data={
            "errors": [{"message": "Cannot query field 'sampleImages' on type 'PPVContent'."}],
            "data": None
        })
        with patch.object(dmm_scraper._session, 'post', return_value=error_resp):
            result = dmm_scraper._probe_sample_images("sone00205")

        assert result == []
        assert dmm_module._sample_images_supported is False
        # genres should still be True (unaffected)
        assert dmm_module._genres_supported is True

    def test_sample_images_probe_success(self, dmm_scraper, monkeypatch):
        """sampleImages probe 成功 → 回傳圖片列表"""
        import core.scrapers.dmm as dmm_module
        monkeypatch.setattr(dmm_module, '_sample_images_supported', None)

        success_resp = _make_mock_resp(status_code=200, json_data={
            "data": {"ppvContent": {"sampleImages": [
                {"imageUrl": "https://a.jpg"},
                {"imageUrl": "https://b.jpg"}
            ]}}
        })
        with patch.object(dmm_scraper._session, 'post', return_value=success_resp):
            result = dmm_scraper._probe_sample_images("sone00205")

        assert result == ["https://a.jpg", "https://b.jpg"]
        assert dmm_module._sample_images_supported is True

    def test_sample_images_probe_high_res_url(self, dmm_scraper, monkeypatch):
        """sampleImages URL 轉換為高解析度版本（-N.jpg → jp-N.jpg）"""
        import core.scrapers.dmm as dmm_module
        monkeypatch.setattr(dmm_module, '_sample_images_supported', None)

        success_resp = _make_mock_resp(status_code=200, json_data={
            "data": {"ppvContent": {"sampleImages": [
                {"imageUrl": "https://pics.dmm.co.jp/digital/video/ipzz00698/ipzz00698-1.jpg"},
                {"imageUrl": "https://pics.dmm.co.jp/digital/video/ipzz00698/ipzz00698-10.jpg"},
            ]}}
        })
        with patch.object(dmm_scraper._session, 'post', return_value=success_resp):
            result = dmm_scraper._probe_sample_images("ipzz00698")

        assert result == [
            "https://pics.dmm.co.jp/digital/video/ipzz00698/ipzz00698jp-1.jpg",
            "https://pics.dmm.co.jp/digital/video/ipzz00698/ipzz00698jp-10.jpg",
        ]

    def test_sample_images_probe_non_jpg_preserved(self, dmm_scraper, monkeypatch):
        """非 -N.jpg 格式的 URL 原樣保留"""
        import core.scrapers.dmm as dmm_module
        monkeypatch.setattr(dmm_module, '_sample_images_supported', None)

        success_resp = _make_mock_resp(status_code=200, json_data={
            "data": {"ppvContent": {"sampleImages": [
                {"imageUrl": "https://example.com/sample.png"},
            ]}}
        })
        with patch.object(dmm_scraper._session, 'post', return_value=success_resp):
            result = dmm_scraper._probe_sample_images("test001")

        assert result == ["https://example.com/sample.png"]

    def test_sample_images_probe_already_high_res_idempotent(self, dmm_scraper, monkeypatch):
        """已是高解析度 jp-N.jpg → 不重複轉換（冪等性）"""
        import core.scrapers.dmm as dmm_module
        monkeypatch.setattr(dmm_module, '_sample_images_supported', None)

        success_resp = _make_mock_resp(status_code=200, json_data={
            "data": {"ppvContent": {"sampleImages": [
                {"imageUrl": "https://pics.dmm.co.jp/digital/video/ipzz00698/ipzz00698jp-1.jpg"},
            ]}}
        })
        with patch.object(dmm_scraper._session, 'post', return_value=success_resp):
            result = dmm_scraper._probe_sample_images("ipzz00698")

        # Should NOT become ipzz00698jpjp-1.jpg
        assert result == ["https://pics.dmm.co.jp/digital/video/ipzz00698/ipzz00698jp-1.jpg"]

    def test_sample_images_probe_cache_false_skip(self, dmm_scraper, monkeypatch):
        """_sample_images_supported=False → 不發請求"""
        import core.scrapers.dmm as dmm_module
        monkeypatch.setattr(dmm_module, '_sample_images_supported', False)

        with patch.object(dmm_scraper._session, 'post') as mock_post:
            result = dmm_scraper._probe_sample_images("sone00205")

        assert result == []
        mock_post.assert_not_called()
