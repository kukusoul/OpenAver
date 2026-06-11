"""test_api_thumb.py - 縮圖快取 API 整合測試（feature/71 T3）

涵蓋 TASK-71-T3 邊界 1-9：
- GET /api/gallery/thumb：hit serve webp + no-cache + 強 ETag；If-None-Match → 304；
  hit 零 DB/零 NAS；miss 生成；無 cover 404；generate 失敗 fallback 原圖。
- POST /api/gallery/thumb/prewarm：disabled gate / started / already_running 重入。

隔離關鍵：thumbnail_cache._thumb_dir 與 scanner.get_db_path 是兩個獨立 reference，
兩者都要 patch（見 TASK card 測試隔離坑）。
"""
import pytest
from pathlib import Path
from urllib.parse import quote

from PIL import Image

from core.path_utils import to_file_uri, uri_to_fs_path
from core import thumbnail_cache


# ---------- helpers ----------

def _make_small_jpg(path: Path, size=(800, 600)):
    """產生一張真 JPG 小圖（用於 cover 來源）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (120, 60, 200)).save(path, "JPEG")
    return path


def _make_webp(path: Path, size=(400, 300)):
    """直接放一張真 webp 到 thumb 位置（用於 hit 測試）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (10, 200, 100)).save(path, "WEBP")
    return path


@pytest.fixture
def thumb_dir(tmp_path, mocker):
    """把 thumbnail_cache._thumb_dir 導向 temp，避免污染真 output/thumb。"""
    d = tmp_path / "thumb"
    d.mkdir()
    mocker.patch("core.thumbnail_cache._thumb_dir", return_value=d)
    return d


@pytest.fixture
def temp_db(tmp_path, mocker):
    """建真 temp DB + 把 scanner.get_db_path 導向它，回 (db_path, repo)。"""
    from core.database import init_db, VideoRepository
    db_path = tmp_path / "test.db"
    init_db(db_path)
    repo = VideoRepository(db_path)
    mocker.patch("web.routers.scanner.get_db_path", return_value=db_path)
    return db_path, repo


# ============ GET /api/gallery/thumb ============

class TestGetThumbHit:
    def test_hit_serves_webp_with_no_cache_and_etag(self, client, thumb_dir):
        """邊界1：hit → 200 image/webp + Cache-Control: no-cache + 強 ETag。"""
        uri = to_file_uri("/movies/v1.mp4")
        _make_webp(thumbnail_cache.thumb_file_for(uri))

        resp = client.get("/api/gallery/thumb", params={"path": uri})

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/webp"
        assert resp.headers["cache-control"] == "no-cache"
        etag = resp.headers["etag"]
        assert etag.startswith('"') and etag.endswith('"')
        assert etag.strip('"').isdigit()

    def test_hit_zero_db_zero_nas(self, client, thumb_dir, mocker):
        """邊界2：hit 路徑零 DB、零 NAS（generate / VideoRepository 未被呼叫）。"""
        uri = to_file_uri("/movies/v1.mp4")
        _make_webp(thumbnail_cache.thumb_file_for(uri))

        gen_spy = mocker.patch("web.routers.scanner.thumbnail_cache.generate")
        repo_spy = mocker.patch("web.routers.scanner.VideoRepository")
        db_spy = mocker.patch("web.routers.scanner.get_db_path")

        resp = client.get("/api/gallery/thumb", params={"path": uri})

        assert resp.status_code == 200
        gen_spy.assert_not_called()
        repo_spy.assert_not_called()
        db_spy.assert_not_called()

    def test_if_none_match_returns_304(self, client, thumb_dir):
        """邊界3：If-None-Match 命中 → 304 空 body。"""
        uri = to_file_uri("/movies/v1.mp4")
        _make_webp(thumbnail_cache.thumb_file_for(uri))

        first = client.get("/api/gallery/thumb", params={"path": uri})
        etag = first.headers["etag"]

        resp = client.get(
            "/api/gallery/thumb",
            params={"path": uri},
            headers={"If-None-Match": etag},
        )
        assert resp.status_code == 304
        assert resp.content == b""


