"""
測試 core/gallery_scanner.py 中的 parse_nfo() 新欄位讀取、
VideoInfo round-trip 及 scan_file() merge 邏輯。
"""
import dataclasses
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from core.gallery_scanner import VideoInfo, VideoScanner


# ============ VideoInfo dataclass 測試 ============

class TestVideoInfoNewFields:
    """VideoInfo 新增 director/duration/series/label 欄位測試"""

    def test_videoinfo_has_director_field(self):
        """VideoInfo 應有 director 欄位，預設 ''"""
        info = VideoInfo()
        assert hasattr(info, 'director')
        assert info.director == ''

    def test_videoinfo_has_duration_field(self):
        """VideoInfo 應有 duration 欄位，預設 None"""
        info = VideoInfo()
        assert hasattr(info, 'duration')
        assert info.duration is None

    def test_videoinfo_has_series_field(self):
        """VideoInfo 應有 series 欄位，預設 ''"""
        info = VideoInfo()
        assert hasattr(info, 'series')
        assert info.series == ''

    def test_videoinfo_has_label_field(self):
        """VideoInfo 應有 label 欄位，預設 ''"""
        info = VideoInfo()
        assert hasattr(info, 'label')
        assert info.label == ''

    def test_to_dict_includes_all_new_fields(self):
        """to_dict() 應包含 4 個新欄位"""
        info = VideoInfo(
            path="/test.mp4",
            director="テスト監督",
            duration=119,
            series="テストシリーズ",
            label="S1"
        )
        d = info.to_dict()
        assert 'director' in d
        assert 'duration' in d
        assert 'series' in d
        assert 'label' in d
        assert d['director'] == "テスト監督"
        assert d['duration'] == 119
        assert d['series'] == "テストシリーズ"
        assert d['label'] == "S1"

    def test_from_dict_roundtrip(self):
        """from_dict() round-trip 應完整還原新欄位"""
        original = VideoInfo(
            path="/test.mp4",
            title="タイトル",
            director="監督名",
            duration=90,
            series="シリーズ名",
            label="premium"
        )
        d = original.to_dict()
        restored = VideoInfo.from_dict(d)
        assert restored.director == original.director
        assert restored.duration == original.duration
        assert restored.series == original.series
        assert restored.label == original.label

    def test_from_dict_old_dict_no_crash(self):
        """舊 dict（缺新欄位）→ 不 crash，用預設值填充"""
        old_dict = {
            "path": "/old.mp4",
            "title": "舊標題",
            "originaltitle": "",
            "actor": "",
            "num": "OLD-001",
            "maker": "",
            "date": "",
            "genre": "",
            "size": 0,
            "mtime": 0,
            "img": ""
        }
        info = VideoInfo.from_dict(old_dict)
        assert info.path == "/old.mp4"
        assert info.title == "舊標題"
        assert info.director == ''
        assert info.duration is None
        assert info.series == ''
        assert info.label == ''

    def test_from_dict_unknown_key_no_crash(self):
        """含未知 key 的 dict → 不 crash（防禦性過濾）"""
        d = {
            "path": "/test.mp4",
            "title": "テスト",
            "originaltitle": "",
            "actor": "",
            "num": "",
            "maker": "",
            "date": "",
            "genre": "",
            "size": 0,
            "mtime": 0,
            "img": "",
            "unknown_future_field": "some_value",
            "another_unknown": 42
        }
        info = VideoInfo.from_dict(d)
        assert info.path == "/test.mp4"
        assert info.title == "テスト"

    def test_from_dict_duration_zero_preserved(self):
        """duration=0 在 round-trip 中不被短路為 None"""
        original = VideoInfo(path="/test.mp4", duration=0)
        d = original.to_dict()
        restored = VideoInfo.from_dict(d)
        assert restored.duration == 0


# ============ parse_nfo() 新欄位測試 ============

