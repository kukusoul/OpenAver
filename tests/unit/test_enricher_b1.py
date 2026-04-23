"""tests/unit/test_enricher_b1.py — spec-48b §b1 AC#1 root-cause fix 測試

- TestDbUpsertSampleImagesGate：驗證 _db_upsert() sample_images gate 行為
  write_extrafanart=False  → DB 不寫入遠端 URL（保留現有值）
  write_extrafanart=True, count=0 → DB 不寫入
  write_extrafanart=True, count>0 → DB 更新
"""


class TestDbUpsertSampleImagesGate:
    """spec-48b §b1 AC#1 — _db_upsert sample_images gate"""

    def _run_enrich(self, write_extrafanart, download_count, existing_samples=None):
        """Helper：執行 enrich_single 並回傳 repo.upsert call args"""
        from unittest.mock import patch, MagicMock, call
        with patch("os.path.exists", return_value=True), \
             patch("core.enricher.VideoRepository") as mock_repo_cls, \
             patch("core.enricher.search_jav") as mock_search, \
             patch("core.enricher.generate_nfo", return_value=True), \
             patch("core.enricher.download_image", return_value=True), \
             patch("core.enricher._write_extrafanart", return_value=download_count), \
             patch("core.enricher.find_subtitle_files", return_value=[]):
            mock_repo = MagicMock()
            mock_existing = MagicMock()
            mock_existing.sample_images = existing_samples or []
            mock_existing.user_tags = []
            mock_existing.cover_path = ""
            mock_repo.get_by_path.return_value = mock_existing
            mock_repo_cls.return_value = mock_repo
            mock_search.return_value = {
                "number": "SONE-205",
                "title": "Test",
                "actors": [],
                "cover": "http://example.com/cover.jpg",
                "date": "2024-01-01",
                "maker": "SOD",
                "director": "",
                "series": "",
                "label": "",
                "tags": [],
                "sample_images": ["http://example.com/s1.jpg"],
                "source": "javbus",
            }
            from core.enricher import enrich_single
            enrich_single(
                file_path="/tmp/SONE-205.mp4",
                number="SONE-205",
                mode="refresh_full",
                write_extrafanart=write_extrafanart,
                write_nfo=False,
                write_cover=False,
            )
            return mock_repo.upsert.call_args

    def test_no_extrafanart_flag_does_not_write_sample_images(self):
        """write_extrafanart=False → sample_images 欄位保留現有值"""
        args = self._run_enrich(write_extrafanart=False, download_count=0, existing_samples=["file:///old.jpg"])
        video = args[0][0]
        assert video.sample_images == ["file:///old.jpg"], \
            "write_extrafanart=False 時不應覆蓋 DB sample_images"

    def test_extrafanart_written_zero_does_not_write_sample_images(self):
        """write_extrafanart=True 但下載 0 張 → 不更新"""
        args = self._run_enrich(write_extrafanart=True, download_count=0, existing_samples=[])
        video = args[0][0]
        assert video.sample_images == [], \
            "extrafanart_written=0 時不應寫入 scraper 回傳的遠端 URL"

    def test_extrafanart_written_positive_updates_sample_images(self):
        """write_extrafanart=True 且下載 > 0 張 → 更新 DB"""
        args = self._run_enrich(write_extrafanart=True, download_count=2, existing_samples=[])
        video = args[0][0]
        assert "http://example.com/s1.jpg" in video.sample_images, \
            "extrafanart_written>0 時應寫入 scraper 回傳的 URLs"