class TestGetThumbMiss:
    def test_miss_generates_webp(self, client, thumb_dir, temp_db, tmp_path):
        """邊界4：miss + DB 有 video + cover 真小圖 → 200 image/webp，thumb 檔被建立。"""
        from core.database import Video
        _, repo = temp_db
        cover = _make_small_jpg(tmp_path / "cover.jpg")
        uri = to_file_uri("/movies/v1.mp4")
        repo.upsert_batch([
            Video(path=uri, mtime=100.0, cover_path=to_file_uri(str(cover))),
        ])

        tf = thumbnail_cache.thumb_file_for(uri)
        assert not tf.exists()

        resp = client.get("/api/gallery/thumb", params={"path": uri})

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/webp"
        assert tf.exists()

    def test_no_cover_returns_404(self, client, thumb_dir, temp_db):
        """邊界5a：DB 有 video 但 cover_path 空 → 404。"""
        from core.database import Video
        _, repo = temp_db
        uri = to_file_uri("/movies/nocover.mp4")
        repo.upsert_batch([Video(path=uri, mtime=100.0)])

        resp = client.get("/api/gallery/thumb", params={"path": uri})
        assert resp.status_code == 404

    def test_no_video_returns_404(self, client, thumb_dir, temp_db):
        """邊界5b：DB 無該 video → 404。"""
        uri = to_file_uri("/movies/ghost.mp4")
        resp = client.get("/api/gallery/thumb", params={"path": uri})
        assert resp.status_code == 404

    def test_db_not_exists_returns_404(self, client, thumb_dir, mocker):
        """miss 但 DB 不存在 → 404（不 500）。"""
        mocker.patch("web.routers.scanner.get_db_path",
                     return_value=Path("/nonexistent/openaver.db"))
        uri = to_file_uri("/movies/v1.mp4")
        resp = client.get("/api/gallery/thumb", params={"path": uri})
        assert resp.status_code == 404

    def test_generate_fail_fallbacks_to_original(self, client, thumb_dir, temp_db, tmp_path, mocker):
        """邊界6：generate 失敗 → fallback 原圖（200，非 image/webp、非 404、非破圖）。"""
        from core.database import Video
        _, repo = temp_db
        cover = _make_small_jpg(tmp_path / "cover.jpg")
        uri = to_file_uri("/movies/v1.mp4")
        repo.upsert_batch([
            Video(path=uri, mtime=100.0, cover_path=to_file_uri(str(cover))),
        ])
        mocker.patch("web.routers.scanner.thumbnail_cache.generate", return_value=False)

        resp = client.get("/api/gallery/thumb", params={"path": uri})

        assert resp.status_code == 200
        assert resp.headers["content-type"] != "image/webp"
        assert resp.headers["content-type"] == "image/jpeg"
        assert len(resp.content) > 0

    def test_generate_fail_missing_cover_returns_404_not_500(
        self, client, thumb_dir, temp_db, tmp_path, mocker
    ):
        """Codex P2(a)：generate 失敗且 cover 原圖不存在（並發刪/搬移）→ 404，
        而非 FileResponse(cover_fs) 在 send 時拋 → 500。讓前端破圖三態接手（D6）。
        """
        from core.database import Video
        _, repo = temp_db
        # 建一個真檔讓 is_known_cover_path 通過後再刪，模擬 cover 消失
        cover = _make_small_jpg(tmp_path / "cover.jpg")
        uri = to_file_uri("/movies/v1.mp4")
        repo.upsert_batch([
            Video(path=uri, mtime=100.0, cover_path=to_file_uri(str(cover))),
        ])
        cover.unlink()  # cover 原圖消失
        mocker.patch("web.routers.scanner.thumbnail_cache.generate", return_value=False)

        resp = client.get("/api/gallery/thumb", params={"path": uri})

        assert resp.status_code == 404, (
            f"cover 不存在時 fallback 應回 404（非 500/200），實際 {resp.status_code}"
        )


# ============ Codex round-2 P2: miss→generate 成功的 serve 在 OSError guard 外 ============

