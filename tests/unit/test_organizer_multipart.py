"""
測試 core/organizer.py 中的多段 token 純函式：
  - MULTIPART_TOKENS 常數
  - _detect_multipart_token(filename) -> Optional[Tuple[str, int]]
  - _strip_part_token(stem) -> str

TDD-lite：先 RED，實作後 GREEN。
"""
import pytest
from core.organizer import (
    MULTIPART_TOKENS,
    _detect_multipart_token,
    _strip_part_token,
)


# ---------------------------------------------------------------------------
# MULTIPART_TOKENS 常數
# ---------------------------------------------------------------------------

class TestMultipartTokensConstant:
    def test_contains_all_prefixes(self):
        assert {'cd', 'dvd', 'part', 'pt', 'disc'} == MULTIPART_TOKENS


# ---------------------------------------------------------------------------
# _detect_multipart_token — Positive cases
# ---------------------------------------------------------------------------

class TestDetectMultipartTokenPositive:
    def test_cd1(self):
        assert _detect_multipart_token('MIRD-151-cd1.mkv') == ('cd1', 1)

    def test_dvd2(self):
        assert _detect_multipart_token('ABC-123-dvd2.mp4') == ('dvd2', 2)

    def test_part1(self):
        assert _detect_multipart_token('XYZ-001-part1.avi') == ('part1', 1)

    def test_pt2(self):
        assert _detect_multipart_token('FOO-009-pt2.wmv') == ('pt2', 2)

    def test_disc1(self):
        assert _detect_multipart_token('BAR-555-disc1.mkv') == ('disc1', 1)

    def test_case_insensitive_CD1(self):
        """大寫 CD1 回傳 lower 的 ("cd1", 1)"""
        assert _detect_multipart_token('MIRD-151-CD1.mkv') == ('cd1', 1)

    def test_bracket_square_cd1(self):
        """[cd1] bracket 包裹"""
        assert _detect_multipart_token('MIRD-151[cd1].mkv') == ('cd1', 1)

    def test_bracket_paren_part2(self):
        """(part2) 括號包裹"""
        assert _detect_multipart_token('MIRD-151(part2).mp4') == ('part2', 2)

    def test_underscore_separator(self):
        """底線分隔"""
        assert _detect_multipart_token('MIRD-151_cd1.mkv') == ('cd1', 1)

    def test_space_separator(self):
        """空白分隔"""
        assert _detect_multipart_token('MIRD-151 cd2.mkv') == ('cd2', 2)

    def test_all_digit_positions_1_to_9(self):
        """1-9 各數字都應匹配"""
        for i in range(1, 10):
            result = _detect_multipart_token(f'ABC-{i:03d}-cd{i}.mkv')
            assert result == (f'cd{i}', i), f'Failed for cd{i}'

    def test_rightmost_match_wins(self):
        """多個 token 時取最右（靠後）那個"""
        result = _detect_multipart_token('MIRD-cd1-cd2.mkv')
        assert result == ('cd2', 2)


# ---------------------------------------------------------------------------
# _detect_multipart_token — Negative cases
# ---------------------------------------------------------------------------