class TestDatabaseHelpers:
    """spec-48b §b1 — VideoRepository.update_sample_images + count_videos_in_folder"""

    def _make_repo(self, tmp_path):
        """建立 in-memory DB（使用 tmp_path 確保隔離）"""
        from pathlib import Path
        from core.database import init_db, VideoRepository
        db_path = tmp_path / "test_b2.db"
        init_db(db_path)
        return VideoRepository(db_path)

    def _insert_video(self, repo, path: str, **kwargs):
        """插入測試影片 row"""
        from core.database import Video
        video = Video(
            path=path,
            number=kwargs.get("number", "TEST-001"),
            title=kwargs.get("title", "Test Title"),
            actresses=kwargs.get("actresses", []),
            user_tags=kwargs.get("user_tags", []),
            sample_images=kwargs.get("sample_images", []),
        )
        repo.upsert(video)

    def test_update_sample_images_only_updates_that_field(self, tmp_path):
        """update_sample_images 寫入後，其他欄位（title / user_tags）不變"""
        from core.database import init_db, VideoRepository
        repo = self._make_repo(tmp_path)
        self._insert_video(
            repo,
            path="file:///A/v1.mp4",
            title="Original Title",
            user_tags=["tag1"],
            sample_images=[],
        )

        new_samples = ["file:///A/extrafanart/s1.jpg"]
        result = repo.update_sample_images("file:///A/v1.mp4", new_samples)

        assert result is True, "update_sample_images 應回傳 True（rowcount > 0）"

        video = repo.get_by_path("file:///A/v1.mp4")
        assert video.sample_images == new_samples, "sample_images 應被更新"
        assert video.title == "Original Title", "title 欄位不應被改動"
        assert video.user_tags == ["tag1"], "user_tags 欄位不應被改動"

    def test_count_videos_in_folder_excludes_subdirectories(self, tmp_path):
        """/A/v1.mp4 + /A/v2.mp4 + /A/sub/v3.mp4 → count_in_folder("file:///A/") == 2"""
        repo = self._make_repo(tmp_path)
        self._insert_video(repo, path="file:///A/v1.mp4", number="A001")
        self._insert_video(repo, path="file:///A/v2.mp4", number="A002")
        self._insert_video(repo, path="file:///A/sub/v3.mp4", number="A003")

        count = repo.count_videos_in_folder("file:///A/")
        assert count == 2, (
            f"子目錄排除失敗：期待 2，實際 {count}。"
            "/A/sub/v3.mp4 不應計入 /A/ 的計數"
        )

    def test_count_videos_in_folder_escapes_underscore(self, tmp_path):
        """my_movie/ prefix 只 match my_movie/，不應 match myXmovie/"""
        repo = self._make_repo(tmp_path)
        self._insert_video(repo, path="file:///A/my_movie/v1.mp4", number="U001")
        self._insert_video(repo, path="file:///A/myXmovie/v2.mp4", number="U002")

        count = repo.count_videos_in_folder("file:///A/my_movie/")
        assert count == 1, (
            f"下底線 escape 失敗：期待 1，實際 {count}。"
            "my_movie/ 中的 _ 被當成 LIKE 單字元 wildcard 誤匹配 myXmovie/"
        )

    def test_count_videos_in_folder_escapes_percent(self, tmp_path):
        """user%20name/ prefix 中的 % 應被 escape，正確 match 路徑"""
        repo = self._make_repo(tmp_path)
        self._insert_video(
            repo,
            path="file:///home/user%20name/v.mp4",
            number="P001",
        )
        self._insert_video(
            repo,
            path="file:///home/userXXname/v2.mp4",
            number="P002",
        )

        count = repo.count_videos_in_folder("file:///home/user%20name/")
        assert count == 1, (
            f"百分號 escape 失敗：期待 1，實際 {count}。"
            "%20 中的 % 不應被當成 LIKE wildcard"
        )

    def test_count_videos_in_folder_escapes_backslash(self, tmp_path):
        """Windows UNC: file:////server/share/ prefix 正確 match"""
        repo = self._make_repo(tmp_path)
        self._insert_video(
            repo,
            path="file:////server/share/v.mp4",
            number="W001",
        )

        count = repo.count_videos_in_folder("file:////server/share/")
        assert count == 1, (
            f"反斜線 escape 失敗：期待 1，實際 {count}。"
            "Windows UNC path 中的反斜線應被正確 escape"
        )