class TestGetThumbMissServeConcurrentUnlinkRace:
    """Codex round-2 P2：miss→generate 成功後 _serve_thumb_file 不在 try/except OSError 內。
    generate 成功 → DB row 刪除 + invalidate 移除 thumb → _serve_thumb_file 拋
    FileNotFoundError → 應降級 fallback（200 原圖 / 404），不得 500。
    """

    def test_miss_serve_oserror_does_not_500(self, client, thumb_dir, temp_db, tmp_path, mocker):
        """miss→generate True，但 miss-serve 拋 FileNotFoundError → 降級 fallback 原圖 200（非 500）。"""
        from core.database import Video
        _, repo = temp_db
        cover = _make_small_jpg(tmp_path / "cover.jpg")
        uri = to_file_uri("/movies/v1.mp4")
        repo.upsert_batch([
            Video(path=uri, mtime=100.0, cover_path=to_file_uri(str(cover))),
        ])
        # generate 回 True（但不真寫 thumb），miss-serve _serve_thumb_file 拋 FileNotFoundError
        mocker.patch("web.routers.scanner.thumbnail_cache.generate", return_value=True)

        real_serve = __import__("web.routers.scanner", fromlist=["_serve_thumb_file"])._serve_thumb_file
        state = {"raised": False}

        def racing_serve(tf, request):
            if not state["raised"]:
                state["raised"] = True
                raise FileNotFoundError("raced unlink before serve")
            return real_serve(tf, request)

        mocker.patch("web.routers.scanner._serve_thumb_file", side_effect=racing_serve)

        resp = client.get("/api/gallery/thumb", params={"path": uri})

        assert resp.status_code != 500, (
            f"miss→generate 成功後 serve 拋 OSError 不得 500，實際 {resp.status_code}"
        )
        # 降級 fallback：cover 原圖仍在 → 200 原圖
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/jpeg"


# ============ Codex round-2 P1: generate 後 fresh is None / 空 cover → stale ============

class TestGetThumbFreshNoneAfterGenerate:
    """Codex round-2 P1：generate 成功後 re-read DB 回 None（或 cover_path 空）→
    視為 stale，invalidate 丟棄剛寫 thumb 並回 404，不 serve 剛生成的 stale thumb。
    """

    def test_fresh_none_invalidates_and_404(self, client, thumb_dir, temp_db, tmp_path, mocker):
        from core.database import Video
        _, repo = temp_db
        cover = _make_small_jpg(tmp_path / "cover.jpg")
        uri = to_file_uri("/movies/v1.mp4")
        repo.upsert_batch([
            Video(path=uri, mtime=100.0, cover_path=to_file_uri(str(cover))),
        ])

        invalidate_spy = mocker.patch("web.routers.scanner.thumbnail_cache.invalidate")

        # get_by_path 第一次回真 video（miss 取 cover），generate 後第二次回 None（並發刪除）
        real_get = repo.get_by_path
        calls = {"n": 0}

        def get_then_none(p):
            calls["n"] += 1
            if calls["n"] == 1:
                return real_get(p)
            return None

        mocker.patch.object(
            __import__("web.routers.scanner", fromlist=["VideoRepository"]).VideoRepository,
            "get_by_path",
            autospec=True,
            side_effect=lambda self, p: get_then_none(p),
        )
        # generate 真寫一個 thumb（回 True）
        resp = client.get("/api/gallery/thumb", params={"path": uri})

        invalidate_spy.assert_called_once_with(uri)
        assert resp.status_code == 404, (
            f"fresh is None 應視為 stale → invalidate + 404，實際 {resp.status_code}"
        )


# ============ P1: generate 後 cover stale → invalidate + serve 當前封面 ============

