"""
tests/integration/test_clip_api.py
TDD-lite integration tests for GET /api/similar-covers endpoint.
Uses FastAPI TestClient + mock provider + mock VideoRepository.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helper: build a minimal mock provider
# ---------------------------------------------------------------------------

def _make_provider(
    is_enabled: bool = True,
    model_available: bool = True,
    session_loaded: bool = True,
    model_id: str = "clip-vit-b32-int8-xenova-v1",
    compute_similar_result: list | None = None,
):
    provider = MagicMock()
    provider.is_enabled = is_enabled
    provider.model_available = model_available
    provider.session_loaded = session_loaded
    provider.model_id = model_id
    if compute_similar_result is None:
        compute_similar_result = []
    provider.compute_similar = AsyncMock(return_value=compute_similar_result)
    return provider


# ---------------------------------------------------------------------------
# Helper: build a minimal mock Video
# ---------------------------------------------------------------------------

def _make_video(
    video_id: int = 1,
    number: str = "ABC-001",
    title: str = "Test Video",
    cover_path: str = "file:///test/cover.jpg",
    actresses: list | None = None,
    clip_embedding: bytes | None = b"\x00" * 2048,
    clip_model_id: str | None = "clip-vit-b32-int8-xenova-v1",
):
    video = MagicMock()
    video.id = video_id
    video.number = number
    video.title = title
    video.cover_path = cover_path
    video.actresses = actresses or []
    video.clip_embedding = clip_embedding
    video.clip_model_id = clip_model_id
    return video


# ---------------------------------------------------------------------------
# App fixture — import app after setting up mocks
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Return a TestClient for the FastAPI app."""
    from web.app import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSimilarCoversAPI:
    def test_get_similar_covers_200(self, client):
        """200 正常 case：provider 有 matrix，query video 有 embedding，回傳 results"""
        target_video = _make_video(video_id=1, actresses=["Alice"])
        result_video = _make_video(video_id=2, number="XYZ-002", actresses=["Bob"])

        provider = _make_provider(
            compute_similar_result=[{"video_id": 2, "cosine_score": 0.85}],
        )

        def mock_get_by_id(vid):
            return {1: target_video, 2: result_video}.get(vid)

        with (
            patch("web.routers.clip.get_provider", return_value=provider),
            patch("web.routers.clip.VideoRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_id.side_effect = mock_get_by_id

            resp = client.get("/api/similar-covers/1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["video_id"] == 1
        assert data["model_id"] == "clip-vit-b32-int8-xenova-v1"
        assert isinstance(data["results"], list)

    def test_get_similar_covers_503_not_enabled(self, client):
        """503：is_enabled == False"""
        provider = _make_provider(is_enabled=False)

        with patch("web.routers.clip.get_provider", return_value=provider):
            resp = client.get("/api/similar-covers/1")

        assert resp.status_code == 503
        assert resp.json()["detail"] == "CLIP 索引尚未準備好"

    def test_get_similar_covers_404_no_embedding(self, client):
        """404：query video clip_embedding IS NULL"""
        target_video = _make_video(video_id=1, clip_embedding=None, clip_model_id=None)
        provider = _make_provider()

        with (
            patch("web.routers.clip.get_provider", return_value=provider),
            patch("web.routers.clip.VideoRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_id.return_value = target_video

            resp = client.get("/api/similar-covers/1")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "找不到影片或尚未建立索引"

    def test_get_similar_covers_404_video_not_found(self, client):
        """404：video_id 不存在於 DB"""
        provider = _make_provider()

        with (
            patch("web.routers.clip.get_provider", return_value=provider),
            patch("web.routers.clip.VideoRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_id.return_value = None

            resp = client.get("/api/similar-covers/9999")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "找不到影片或尚未建立索引"

    def test_get_similar_covers_422_model_mismatch(self, client):
        """422：query video clip_model_id 與 provider.model_id 不一致"""
        target_video = _make_video(
            video_id=1,
            clip_embedding=b"\x00" * 2048,
            clip_model_id="old-model-v0",  # 不一致
        )
        provider = _make_provider(model_id="clip-vit-b32-int8-xenova-v1")

        with (
            patch("web.routers.clip.get_provider", return_value=provider),
            patch("web.routers.clip.VideoRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_id.return_value = target_video

            resp = client.get("/api/similar-covers/1")

        assert resp.status_code == 422
        assert resp.json()["detail"] == "CLIP 索引模型不一致，請至設定重建索引"

    def test_similar_covers_200_when_session_not_loaded(self, client):
        """防回歸 P2-1：session_loaded=False + model_available=True → 仍回 200"""
        target_video = _make_video(video_id=1, actresses=["Alice"])
        provider = _make_provider(
            session_loaded=False,  # session 未載入
            model_available=True,
            compute_similar_result=[],
        )

        with (
            patch("web.routers.clip.get_provider", return_value=provider),
            patch("web.routers.clip.VideoRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_id.return_value = target_video

            resp = client.get("/api/similar-covers/1")

        assert resp.status_code == 200, (
            "P2-1 防回歸：session_loaded=False 不應阻止相似查詢（相似查詢不需要 ONNX session）"
        )

    def test_diversity_penalty_applied(self, client):
        """diversity penalty applied：同女優候選 penalty_applied=True，cosine_score < raw score"""
        target_video = _make_video(video_id=1, actresses=["Alice"])
        same_actress_video = _make_video(video_id=2, actresses=["Alice", "Bob"])

        raw_score = 0.9
        provider = _make_provider(
            compute_similar_result=[{"video_id": 2, "cosine_score": raw_score}],
        )

        def mock_get_by_id(vid):
            return {1: target_video, 2: same_actress_video}.get(vid)

        with (
            patch("web.routers.clip.get_provider", return_value=provider),
            patch("web.routers.clip.VideoRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_id.side_effect = mock_get_by_id

            resp = client.get("/api/similar-covers/1")

        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) == 1
        r = results[0]
        assert r["penalty_applied"] is True
        assert r["cosine_score"] < raw_score

    def test_by_number_200(self, client):
        """by-number 端點 200：番號存在且有 embedding"""
        target_video = _make_video(video_id=5, number="ABC-005", actresses=["Carol"])
        provider = _make_provider(compute_similar_result=[])

        with (
            patch("web.routers.clip.get_provider", return_value=provider),
            patch("web.routers.clip.VideoRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_number.return_value = target_video
            MockRepo.return_value.get_by_id.return_value = target_video

            resp = client.get("/api/similar-covers/by-number/ABC-005")

        assert resp.status_code == 200
        data = resp.json()
        assert data["video_id"] == 5

    def test_by_number_404(self, client):
        """by-number 端點 404：番號不存在"""
        provider = _make_provider()

        with (
            patch("web.routers.clip.get_provider", return_value=provider),
            patch("web.routers.clip.VideoRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_number.return_value = None

            resp = client.get("/api/similar-covers/by-number/NONEXIST-999")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "找不到影片或尚未建立索引"

    def test_limit_parameter_respected(self, client):
        """limit 參數傳遞給 compute_similar"""
        target_video = _make_video(video_id=1)
        provider = _make_provider(compute_similar_result=[])

        with (
            patch("web.routers.clip.get_provider", return_value=provider),
            patch("web.routers.clip.VideoRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_id.return_value = target_video

            resp = client.get("/api/similar-covers/1?limit=5")

        assert resp.status_code == 200
        # Verify compute_similar was called with limit=5
        provider.compute_similar.assert_awaited_once()
        call_kwargs = provider.compute_similar.call_args
        # limit may be positional or keyword
        called_limit = (
            call_kwargs.kwargs.get("limit")
            if "limit" in call_kwargs.kwargs
            else call_kwargs.args[1] if len(call_kwargs.args) > 1 else None
        )
        assert called_limit == 5

    def test_limit_over_50_returns_422(self, client):
        """limit > 50 → FastAPI Query validation → 422"""
        provider = _make_provider()

        with patch("web.routers.clip.get_provider", return_value=provider):
            resp = client.get("/api/similar-covers/1?limit=51")

        assert resp.status_code == 422

    def test_model_available_false_returns_empty_results(self, client):
        """model_available=False（DB 無索引）→ 200 + results: []（不是 error）"""
        target_video = _make_video(video_id=1)
        provider = _make_provider(model_available=False, compute_similar_result=[])

        with (
            patch("web.routers.clip.get_provider", return_value=provider),
            patch("web.routers.clip.VideoRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_id.return_value = target_video

            resp = client.get("/api/similar-covers/1")

        assert resp.status_code == 200
        assert resp.json()["results"] == []


# ---------------------------------------------------------------------------
# 56c-T1: response shape — query_video + cover_url
# ---------------------------------------------------------------------------

class TestSimilarCoversResponseShape:
    """56c-T1 contract: response 增補 query_video（頂層中央主圖 metadata）
    與 cover_url（每筆 result）。前端零 path 邏輯。
    """

    def test_query_video_present(self, client):
        """response.query_video 含 video_id / number / title / cover_url 4 欄位"""
        target_video = _make_video(
            video_id=1,
            number="ABC-001",
            title="Test Video",
            cover_path="file:///test/cover.jpg",
            actresses=["Alice"],
        )
        result_video = _make_video(video_id=2, number="XYZ-002", actresses=["Bob"])
        provider = _make_provider(
            compute_similar_result=[{"video_id": 2, "cosine_score": 0.85}],
        )

        def mock_get_by_id(vid):
            return {1: target_video, 2: result_video}.get(vid)

        with (
            patch("web.routers.clip.get_provider", return_value=provider),
            patch("web.routers.clip.VideoRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_id.side_effect = mock_get_by_id
            resp = client.get("/api/similar-covers/1")

        assert resp.status_code == 200
        data = resp.json()
        assert "query_video" in data
        qv = data["query_video"]
        assert qv["video_id"] == 1
        assert qv["number"] == "ABC-001"
        assert qv["title"] == "Test Video"
        assert "cover_url" in qv
        assert isinstance(qv["cover_url"], str)

    def test_cover_url_form(self, client):
        """query_video.cover_url 與 results[i].cover_url 皆以 /api/gallery/image?path= 開頭，URL-encoded"""
        # cover_path 含特殊字元（空白 + 中文），驗 URL-encode safe=''
        target_video = _make_video(
            video_id=1,
            number="ABC-001",
            cover_path="file:///media/影片 庫/cover one.jpg",
            actresses=["Alice"],
        )
        result_video = _make_video(
            video_id=2,
            number="XYZ-002",
            cover_path="file:///media/影片 庫/cover two.jpg",
            actresses=["Bob"],
        )
        provider = _make_provider(
            compute_similar_result=[{"video_id": 2, "cosine_score": 0.85}],
        )

        def mock_get_by_id(vid):
            return {1: target_video, 2: result_video}.get(vid)

        with (
            patch("web.routers.clip.get_provider", return_value=provider),
            patch("web.routers.clip.VideoRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_id.side_effect = mock_get_by_id
            resp = client.get("/api/similar-covers/1")

        assert resp.status_code == 200
        data = resp.json()

        # query_video.cover_url
        qv_url = data["query_video"]["cover_url"]
        assert qv_url.startswith("/api/gallery/image?path=")
        # safe='' 表示空白與中文都需要 encode → encoded 結果不應含 raw 空白或 raw 中文
        qs = qv_url.split("path=", 1)[1]
        assert " " not in qs  # 原始空白被 encoded 為 %20
        assert "影" not in qs  # 原始中文被 encoded

        # results[i].cover_url
        results = data["results"]
        assert len(results) == 1
        r_url = results[0]["cover_url"]
        assert r_url.startswith("/api/gallery/image?path=")
        r_qs = r_url.split("path=", 1)[1]
        assert " " not in r_qs
        assert "影" not in r_qs

    def test_results_count_12(self, client):
        """預設不帶 limit 時，傳給 provider.compute_similar 的 limit=12"""
        target_video = _make_video(video_id=1)
        provider = _make_provider(compute_similar_result=[])

        with (
            patch("web.routers.clip.get_provider", return_value=provider),
            patch("web.routers.clip.VideoRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_id.return_value = target_video
            resp = client.get("/api/similar-covers/1")

        assert resp.status_code == 200
        provider.compute_similar.assert_awaited_once()
        call_kwargs = provider.compute_similar.call_args
        called_limit = (
            call_kwargs.kwargs.get("limit")
            if "limit" in call_kwargs.kwargs
            else call_kwargs.args[1] if len(call_kwargs.args) > 1 else None
        )
        assert called_limit == 12

    def test_each_result_has_cover_url(self, client):
        """results 非空時每筆都含 cover_url 欄位（form 同 #2）"""
        target_video = _make_video(video_id=1, actresses=["Alice"])
        v2 = _make_video(video_id=2, number="V2", cover_path="file:///a/b/v2.jpg", actresses=["B"])
        v3 = _make_video(video_id=3, number="V3", cover_path="file:///a/b/v3.jpg", actresses=["C"])
        provider = _make_provider(
            compute_similar_result=[
                {"video_id": 2, "cosine_score": 0.85},
                {"video_id": 3, "cosine_score": 0.80},
            ],
        )

        def mock_get_by_id(vid):
            return {1: target_video, 2: v2, 3: v3}.get(vid)

        with (
            patch("web.routers.clip.get_provider", return_value=provider),
            patch("web.routers.clip.VideoRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_id.side_effect = mock_get_by_id
            resp = client.get("/api/similar-covers/1")

        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) == 2
        for item in results:
            assert "cover_url" in item
            assert item["cover_url"].startswith("/api/gallery/image?path=")

    def test_cover_path_still_present(self, client):
        """向後相容：results[i].cover_path 仍存在 = DB file:/// URI"""
        target_video = _make_video(video_id=1, actresses=["Alice"])
        result_video = _make_video(
            video_id=2,
            number="XYZ-002",
            cover_path="file:///test/result-cover.jpg",
            actresses=["Bob"],
        )
        provider = _make_provider(
            compute_similar_result=[{"video_id": 2, "cosine_score": 0.85}],
        )

        def mock_get_by_id(vid):
            return {1: target_video, 2: result_video}.get(vid)

        with (
            patch("web.routers.clip.get_provider", return_value=provider),
            patch("web.routers.clip.VideoRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_id.side_effect = mock_get_by_id
            resp = client.get("/api/similar-covers/1")

        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) == 1
        # cover_path 必須仍存在，且為 DB 原 file:/// URI
        assert results[0]["cover_path"] == "file:///test/result-cover.jpg"


# ---------------------------------------------------------------------------
# 56c-T5: cover_url 可 GET 200（query_video + results[0]）
# ---------------------------------------------------------------------------

class TestCoverUrlFetchable:
    """56c-T5 guard：query_video.cover_url 與 results[0].cover_url 皆為合法 /api/gallery/image 路徑，
    格式與既有 TestSimilarCoversResponseShape 一致（/api/gallery/image?path= 開頭）。
    本 class 確認 by-number 端點也回傳正確 cover_url 格式（前端 _fetchClipResults 呼叫路徑）。
    """

    def test_by_number_query_video_cover_url_fetchable(self, client):
        """by-number 端點 query_video.cover_url 以 /api/gallery/image?path= 開頭"""
        target_video = _make_video(
            video_id=5,
            number="ABC-005",
            cover_path="file:///media/covers/abc005.jpg",
            actresses=["Carol"],
        )
        provider = _make_provider(compute_similar_result=[])

        with (
            patch("web.routers.clip.get_provider", return_value=provider),
            patch("web.routers.clip.VideoRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_number.return_value = target_video
            MockRepo.return_value.get_by_id.return_value = target_video

            resp = client.get("/api/similar-covers/by-number/ABC-005")

        assert resp.status_code == 200
        data = resp.json()
        assert "query_video" in data
        qv_url = data["query_video"]["cover_url"]
        assert qv_url.startswith("/api/gallery/image?path="), (
            f"query_video.cover_url 應以 /api/gallery/image?path= 開頭，實際：{qv_url!r}"
        )

    def test_by_number_results_cover_url_fetchable(self, client):
        """by-number 端點 results[0].cover_url 以 /api/gallery/image?path= 開頭"""
        target_video = _make_video(
            video_id=5,
            number="ABC-005",
            cover_path="file:///media/covers/abc005.jpg",
            actresses=["Carol"],
        )
        result_video = _make_video(
            video_id=6,
            number="XYZ-006",
            cover_path="file:///media/covers/xyz006.jpg",
            actresses=["Dana"],
        )
        provider = _make_provider(
            compute_similar_result=[{"video_id": 6, "cosine_score": 0.80}],
        )

        def mock_get_by_id(vid):
            return {5: target_video, 6: result_video}.get(vid)

        with (
            patch("web.routers.clip.get_provider", return_value=provider),
            patch("web.routers.clip.VideoRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_number.return_value = target_video
            MockRepo.return_value.get_by_id.side_effect = mock_get_by_id

            resp = client.get("/api/similar-covers/by-number/ABC-005")

        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) == 1
        r_url = results[0]["cover_url"]
        assert r_url.startswith("/api/gallery/image?path="), (
            f"results[0].cover_url 應以 /api/gallery/image?path= 開頭，實際：{r_url!r}"
        )
