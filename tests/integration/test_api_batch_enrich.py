"""
test_api_batch_enrich.py - POST /api/batch-enrich 端點整合測試（SSE Streaming）

使用 FastAPI TestClient + mocker，mock web.routers.scraper.enrich_single（使用端）。
"""

import json
import pytest
from unittest.mock import patch, MagicMock


# ── helper ───────────────────────────────────────────────────────────────────

def parse_sse(text: str) -> list:
    """解析 SSE 文字，回傳事件 dict 列表"""
    events = []
    for line in text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def _ok_result(**kwargs):
    """建立成功的 EnrichResult mock 物件"""
    from core.enricher import EnrichResult
    defaults = dict(
        success=True,
        nfo_written=True,
        cover_written=True,
        extrafanart_written=0,
        fields_filled=[],
        source_used="javbus",
        error=None,
    )
    defaults.update(kwargs)
    return EnrichResult(**defaults)


def _err_result(error: str):
    """建立失敗的 EnrichResult mock 物件"""
    from core.enricher import EnrichResult
    return EnrichResult(
        success=False,
        nfo_written=False,
        cover_written=False,
        extrafanart_written=0,
        fields_filled=[],
        source_used="",
        error=error,
    )


# ── tests ────────────────────────────────────────────────────────────────────

class TestBatchEnrich:

    def test_batch_single_item_sse_events(self, client, mocker):
        """1 筆成功：progress + result-item(success=True) + done 事件順序正確"""
        mocker.patch(
            "web.routers.scraper.enrich_single",
            return_value=_ok_result(),
        )

        response = client.post("/api/batch-enrich", json={
            "items": [{"file_path": "/video/IPZ-154.mp4", "number": "IPZ-154"}],
            "mode": "refresh_full",
        })

        assert response.status_code == 200
        events = parse_sse(response.text)

        # 應有 3 個事件：progress, result-item, done
        assert len(events) == 3

        # 第一個事件：progress
        assert events[0]["type"] == "progress"
        assert events[0]["current"] == 1
        assert events[0]["total"] == 1
        assert events[0]["number"] == "IPZ-154"

        # 第二個事件：result-item，success=True
        assert events[1]["type"] == "result-item"
        assert events[1]["number"] == "IPZ-154"
        assert events[1]["file_path"] == "/video/IPZ-154.mp4"
        assert events[1]["success"] is True

        # 第三個事件：done
        assert events[2]["type"] == "done"
        assert events[2]["summary"]["total"] == 1
        assert events[2]["summary"]["success"] == 1
        assert events[2]["summary"]["failed"] == 0

    def test_batch_done_summary_counts(self, client, mocker):
        """2 筆，1 成功 1 失敗：done.summary.success/failed 正確計數"""
        mocker.patch(
            "web.routers.scraper.enrich_single",
            side_effect=[
                _ok_result(),
                _err_result("檔案不存在"),
            ],
        )

        response = client.post("/api/batch-enrich", json={
            "items": [
                {"file_path": "/video/IPZ-154.mp4", "number": "IPZ-154"},
                {"file_path": "/video/SONE-205.mp4", "number": "SONE-205"},
            ],
            "mode": "refresh_full",
        })

        assert response.status_code == 200
        events = parse_sse(response.text)

        # 取得 done 事件
        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1

        summary = done_events[0]["summary"]
        assert summary["total"] == 2
        assert summary["success"] == 1
        assert summary["failed"] == 1

    def test_batch_empty_items_returns_done(self, client, mocker):
        """空 items → 直接 done，summary 全 0"""
        mock_enrich = mocker.patch(
            "web.routers.scraper.enrich_single",
            return_value=_ok_result(),
        )

        response = client.post("/api/batch-enrich", json={
            "items": [],
            "mode": "refresh_full",
        })

        assert response.status_code == 200
        events = parse_sse(response.text)

        # 不呼叫 enrich_single
        mock_enrich.assert_not_called()

        # 只有 done 事件
        assert len(events) == 1
        assert events[0]["type"] == "done"
        assert events[0]["summary"]["total"] == 0
        assert events[0]["summary"]["success"] == 0
        assert events[0]["summary"]["failed"] == 0

    def test_batch_over_limit_returns_422(self, client, mocker):
        """21 筆 → HTTP 422"""
        mocker.patch(
            "web.routers.scraper.enrich_single",
            return_value=_ok_result(),
        )

        items = [
            {"file_path": f"/video/IPZ-{i:03d}.mp4", "number": f"IPZ-{i:03d}"}
            for i in range(21)
        ]

        response = client.post("/api/batch-enrich", json={
            "items": items,
            "mode": "refresh_full",
        })

        assert response.status_code == 422

    def test_batch_duplicate_path_deduped(self, client, mocker):
        """同 file_path 兩筆 → enrich_single 只呼叫 1 次"""
        mock_enrich = mocker.patch(
            "web.routers.scraper.enrich_single",
            return_value=_ok_result(),
        )

        response = client.post("/api/batch-enrich", json={
            "items": [
                {"file_path": "/video/IPZ-154.mp4", "number": "IPZ-154"},
                {"file_path": "/video/IPZ-154.mp4", "number": "IPZ-154"},  # 重複
            ],
            "mode": "refresh_full",
        })

        assert response.status_code == 200

        # enrich_single 只被呼叫 1 次
        assert mock_enrich.call_count == 1

        events = parse_sse(response.text)
        done_events = [e for e in events if e["type"] == "done"]
        # total 只計去重後的數量
        assert done_events[0]["summary"]["total"] == 1

    def test_batch_enrich_failure_continues(self, client, mocker):
        """第 1 筆 enrich_single 回傳 error → result-item success=False，第 2 筆仍正常處理"""
        mocker.patch(
            "web.routers.scraper.enrich_single",
            side_effect=[
                _err_result("找不到番號資料"),
                _ok_result(),
            ],
        )

        response = client.post("/api/batch-enrich", json={
            "items": [
                {"file_path": "/video/XXX-999.mp4", "number": "XXX-999"},
                {"file_path": "/video/SONE-205.mp4", "number": "SONE-205"},
            ],
            "mode": "refresh_full",
        })

        assert response.status_code == 200
        events = parse_sse(response.text)

        result_items = [e for e in events if e["type"] == "result-item"]
        assert len(result_items) == 2

        # 第 1 筆失敗
        assert result_items[0]["success"] is False
        assert result_items[0]["number"] == "XXX-999"

        # 第 2 筆成功
        assert result_items[1]["success"] is True
        assert result_items[1]["number"] == "SONE-205"

        # done summary 正確計數
        done_events = [e for e in events if e["type"] == "done"]
        assert done_events[0]["summary"]["success"] == 1
        assert done_events[0]["summary"]["failed"] == 1

    def test_batch_content_type_is_event_stream(self, client, mocker):
        """response.headers['content-type'] 含 'text/event-stream'"""
        mocker.patch(
            "web.routers.scraper.enrich_single",
            return_value=_ok_result(),
        )

        response = client.post("/api/batch-enrich", json={
            "items": [{"file_path": "/video/IPZ-154.mp4", "number": "IPZ-154"}],
            "mode": "refresh_full",
        })

        assert "text/event-stream" in response.headers.get("content-type", "")