class TestGetThumbStaleCoverAfterGenerate:
    """Codex P1：miss 路徑 generate(cover_fs) 成功後、serve 前 re-read DB cover；
    若 cover_path 已被並發換掉（enrich/rescrape）→ 丟棄剛寫的 stale thumb（invalidate）
    並改 serve 當前封面，避免把舊封面 thumb 當新圖回給用戶。
    """

    def test_stale_cover_invalidates_and_serves_current_cover(
        self, client, thumb_dir, temp_db, tmp_path, mocker
    ):
        from core.database import Video
        _, repo = temp_db
        cover_a = _make_small_jpg(tmp_path / "cover_a.jpg", size=(800, 600))
        cover_b = _make_small_jpg(tmp_path / "cover_b.jpg", size=(640, 480))
        uri = to_file_uri("/movies/v1.mp4")
        # DB 初始 cover A
        repo.upsert_batch([
            Video(path=uri, mtime=100.0, cover_path=to_file_uri(str(cover_a))),
        ])

        invalidate_spy = mocker.patch(
            "web.routers.scanner.thumbnail_cache.invalidate"
        )

        # generate(cover_a, tf) 「成功」後，模擬 DB 已被換成 cover B：
        # 讓 generate 真寫一個 thumb（回 True），且在 generate 後把 DB cover_path 改 B。
        real_generate = thumbnail_cache.generate

        def generate_then_swap(cover_fs, dst):
            ok = real_generate(cover_fs, dst)
            # 模擬並發 enrich 換封面
            repo.upsert_batch([
                Video(path=uri, mtime=100.0, cover_path=to_file_uri(str(cover_b))),
            ])
            return ok

        mocker.patch(
            "web.routers.scanner.thumbnail_cache.generate",
            side_effect=generate_then_swap,
        )

        resp = client.get("/api/gallery/thumb", params={"path": uri})

        # 偵測 stale → invalidate(path) 被呼叫丟棄剛寫的舊 thumb
        invalidate_spy.assert_called_once_with(uri)
        # serve 的不是 stale thumb（非 image/webp），而是當前封面 B 的原圖
        assert resp.status_code == 200
        assert resp.headers["content-type"] != "image/webp"
        assert resp.headers["content-type"] == "image/jpeg"
        # 內容是 cover B（當前封面），不是 cover A
        assert resp.content == cover_b.read_bytes()


# ============ POST /api/gallery/thumb/prewarm ============

class TestThumbPrewarm:
    def test_disabled_returns_disabled(self, client, mocker):
        """邊界7：thumbnail_cache_enabled=False → disabled，worker 未啟動。"""
        mocker.patch("web.routers.scanner.load_config",
                     return_value={"thumbnail_cache_enabled": False})
        iter_spy = mocker.patch("web.routers.scanner.thumbnail_cache.iter_missing")
        gen_spy = mocker.patch("web.routers.scanner.thumbnail_cache.generate")
        thread_spy = mocker.patch("web.routers.scanner.threading.Thread")

        resp = client.post("/api/gallery/thumb/prewarm")

        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"
        iter_spy.assert_not_called()
        gen_spy.assert_not_called()
        thread_spy.assert_not_called()

    def test_started_returns_started(self, client, mocker):
        """邊界8：enabled → started（patch Thread no-op 避免 flakiness）。"""
        import web.routers.scanner as scanner_mod
        mocker.patch("web.routers.scanner.load_config",
                     return_value={"thumbnail_cache_enabled": True})
        thread_spy = mocker.patch("web.routers.scanner.threading.Thread")

        # 確保 flag 乾淨
        scanner_mod._prewarming = False
        try:
            resp = client.post("/api/gallery/thumb/prewarm")
            assert resp.status_code == 200
            assert resp.json()["status"] == "started"
            thread_spy.assert_called_once()
            thread_spy.return_value.start.assert_called_once()
        finally:
            scanner_mod._prewarming = False

    def test_reentrant_returns_already_running(self, client, mocker):
        """邊界9：_prewarming=True → already_running，且不啟新 thread。"""
        import web.routers.scanner as scanner_mod
        mocker.patch("web.routers.scanner.load_config",
                     return_value={"thumbnail_cache_enabled": True})
        thread_spy = mocker.patch("web.routers.scanner.threading.Thread")

        scanner_mod._prewarming = True
        try:
            resp = client.post("/api/gallery/thumb/prewarm")
            assert resp.status_code == 200
            assert resp.json()["status"] == "already_running"
            thread_spy.assert_not_called()
        finally:
            scanner_mod._prewarming = False


