"""
tests/unit/test_javlibrary_parser.py
──────────────────────────────────────
HTML fixture 驗 parser 純邏輯（TDD-lite RED → GREEN）

情境 h–o：
  h) parse_detail happy path
  i) parse_detail 封面 // 補全
  j) parse_detail 標題剝番號前綴
  k) _is_cf_challenge
  l) _is_age_gate
  m) _extract_detail_url multi-result
  n) _extract_detail_url 無結果
  o) _is_detail_page
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from core.scrapers.javlibrary import (
    _extract_detail_url,
    _is_age_gate,
    _is_cf_challenge,
    _is_detail_page,
    parse_detail,
)

# ──────────────────────────────────────
# 共用 fixture HTML
# ──────────────────────────────────────

DETAIL_HTML = """\
<html><head><title>TCD-332 恥辱の○秘映像</title></head><body>
  <h3 class="post-title">TCD-332　恥辱の○秘映像鈴白めいか</h3>
  <div id="video_id"><table><tr><td class="text">TCD-332</td></tr></table></div>
  <div id="video_date"><table><tr><td class="text">2026-05-12</td></tr></table></div>
  <div id="video_length"><table><tr><td class="text"><span>126</span></td></tr></table></div>
  <div id="video_director"><table><tr><td class="text"><span><a>アングラ仁（JIN）</a></span></td></tr></table></div>
  <div id="video_maker"><table><tr><td class="text"><span><a>TRANS CLUB</a></span></td></tr></table></div>
  <div id="video_label"><table><tr><td class="text"><span><a>----</a></span></td></tr></table></div>
  <div id="video_review"><span>(10.00)</span></div>
  <img id="video_jacket_img" src="//pics.dmm.co.jp/mono/movie/adult/tcd332/tcd332pl.jpg" />
  <div id="video_genres"><a>変性者</a><a>単体作品</a></div>
  <div id="video_cast">
    <span class="star"><a>鈴白めいか</a></span>
    <span class="star"><a>  </a></span>
  </div>
  <div class="previewthumbs">
    <a href="//pics.dmm.co.jp/sample1.jpg"><img></a>
    <a href="//pics.dmm.co.jp/sample2.jpg"><img></a>
  </div>
</body></html>"""

CF_CHALLENGE_HTML = """\
<html><head><title>Just a moment...</title></head><body>
  <form id="challenge-form">
    <input name="cf-turnstile-response" type="hidden">
  </form>
</body></html>"""

AGE_GATE_HTML = """\
<html><head><title>JavLibrary</title></head><body>
  利用規約に同意して続けてください。
  <button id="agreeBtn">同意</button>
</body></html>"""

MULTI_RESULT_HTML = """\
<html><head><title>Search Results</title></head><body>
  <div class="video"><a href="./javmezzbqu.html" title="TCD-332 恥辱...">TCD-332 恥辱...</a></div>
  <div class="video"><a href="./javother001.html" title="OTHER-001">OTHER-001</a></div>
</body></html>"""

NO_RESULT_HTML = """\
<html><head><title>No Results</title></head><body>
  <p>No results found.</p>
</body></html>"""

COVER_ONLY_HTML = """\
<html><head><title>MIDE-800</title></head><body>
  <h3 class="post-title">MIDE-800　美しい...</h3>
  <div id="video_id"><table><tr><td class="text">MIDE-800</td></tr></table></div>
  <img id="video_jacket_img" src="//pics.dmm.co.jp/mide800pl.jpg" />
</body></html>"""


# ──────────────────────────────────────
# (h) parse_detail happy path
# ──────────────────────────────────────

def test_parse_detail_happy_path_number():
    fields = parse_detail(DETAIL_HTML, "TCD-332")
    assert fields["number"] == "TCD-332"


def test_parse_detail_happy_path_title_stripped():
    fields = parse_detail(DETAIL_HTML, "TCD-332")
    # 標題不含番號前綴
    assert "TCD-332" not in fields["title"]
    assert len(fields["title"]) > 0


def test_parse_detail_happy_path_score():
    fields = parse_detail(DETAIL_HTML, "TCD-332")
    assert fields["score"] == 10.0


def test_parse_detail_happy_path_genres():
    fields = parse_detail(DETAIL_HTML, "TCD-332")
    assert "変性者" in fields["genres"]
    assert "単体作品" in fields["genres"]


def test_parse_detail_happy_path_cast():
    fields = parse_detail(DETAIL_HTML, "TCD-332")
    assert "鈴白めいか" in fields["cast"]


def test_parse_detail_happy_path_cover_https():
    fields = parse_detail(DETAIL_HTML, "TCD-332")
    assert fields["cover"].startswith("https://")


def test_parse_detail_happy_path_sample_images_list():
    fields = parse_detail(DETAIL_HTML, "TCD-332")
    assert isinstance(fields["samples"], list)
    assert len(fields["samples"]) == 2
    for url in fields["samples"]:
        assert url.startswith("https://")


def test_parse_detail_happy_path_duration():
    fields = parse_detail(DETAIL_HTML, "TCD-332")
    assert fields["length"] == "126"


def test_parse_detail_happy_path_date():
    fields = parse_detail(DETAIL_HTML, "TCD-332")
    assert fields["date"] == "2026-05-12"


def test_parse_detail_happy_path_empty_cast_filtered():
    """空白演員名稱不應出現在 cast list"""
    fields = parse_detail(DETAIL_HTML, "TCD-332")
    for name in fields["cast"]:
        assert name.strip() != ""


# ──────────────────────────────────────
# (i) parse_detail 封面 // 補全
# ──────────────────────────────────────

def test_parse_detail_cover_protocol_relative():
    """cover src 以 // 開頭時，應補全為 https:"""
    html = """\
<html><head><title>MIDE-800</title></head><body>
  <h3 class="post-title">MIDE-800　美しい女優</h3>
  <div id="video_id"><table><tr><td class="text">MIDE-800</td></tr></table></div>
  <img id="video_jacket_img" src="//pics.dmm.co.jp/mono/movie/adult/mide800/mide800pl.jpg" />
</body></html>"""
    fields = parse_detail(html, "MIDE-800")
    assert fields["cover"].startswith("https://pics.dmm.co.jp/")