class TestParseNfoNewFields:
    """parse_nfo() 讀取 <runtime>, <director>, <set><name>, <label> 測試"""

    def _write_nfo(self, tmp_path, content: str) -> str:
        """寫入 NFO 並回傳路徑字串"""
        nfo = tmp_path / "test.nfo"
        nfo.write_text(content, encoding="utf-8")
        return str(nfo)

    def test_parse_nfo_all_new_fields(self, tmp_path):
        """mock XML 含全部新 tag → 正確讀回 director/duration/series/label"""
        nfo_xml = textwrap.dedent("""\
            <?xml version="1.0" encoding="utf-8"?>
            <movie>
              <title>テストタイトル</title>
              <originaltitle>Test Title</originaltitle>
              <runtime>119</runtime>
              <director>テスト監督</director>
              <set><name>テストシリーズ</name></set>
              <label>S1</label>
              <studio>テスト片商</studio>
            </movie>
        """)
        nfo_path = self._write_nfo(tmp_path, nfo_xml)
        scanner = VideoScanner()
        info = scanner.parse_nfo(nfo_path)

        assert info is not None
        assert info.duration == 119
        assert info.director == "テスト監督"
        assert info.series == "テストシリーズ"
        assert info.label == "S1"

    def test_parse_nfo_runtime_invalid_string(self, tmp_path):
        """<runtime> 非數字字串 → duration=None（不 crash）"""
        nfo_xml = textwrap.dedent("""\
            <?xml version="1.0" encoding="utf-8"?>
            <movie>
              <title>テスト</title>
              <runtime>N/A</runtime>
            </movie>
        """)
        nfo_path = self._write_nfo(tmp_path, nfo_xml)
        scanner = VideoScanner()
        info = scanner.parse_nfo(nfo_path)

        assert info is not None
        assert info.duration is None

    def test_parse_nfo_runtime_zero(self, tmp_path):
        """<runtime>0</runtime> → duration=0（0 是有效值，不應被忽略）"""
        nfo_xml = textwrap.dedent("""\
            <?xml version="1.0" encoding="utf-8"?>
            <movie>
              <title>テスト</title>
              <runtime>0</runtime>
            </movie>
        """)
        nfo_path = self._write_nfo(tmp_path, nfo_xml)
        scanner = VideoScanner()
        info = scanner.parse_nfo(nfo_path)

        assert info is not None
        assert info.duration == 0

    def test_parse_nfo_set_without_name(self, tmp_path):
        """<set> 存在但無 <name> → series=''"""
        nfo_xml = textwrap.dedent("""\
            <?xml version="1.0" encoding="utf-8"?>
            <movie>
              <title>テスト</title>
              <set></set>
            </movie>
        """)
        nfo_path = self._write_nfo(tmp_path, nfo_xml)
        scanner = VideoScanner()
        info = scanner.parse_nfo(nfo_path)

        assert info is not None
        assert info.series == ''

    def test_parse_nfo_missing_all_new_tags(self, tmp_path):
        """缺全部新 tag → 全部為預設值"""
        nfo_xml = textwrap.dedent("""\
            <?xml version="1.0" encoding="utf-8"?>
            <movie>
              <title>テスト</title>
              <studio>テスト片商</studio>
            </movie>
        """)
        nfo_path = self._write_nfo(tmp_path, nfo_xml)
        scanner = VideoScanner()
        info = scanner.parse_nfo(nfo_path)

        assert info is not None
        assert info.duration is None
        assert info.director == ''
        assert info.series == ''
        assert info.label == ''

    def test_parse_nfo_runtime_empty_tag(self, tmp_path):
        """<runtime></runtime> 空標籤 → duration=None"""
        nfo_xml = textwrap.dedent("""\
            <?xml version="1.0" encoding="utf-8"?>
            <movie>
              <title>テスト</title>
              <runtime></runtime>
            </movie>
        """)
        nfo_path = self._write_nfo(tmp_path, nfo_xml)
        scanner = VideoScanner()
        info = scanner.parse_nfo(nfo_path)

        assert info is not None
        assert info.duration is None

    def test_parse_nfo_label_empty_tag(self, tmp_path):
        """<label></label> 空標籤 → label=''"""
        nfo_xml = textwrap.dedent("""\
            <?xml version="1.0" encoding="utf-8"?>
            <movie>
              <title>テスト</title>
              <label></label>
            </movie>
        """)
        nfo_path = self._write_nfo(tmp_path, nfo_xml)
        scanner = VideoScanner()
        info = scanner.parse_nfo(nfo_path)

        assert info is not None
        assert info.label == ''


# ============ scan_file() merge 測試 ============

class TestScanFileMerge:
    """scan_file() NFO merge 區塊覆蓋 director/duration/series/label"""

    def test_merge_new_fields_from_nfo(self, tmp_path):
        """scan_file() 應從 NFO merge director/duration/series/label"""
        # 建立假影片檔（touch）
        video_file = tmp_path / "TEST-001.mp4"
        video_file.write_bytes(b"\x00" * 100)

        # 建立 NFO
        nfo_file = tmp_path / "TEST-001.nfo"
        nfo_file.write_text(textwrap.dedent("""\
            <?xml version="1.0" encoding="utf-8"?>
            <movie>
              <title>テストタイトル</title>
              <num>TEST-001</num>
              <runtime>90</runtime>
              <director>A監督</director>
              <set><name>Aシリーズ</name></set>
              <label>premium</label>
            </movie>
        """), encoding="utf-8")

        scanner = VideoScanner()
        info = scanner.scan_file(str(video_file))

        assert info.duration == 90
        assert info.director == "A監督"
        assert info.series == "Aシリーズ"
        assert info.label == "premium"

    def test_merge_duration_zero_not_skipped(self, tmp_path):
        """duration=0 在 merge 時不應被 or 短路跳過"""
        video_file = tmp_path / "TEST-002.mp4"
        video_file.write_bytes(b"\x00" * 100)

        nfo_file = tmp_path / "TEST-002.nfo"
        nfo_file.write_text(textwrap.dedent("""\
            <?xml version="1.0" encoding="utf-8"?>
            <movie>
              <title>テスト</title>
              <num>TEST-002</num>
              <runtime>0</runtime>
            </movie>
        """), encoding="utf-8")

        scanner = VideoScanner()
        info = scanner.scan_file(str(video_file))

        assert info.duration == 0