# ============ M1: hit 後並發 unlink race（feature/71 T8）============

class TestThumbHitConcurrentUnlinkRace:
    """T8 邊界9：hit 判定（tf.exists()）通過後、_serve_thumb_file 內 tf.stat() 前，
    thumb 被並發 invalidate(unlink) → 不得 500（降級走 miss 重生或 404）。
    """

    def test_stat_filenotfound_does_not_500(self, client, thumb_dir, temp_db, tmp_path, mocker):
        """hit 後 stat 拋 FileNotFoundError：DB 有 video+cover → 降級重生 200（非 500）。"""
        from core.database import Video
        _, repo = temp_db
        cover = _make_small_jpg(tmp_path / "cover.jpg")
        uri = to_file_uri("/movies/v1.mp4")
        # 放真 thumb 讓 tf.exists() 為 True（hit 判定通過）
        _make_webp(thumbnail_cache.thumb_file_for(uri))
        repo.upsert_batch([
            Video(path=uri, mtime=100.0, cover_path=to_file_uri(str(cover))),
        ])

        # 模擬 race：tf.exists() 仍 True（hit 判定通過），但 _serve_thumb_file 的
        # tf.stat()（無 follow_symlinks kwarg）拋 FileNotFoundError。
        # Path.exists() 內部 stat 帶 follow_symlinks → 用此區分，不影響 hit 判定。
        # 只在「第一次」serve stat 拋（模擬 race）；降級重生後的 serve stat 正常。
        real_stat = Path.stat
        tf = thumbnail_cache.thumb_file_for(uri)
        state = {"raised": False}

        def racing_stat(self, *a, **kw):
            if self == tf and "follow_symlinks" not in kw and not state["raised"]:
                state["raised"] = True
                raise FileNotFoundError("raced unlink")
            return real_stat(self, *a, **kw)

        mocker.patch.object(Path, "stat", racing_stat)

        resp = client.get("/api/gallery/thumb", params={"path": uri})

        assert resp.status_code != 500, (
            f"hit 後並發 unlink（stat FileNotFound）不得 500，實際 {resp.status_code}"
        )
        # 降級重生：200 webp（DB 有 cover）
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/webp"

    def test_stat_filenotfound_no_cover_returns_404_not_500(
        self, client, thumb_dir, temp_db, mocker
    ):
        """hit 後 stat 拋 FileNotFoundError、DB 無 video → 404（非 500）。"""
        uri = to_file_uri("/movies/ghost.mp4")
        _make_webp(thumbnail_cache.thumb_file_for(uri))  # 有檔 → hit

        real_stat = Path.stat
        tf = thumbnail_cache.thumb_file_for(uri)

        def racing_stat(self, *a, **kw):
            if self == tf and "follow_symlinks" not in kw:
                raise FileNotFoundError("raced unlink")
            return real_stat(self, *a, **kw)

        mocker.patch.object(Path, "stat", racing_stat)

        resp = client.get("/api/gallery/thumb", params={"path": uri})

        assert resp.status_code != 500
        assert resp.status_code == 404


# ============ P2: clear/prewarm 競態（feature/71 round-3）============