class TestDetectMultipartTokenNegative:
    def test_no_token(self):
        assert _detect_multipart_token('ABC-123.mkv') is None

    def test_cd10_two_digits(self):
        """cd10 數字≥10，不匹配"""
        assert _detect_multipart_token('cd10') is None

    def test_cd10_in_filename(self):
        assert _detect_multipart_token('MIRD-151-cd10.mkv') is None

    def test_cd_disc10(self):
        """cd-disc10：disc10 兩位數，不得誤命中 disc1"""
        assert _detect_multipart_token('MIRD-151-cd-disc10.mkv') is None

    def test_apartment1_no_false_positive(self):
        """apartment1：前緣是字母 t，part1 不得誤命中"""
        assert _detect_multipart_token('apartment1.mkv') is None

    def test_version_4k(self):
        """VERSION token 4k 不得命中"""
        assert _detect_multipart_token('MIRD-151-4k.mkv') is None

    def test_version_uc(self):
        """VERSION token uc 不得命中"""
        assert _detect_multipart_token('ABC-123-uc.mkv') is None

    def test_version_C_subtitle(self):
        """FOO-C（中文字幕版）不得命中"""
        assert _detect_multipart_token('FOO-C.mkv') is None

    def test_cd0_zero_digit(self):
        """cd0：0 不在 1-9，不匹配"""
        assert _detect_multipart_token('cd0.mkv') is None

    def test_cd1abc_letter_after_digit(self):
        """cd1abc：token 後緊接字母，後緣邊界否決"""
        assert _detect_multipart_token('MIRD-151-cd1abc.mkv') is None

    def test_record1_prefix_word(self):
        """record1：cd 前緣為字母 r，不得誤命中"""
        assert _detect_multipart_token('record1.mkv') is None

    def test_no_extension(self):
        """無副檔名：純 stem"""
        assert _detect_multipart_token('MIRD-151-cd1') == ('cd1', 1)

    def test_empty_filename(self):
        """空字串不崩潰"""
        assert _detect_multipart_token('') is None


# ---------------------------------------------------------------------------
# _strip_part_token
# ---------------------------------------------------------------------------

class TestStripPartToken:
    def test_strip_dash_cd1(self):
        """MIRD-151-cd1 → MIRD-151（連前導 - 一起剝）"""
        assert _strip_part_token('MIRD-151-cd1') == 'MIRD-151'

    def test_strip_underscore_part2(self):
        """MIRD-151_part2 → MIRD-151（底線前導同剝）"""
        assert _strip_part_token('MIRD-151_part2') == 'MIRD-151'

    def test_noop_no_token(self):
        """無 token → 原樣回傳"""
        assert _strip_part_token('MIRD-151') == 'MIRD-151'

    def test_token_at_stem_start(self):
        """cd1 在起點無前導分隔符 → 只剝 token，回傳 ''"""
        assert _strip_part_token('cd1') == ''

    def test_version_token_untouched(self):
        """MIRD-151-4k 是 VERSION token，不被剝"""
        assert _strip_part_token('MIRD-151-4k') == 'MIRD-151-4k'

    def test_preserves_base_casing(self):
        """MIRD-151-CD1：剝除 token，base 段大小寫不變"""
        assert _strip_part_token('MIRD-151-CD1') == 'MIRD-151'

    def test_strip_space_separator(self):
        """空白作為前導分隔符"""
        assert _strip_part_token('MIRD-151 cd1') == 'MIRD-151'

    def test_strip_bracket_square(self):
        """[cd1] 帶前導 [ 剝掉 '[cd1'，後緣 ']' 為 lookahead 不消耗→殘留（已知契約）"""
        # '[cd1]' — '[' 是前導分隔符一併剝；']' 是後緣邊界 lookahead 不消耗 → 殘留 ']'
        # 此為已知契約（pin 精確值，bracket-wrapped 多段 token 罕見；T5 若直用其輸出需另清尾括）
        result = _strip_part_token('MIRD-151[cd1]')
        assert result == 'MIRD-151]'

    def test_strip_dvd1(self):
        """dvd 前綴"""
        assert _strip_part_token('ABC-123-dvd1') == 'ABC-123'

    def test_strip_disc1(self):
        """disc 前綴"""
        assert _strip_part_token('BAR-555-disc1') == 'BAR-555'

    def test_strip_pt2(self):
        """pt 前綴"""
        assert _strip_part_token('FOO-009-pt2') == 'FOO-009'

    def test_empty_stem(self):
        """空 stem 不崩潰"""
        assert _strip_part_token('') == ''

    def test_rightmost_stripped(self):
        """有兩個 token 時剝最靠後的那個"""
        # 'MIRD-cd1-cd2' → 剝 '-cd2' → 'MIRD-cd1'
        assert _strip_part_token('MIRD-cd1-cd2') == 'MIRD-cd1'
