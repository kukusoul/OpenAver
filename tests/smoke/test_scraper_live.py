"""
test_scraper_live.py - 爬蟲連通 Smoke Tests

Phase 16 Task 2: 測試 5 個爬蟲的網路連通性

執行方式：
    pytest tests/smoke/test_scraper_live.py -v -m smoke

注意：
- 只用於本地手動測試，不進 CI（避免被 ban）
- 無法連線時自動 skip，不算失敗
"""

import pytest
from core.scraper import search_jav


# ========== 舊 API 連通測試 ==========

@pytest.mark.smoke
class TestOldAPIConnectivity:
    """舊 API 連通測試（search_jav）"""

    def test_auto_source_connectivity(self):
        """自動來源連通性測試（至少一個來源可用）"""
        result = search_jav("MIDV-139", source="auto")
        if result is None:
            pytest.skip("所有爬蟲來源無法連線（可能被網站封鎖或網路問題）")

        assert result.get('number'), "無番號返回"
        assert result.get('title') not in (None, ""), \
            f"標題為空或 None，實際值: {result.get('title')!r}"
        # search_jav 透過 to_legacy_dict() 回傳，女優欄位名稱為 'actors'（字串列表）
        actors = result.get('actors', [])
        assert isinstance(actors, list), \
            f"'actors' 欄位應為 list，實際型別: {type(actors).__name__}"


# ========== 女優搜尋測試 ==========

@pytest.mark.smoke
class TestActressSearch:
    """女優搜尋連通測試"""

    def test_actress_search_connectivity(self):
        """女優搜尋連通性"""
        from core.scraper import search_actress

        results = search_actress("三上悠亞", limit=5)
        if not results:
            pytest.skip("女優搜尋無法連線（可能被網站封鎖）")

        assert len(results) >= 1, "至少應返回 1 個結果"
        assert results[0].get('number'), "結果應包含番號"


# ========== 特殊番號測試 ==========

@pytest.mark.smoke
class TestSpecialNumbers:
    """特殊番號格式測試"""

    @pytest.mark.parametrize("number,desc", [
        ("FC2-PPV-2200414", "fc2"),
        ("FC2-PPV-2781063", "fc2"),
        ("FC2-PPV-2865434", "fc2"),
        ("010120-001", "1pondo"),
        ("031515-828", "carib"),
    ])
    def test_uncensored_smart_search(self, number, desc):
        """無碼番號 smart_search 觸發測試"""
        from core.scraper import smart_search

        results = smart_search(number, limit=1)
        if not results:
            pytest.skip(f"{number} ({desc}) 無法搜尋到結果")
        assert results[0].get('_mode') == 'uncensored', \
            f"{number} ({desc}) 應為 uncensored 模式，實際: {results[0].get('_mode')}"