def test_parse_detail_sample_images_protocol_relative():
    """sample_images href 以 // 開頭時，應補全為 https:"""
    fields = parse_detail(DETAIL_HTML, "TCD-332")
    for url in fields["samples"]:
        assert url.startswith("https://"), f"Expected https://, got: {url}"


# ──────────────────────────────────────
# (j) parse_detail 標題剝番號前綴
# ──────────────────────────────────────

def test_parse_detail_title_strip_fullwidth_space():
    """番號 + 全形空格前綴應被剝除"""
    html = """\
<html><head><title>TCD-332</title></head><body>
  <h3 class="post-title">TCD-332　恥辱の○秘映像</h3>
  <div id="video_id"><table><tr><td class="text">TCD-332</td></tr></table></div>
  <img id="video_jacket_img" src="//pics.dmm.co.jp/tcd332pl.jpg" />
</body></html>"""
    fields = parse_detail(html, "TCD-332")
    assert not fields["title"].startswith("TCD-332")
    assert "恥辱" in fields["title"]


def test_parse_detail_title_strip_dash_prefix():
    """番號 + ASCII dash 前綴應被剝除"""
    html = """\
<html><head><title>MIDE-800</title></head><body>
  <h3 class="post-title">MIDE-800 - 美しい女優</h3>
  <div id="video_id"><table><tr><td class="text">MIDE-800</td></tr></table></div>
  <img id="video_jacket_img" src="//pics.dmm.co.jp/mide800pl.jpg" />
</body></html>"""
    fields = parse_detail(html, "MIDE-800")
    assert not fields["title"].startswith("MIDE-800")
    assert "美しい" in fields["title"]


# ──────────────────────────────────────
# (k) _is_cf_challenge
# ──────────────────────────────────────

def test_is_cf_challenge_just_a_moment():
    assert _is_cf_challenge("Just a moment", "<html></html>") is True


def test_is_cf_challenge_chinese_title():
    assert _is_cf_challenge("請稍候", "<html></html>") is True


def test_is_cf_challenge_form_marker():
    assert _is_cf_challenge("JavLibrary", CF_CHALLENGE_HTML) is True


def test_is_cf_challenge_turnstile_response():
    html = '<html><body><input name="cf-turnstile-response"></body></html>'
    assert _is_cf_challenge("JavLibrary", html) is True


def test_is_cf_challenge_normal_page():
    assert _is_cf_challenge("JavLibrary", "<html><body>Normal page</body></html>") is False


# ──────────────────────────────────────
# (l) _is_age_gate
# ──────────────────────────────────────

def test_is_age_gate_riyoukiyaku():
    assert _is_age_gate("利用規約に同意してください") is True


def test_is_age_gate_agree_btn():
    assert _is_age_gate('<button id="agreeBtn">同意</button>') is True


def test_is_age_gate_over18():
    assert _is_age_gate('<a href="?over18=1">enter</a>') is True


def test_is_age_gate_normal_page():
    assert _is_age_gate("<html><body>Normal JavLibrary page</body></html>") is False


# ──────────────────────────────────────
# (m) _extract_detail_url multi-result
# ──────────────────────────────────────

def test_extract_detail_url_multi_result():
    base_lang_url = "https://www.javlibrary.com/ja"
    result = _extract_detail_url(MULTI_RESULT_HTML, "TCD-332", base_lang_url)
    assert result is not None
    assert result.startswith("https://www.javlibrary.com/ja/")
    assert "tcd332" in result.lower() or "javmezz" in result.lower()


def test_extract_detail_url_selects_exact_match():
    """番號精確比對應優先選出正確結果"""
    base_lang_url = "https://www.javlibrary.com/ja"
    result = _extract_detail_url(MULTI_RESULT_HTML, "TCD-332", base_lang_url)
    # 應選到第一個（精確比對 TCD-332），不是 OTHER-001
    assert result is not None
    assert "other" not in result.lower()


# ──────────────────────────────────────
# (n) _extract_detail_url 無結果
# ──────────────────────────────────────

def test_extract_detail_url_no_result():
    result = _extract_detail_url(NO_RESULT_HTML, "TCD-332", "https://www.javlibrary.com/ja")
    assert result is None


# ──────────────────────────────────────
# (o) _is_detail_page
# ──────────────────────────────────────

def test_is_detail_page_with_video_id():
    soup = BeautifulSoup(DETAIL_HTML, "html.parser")
    assert _is_detail_page(soup) is True


def test_is_detail_page_without_video_id():
    soup = BeautifulSoup(MULTI_RESULT_HTML, "html.parser")
    assert _is_detail_page(soup) is False


def test_is_detail_page_empty():
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    assert _is_detail_page(soup) is False