class TestPrewarmClearRace:
    """round-3 P2：_prewarm_worker 從 stale snapshot 逐一 generate；期間用戶按
    「清除所有影片快取」→ clear_cache 跑 repo.clear_all() + thumbnail_cache.clear_all()
    （rmtree）。worker 不可在已清空目錄重建 orphan webp（DB 空 thumb 在）。
    修法：迴圈內 get_by_path re-check（before 跳過 / after 清 TOCTOU 孤兒），surgical。
    """

    def _patch_worker_deps(self, mocker, iter_items, get_by_path_side):
        """共用：patch worker 內 get_db_path / VideoRepository / iter_missing。
        回 (gen_spy, invalidate_spy, repo_mock)。
        """
        # db_path.exists() True
        db_path = mocker.MagicMock()
        db_path.exists.return_value = True
        mocker.patch("web.routers.scanner.get_db_path", return_value=db_path)

        repo_mock = mocker.MagicMock()
        repo_mock.get_all.return_value = []  # iter_missing 被 mock，回值不重要
        if isinstance(get_by_path_side, list):
            repo_mock.get_by_path.side_effect = get_by_path_side
        else:
            repo_mock.get_by_path.return_value = get_by_path_side
        mocker.patch("web.routers.scanner.VideoRepository", return_value=repo_mock)

        mocker.patch(
            "web.routers.scanner.thumbnail_cache.iter_missing",
            return_value=iter(iter_items),
        )
        gen_spy = mocker.patch(
            "web.routers.scanner.thumbnail_cache.generate", return_value=True
        )
        invalidate_spy = mocker.patch(
            "web.routers.scanner.thumbnail_cache.invalidate"
        )
        return gen_spy, invalidate_spy, repo_mock

    def test_before_check_skips_generate_when_video_gone(self, mocker):
        """RED1（before-check）：iter_missing 回幾筆，但 get_by_path 一律 None
        （模擬 clear 後 DB 空）→ generate 完全不被呼叫（不生成孤兒）。"""
        import web.routers.scanner as scanner_mod

        items = [
            (to_file_uri("/m/a.mp4"), "/cover/a.jpg"),
            (to_file_uri("/m/b.mp4"), "/cover/b.jpg"),
            (to_file_uri("/m/c.mp4"), "/cover/c.jpg"),
        ]
        gen_spy, invalidate_spy, repo_mock = self._patch_worker_deps(
            mocker, items, get_by_path_side=None  # 一律 None
        )
        mocker.patch("web.routers.scanner._emit_notif")
        scanner_mod._prewarming = True
        try:
            scanner_mod._prewarm_worker()
        finally:
            scanner_mod._prewarming = False

        gen_spy.assert_not_called()
        invalidate_spy.assert_not_called()

    def test_after_check_invalidates_toctou_orphan(self, mocker):
        """RED2（after-check）：get_by_path 第一次（before）回 video、第二次（after）
        回 None（模擬 generate 期間被清）+ generate 回 True → invalidate(uri) 被呼叫
        清掉剛寫的孤兒。"""
        import web.routers.scanner as scanner_mod

        uri = to_file_uri("/m/raced.mp4")
        items = [(uri, "/cover/raced.jpg")]
        # before → video（有 cover，據此生成）；after → None（被清，孤兒）
        sentinel_video = mocker.MagicMock(cover_path=to_file_uri("/cover/raced.jpg"))
        gen_spy, invalidate_spy, repo_mock = self._patch_worker_deps(
            mocker, items, get_by_path_side=[sentinel_video, None]
        )
        mocker.patch("web.routers.scanner._emit_notif")
        scanner_mod._prewarming = True
        try:
            scanner_mod._prewarm_worker()
        finally:
            scanner_mod._prewarming = False

        gen_spy.assert_called_once()
        invalidate_spy.assert_called_once_with(uri)

    def test_generate_uses_current_db_cover_not_stale_snapshot(self, mocker):
        """round-4 RED（cover-path-change，Codex repro）：iter_missing 的 snapshot
        cover 是 old，但 DB 當前 cover 已換成 new（enrich/rescrape）。worker 必須用
        「當前 DB cover」生成，忽略 stale snapshot cover → generate 收到 new 的 fs path。
        """
        import web.routers.scanner as scanner_mod

        uri = to_file_uri("/m/swapped.mp4")
        new_uri = to_file_uri("/cover/new.jpg")
        # snapshot 給 old；DB（before+after）一律回 new
        items = [(uri, "/cover/old.jpg")]
        cur_video = mocker.MagicMock(cover_path=new_uri)
        gen_spy, invalidate_spy, repo_mock = self._patch_worker_deps(
            mocker, items, get_by_path_side=cur_video  # before/after 都回 new
        )
        mocker.patch("web.routers.scanner._emit_notif")
        scanner_mod._prewarming = True
        try:
            scanner_mod._prewarm_worker()
        finally:
            scanner_mod._prewarming = False

        gen_spy.assert_called_once()
        used_cover_fs = gen_spy.call_args.args[0]
        assert used_cover_fs == uri_to_fs_path(new_uri)
        assert used_cover_fs != "/cover/old.jpg"
        # cover 沒在 generate 期間再變（before==after）→ 不 invalidate、計入
        invalidate_spy.assert_not_called()

    def test_after_check_invalidates_when_cover_changed_during_generate(self, mocker):
        """round-4 RED（after cover-change）：before 回 cover A、after 回 cover B
        （generate 期間 cover 又被換）+ generate True → invalidate(uri) 丟棄剛寫的
        stale thumb、不計入。"""
        import web.routers.scanner as scanner_mod

        uri = to_file_uri("/m/midswap.mp4")
        cover_a = to_file_uri("/cover/a.jpg")
        cover_b = to_file_uri("/cover/b.jpg")
        items = [(uri, "/cover/snapshot.jpg")]
        video_a = mocker.MagicMock(cover_path=cover_a)
        video_b = mocker.MagicMock(cover_path=cover_b)
        gen_spy, invalidate_spy, repo_mock = self._patch_worker_deps(
            mocker, items, get_by_path_side=[video_a, video_b]
        )
        mocker.patch("web.routers.scanner._emit_notif")
        scanner_mod._prewarming = True
        try:
            scanner_mod._prewarm_worker()
        finally:
            scanner_mod._prewarming = False

        gen_spy.assert_called_once()
        # before 用 cover A 生成
        assert gen_spy.call_args.args[0] == uri_to_fs_path(cover_a)
        # after 偵測 cover 變 B → 丟棄
        invalidate_spy.assert_called_once_with(uri)


# ============ POST /api/gallery/thumb/clear (71b-T2) ============

class TestThumbClear:
    """71b-T2：DB-safe 清空端點。清 output/thumb/、回 {"cleared": True}，
    **絕不碰 videos DB**（row 數不變）。鏡像 prewarm 端點測試模式。"""

    def test_clear_returns_cleared_true(self, client, thumb_dir):
        resp = client.post("/api/gallery/thumb/clear")
        assert resp.status_code == 200
        assert resp.json() == {"cleared": True}

    def test_clear_removes_thumb_dir_contents(self, client, thumb_dir):
        """thumb_dir 內既有 webp → 清後目錄被移除（rmtree，缺目錄 no-op）。"""
        uri = to_file_uri("/movies/v1.mp4")
        _make_webp(thumbnail_cache.thumb_file_for(uri))
        assert any(thumb_dir.iterdir()), "前置：thumb_dir 應有檔"

        resp = client.post("/api/gallery/thumb/clear")

        assert resp.status_code == 200
        # rmtree(_thumb_dir())：整個目錄移除（CD-11 缺目錄 no-op）
        assert not thumb_dir.exists() or not any(thumb_dir.iterdir()), \
            "thumb_dir 應被清空"

    def test_clear_does_not_touch_videos_db(self, client, thumb_dir, temp_db):
        """硬約束：videos DB row 數清前清後不變（端點絕不碰 DB）。"""
        from core.database import Video
        _, repo = temp_db
        repo.upsert_batch([
            Video(path=to_file_uri("/movies/a.mp4"), mtime=1.0),
            Video(path=to_file_uri("/movies/b.mp4"), mtime=2.0),
            Video(path=to_file_uri("/movies/c.mp4"), mtime=3.0),
        ])
        before = repo.count()
        assert before == 3, "前置：DB 應有 3 筆"

        resp = client.post("/api/gallery/thumb/clear")

        assert resp.status_code == 200
        assert repo.count() == before, \
            f"videos DB row 數不得變（清前 {before}，清後 {repo.count()}）"

    def test_clear_idempotent_when_dir_missing(self, client, thumb_dir):
        """冪等：目錄不存在時再 clear 仍 200 + cleared（rmtree ignore_errors）。"""
        client.post("/api/gallery/thumb/clear")
        resp = client.post("/api/gallery/thumb/clear")
        assert resp.status_code == 200
        assert resp.json() == {"cleared": True}
