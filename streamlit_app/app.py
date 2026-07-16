"""
Streamlit Video Browser — Javbus 風格影片瀏覽器

支援 WSL2，可輸入 Windows 路徑或 WSL Linux 路徑。
點選卡片進入詳細頁，可查看 extrafanart 劇照並編輯 NFO。

用法：
    pip install streamlit
    streamlit run app.py
"""

import base64
import html
import os
import platform
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import streamlit as st

st.set_page_config(page_title="Video Browser", layout="wide")

# ── WSL ────────────────────────────────────────────────────────────────

def _detect_wsl() -> bool:
    if platform.system() != 'Linux':
        return False
    try:
        with open('/proc/version') as f:
            return 'microsoft' in f.read().lower()
    except Exception:
        return False

IN_WSL = _detect_wsl()

def to_wsl_path(path: str) -> str:
    if not path:
        return path
    if path.startswith('/'):
        return path
    if path.startswith('\\\\wsl.localhost\\') or path.startswith('\\\\wsl$\\'):
        path = path.replace('\\\\wsl.localhost\\', '').replace('\\\\wsl$\\', '')
        parts = path.split('\\', 1)
        if len(parts) > 1:
            return '/' + parts[1].replace('\\', '/')
        return '/'
    if len(path) >= 2 and path[1] == ':':
        drive = path[0].lower()
        rest = path[2:].rstrip('\\').replace('\\', '/')
        return f'/mnt/{drive}{rest}' if rest else f'/mnt/{drive}'
    if path.startswith('/mnt/'):
        return path
    return path.replace('\\', '/')

def to_windows_file_uri(path: str) -> str:
    abs_path = path.replace('\\', '/')
    m = re.match(r'^/mnt/([a-z])(/.*)?$', abs_path)
    if m:
        return f"file:///{m.group(1).upper()}:{m.group(2) or ''}"
    if abs_path.startswith('/'):
        return f"file:///wsl.localhost/Ubuntu{abs_path}"
    return f"file:///{abs_path}"

# ── NFO helpers ────────────────────────────────────────────────────────

CDATA_RE = re.compile(rb'<!\[CDATA\[.*?\]\]>', re.DOTALL)
BARE_AMP_RE = re.compile(
    rb'&(?!(?:amp|lt|gt|quot|apos);|#(?:\d+|x[0-9a-fA-F]+);)'
)

def sanitize_nfo_bytes(raw: bytes) -> bytes:
    if b'<![CDATA[' not in raw:
        return BARE_AMP_RE.sub(b'&amp;', raw)
    result = []
    last = 0
    for m in CDATA_RE.finditer(raw):
        result.append(BARE_AMP_RE.sub(b'&amp;', raw[last:m.start()]))
        result.append(m.group())
        last = m.end()
    result.append(BARE_AMP_RE.sub(b'&amp;', raw[last:]))
    return b''.join(result)

@dataclass
class VideoInfo:
    nfo_path: str = ""
    title: str = ""
    originaltitle: str = ""
    actor: str = ""
    num: str = ""
    maker: str = ""
    date: str = ""
    genre: str = ""
    label: str = ""
    series: str = ""
    director: str = ""
    duration: Optional[int] = None
    img: str = ""
    extrafanart: List[str] = None

    def __post_init__(self):
        if self.extrafanart is None:
            self.extrafanart = []

    @property
    def display_title(self) -> str:
        return self.originaltitle or self.title or ""

# ── NFO read ───────────────────────────────────────────────────────────

FIELD_ALIASES = {
    "title": ["title"],
    "originaltitle": ["originaltitle"],
    "num": ["num", "id"],
    "maker": ["maker", "studio"],
    "date": ["release", "premiered", "year"],
    "director": ["director"],
    "series": ["set/name"],
    "label": ["label"],
    "runtime": ["runtime"],
}

def _find_text(root: ET.Element, tags: List[str]) -> str:
    for tag in tags:
        e = root.find(tag)
        if e is not None and e.text:
            return e.text.strip()
    return ""

def parse_nfo(nfo_path: str) -> Optional[VideoInfo]:
    try:
        raw = Path(nfo_path).read_bytes()
        raw = sanitize_nfo_bytes(raw)
        root = ET.fromstring(raw)
        info = VideoInfo(nfo_path=nfo_path)
        info.title = _find_text(root, FIELD_ALIASES["title"])
        info.originaltitle = _find_text(root, FIELD_ALIASES["originaltitle"])
        info.num = _find_text(root, FIELD_ALIASES["num"])
        info.maker = _find_text(root, FIELD_ALIASES["maker"])
        info.date = _find_text(root, FIELD_ALIASES["date"])
        info.director = _find_text(root, FIELD_ALIASES["director"])
        info.series = _find_text(root, FIELD_ALIASES["series"])
        info.label = _find_text(root, FIELD_ALIASES["label"])

        rt = _find_text(root, FIELD_ALIASES["runtime"])
        if rt:
            try:
                info.duration = int(rt)
            except ValueError:
                info.duration = None

        actors = []
        for e in root.findall('.//actor/name'):
            if e.text:
                actors.append(e.text.strip())
        info.actor = ','.join(actors)

        genres = []
        for e in root.findall('genre'):
            if e.text:
                genres.append(e.text.strip())
        for e in root.findall('tag'):
            if e.text and e.text.strip() not in genres:
                genres.append(e.text.strip())
        info.genre = ','.join(genres)

        thumb = root.find('thumb')
        if thumb is not None and thumb.text:
            info.img = thumb.text.strip()

        return info
    except Exception:
        return None

# ── NFO write ──────────────────────────────────────────────────────────

def _set_text(root: ET.Element, tags: List[str], value: str):
    for tag in tags:
        e = root.find(tag)
        if e is not None:
            e.text = value if value else None
            return
    if value:
        ET.SubElement(root, tags[0]).text = value

def _remove_all(root: ET.Element, tag: str):
    for e in list(root.findall(tag)):
        root.remove(e)

def save_nfo(info: VideoInfo) -> bool:
    try:
        raw = Path(info.nfo_path).read_bytes()
        raw = sanitize_nfo_bytes(raw)
        root = ET.fromstring(raw)

        _set_text(root, FIELD_ALIASES["title"], info.title)
        _set_text(root, FIELD_ALIASES["originaltitle"], info.originaltitle)
        _set_text(root, FIELD_ALIASES["num"], info.num)
        _set_text(root, FIELD_ALIASES["maker"], info.maker)
        _set_text(root, FIELD_ALIASES["date"], info.date)
        _set_text(root, FIELD_ALIASES["director"], info.director)
        _set_text(root, FIELD_ALIASES["label"], info.label)
        _set_text(root, FIELD_ALIASES["runtime"],
                  str(info.duration) if info.duration else "")

        if info.series:
            set_elem = root.find('set')
            if set_elem is None:
                set_elem = ET.SubElement(root, 'set')
            name_elem = set_elem.find('name')
            if name_elem is None:
                name_elem = ET.SubElement(set_elem, 'name')
            name_elem.text = info.series
        else:
            set_elem = root.find('set')
            if set_elem is not None:
                root.remove(set_elem)

        _remove_all(root, 'actor')
        if info.actor:
            for name in (n.strip() for n in info.actor.split(',') if n.strip()):
                actor_elem = ET.SubElement(root, 'actor')
                ET.SubElement(actor_elem, 'name').text = name

        _remove_all(root, 'genre')
        if info.genre:
            for g in (g.strip() for g in info.genre.split(',') if g.strip()):
                ET.SubElement(root, 'genre').text = g

        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(info.nfo_path, encoding='utf-8', xml_declaration=True)
        return True
    except Exception:
        return False

# ── scanning ───────────────────────────────────────────────────────────

def find_nfo_files(root_dir: str) -> List[str]:
    nfo_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if fname.lower().endswith('.nfo'):
                nfo_files.append(os.path.join(dirpath, fname))
    return sorted(nfo_files)

def find_cover(nfo_path: str) -> str:
    nfo_dir = os.path.dirname(nfo_path)
    stem = os.path.splitext(os.path.basename(nfo_path))[0]
    for ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
        candidate = os.path.join(nfo_dir, f'{stem}{ext}')
        if os.path.isfile(candidate):
            return candidate
    for fname in sorted(os.listdir(nfo_dir)):
        if fname.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
            return os.path.join(nfo_dir, fname)
    return ""

def find_extrafanart(nfo_dir: str) -> List[str]:
    ef_dir = os.path.join(nfo_dir, 'extrafanart')
    if not os.path.isdir(ef_dir):
        return []
    images = []
    for fname in sorted(os.listdir(ef_dir)):
        if fname.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
            images.append(os.path.join(ef_dir, fname))
    return images

def find_video_file(nfo_path: str) -> str:
    nfo_dir = os.path.dirname(nfo_path)
    for fname in sorted(os.listdir(nfo_dir)):
        ext = os.path.splitext(fname)[1].lower()
        if ext in ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'):
            return os.path.join(nfo_dir, fname)
    return ""

def load_all_videos(root_dir: str, progress_bar=None, status_text=None) -> List[VideoInfo]:
    nfo_files = find_nfo_files(root_dir)
    videos: List[VideoInfo] = []
    total = len(nfo_files)

    for i, nfo_path in enumerate(nfo_files):
        if progress_bar is not None and total > 0:
            progress_bar.progress((i + 1) / total)
        if status_text is not None:
            status_text.text(f"Scanning {i + 1}/{total}")

        info = parse_nfo(nfo_path)
        if info is None:
            continue

        cover = find_cover(nfo_path)
        info.img = cover

        ef = find_extrafanart(os.path.dirname(nfo_path))
        info.extrafanart = ef

        videos.append(info)

    return videos

# ── render ─────────────────────────────────────────────────────────────

GRID_CSS = """
<style>
.cover-img {
    width: 100%;
    aspect-ratio: 16/9;
    object-fit: cover;
    display: block;
    border-radius: 4px;
}
.cover-missing {
    width: 100%;
    aspect-ratio: 16/9;
    background: #f0f0f0;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #bbb;
    font-size: 24px;
    border-radius: 4px;
}
.card-text {
    padding: 2px 2px 4px;
}
.card-text .title {
    font-size: .8em;
    color: #333;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.card-text .actor {
    font-size: .75em;
    color: #888;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
/* 扁長番號按鈕 */
div[data-testid="column"] div[data-testid="stButton"] {
    margin: 4px 0;
}
div[data-testid="column"] div[data-testid="stButton"] button {
    background: #e74c3c !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 4px !important;
    padding: 4px 8px !important;
    min-height: 0 !important;
    height: auto !important;
    font-size: .85em !important;
    font-weight: 700 !important;
    color: #fff !important;
    cursor: pointer !important;
    line-height: 1.4 !important;
    text-align: center !important;
    width: 100% !important;
    display: block !important;
    letter-spacing: .5px !important;
}
div[data-testid="column"] div[data-testid="stButton"] button:hover {
    background: #c0392b !important;
    color: #fff !important;
}
</style>
"""

@st.cache_data(show_spinner=False)
def _img_data_uri(path: str) -> str:
    if not path or not os.path.isfile(path):
        return ""
    with open(path, 'rb') as f:
        data = f.read()
    ext = os.path.splitext(path)[1].lower()
    mime = {'.jpg': 'jpeg', '.jpeg': 'jpeg', '.png': 'png', '.gif': 'gif', '.webp': 'webp'}.get(ext, 'jpeg')
    return f'data:image/{mime};base64,' + base64.b64encode(data).decode('ascii')

def render_grid(videos: List[VideoInfo], start: int, end: int):
    st.markdown(GRID_CSS, unsafe_allow_html=True)
    cols = st.columns(5)
    for i in range(start, min(end, len(videos))):
        v = videos[i]
        with cols[(i - start) % 5]:
            data_uri = _img_data_uri(v.img) if v.img else ""
            img_html = f'<img class="cover-img" src="{data_uri}" alt="cover">' if data_uri \
                       else '<div class="cover-missing">?</div>'

            st.markdown(img_html, unsafe_allow_html=True)

            if st.button(v.num or "▶", key=f"card_{i}", width='stretch'):
                st.session_state.detail_idx = i
                st.session_state.page = "detail"
                st.rerun()

            st.markdown(
                f'''<div class="card-text">
                <div class="title">{html.escape(v.display_title)}</div>
                <div class="actor">{html.escape(v.actor or "")}</div>
                </div>''',
                unsafe_allow_html=True,
            )

def render_detail(v: VideoInfo):
    if st.button("← Back to results"):
        st.session_state.page = "grid"
        st.rerun()

    st.markdown(f"## {v.num} — {v.display_title}")

    c1, c2 = st.columns([1, 1.5])
    with c1:
        if v.img and os.path.isfile(v.img):
            st.image(v.img, width='stretch')
        else:
            st.markdown("<div style='height:300px;background:#eee;display:flex;align-items:center;justify-content:center;color:#999'>No Cover</div>", unsafe_allow_html=True)

        video_path = find_video_file(v.nfo_path)
        if video_path:
            href = to_windows_file_uri(video_path) if IN_WSL else f"file://{video_path}"
            st.markdown(
                f'<a href="{href}" target="_blank" '
                f'style="display:block;text-align:center;padding:8px;background:#e74c3c;color:#fff;'
                f'text-decoration:none;border-radius:4px;margin-top:8px">▶ Play Video</a>',
                unsafe_allow_html=True,
            )

    with c2:
        edit_mode = st.session_state.get("edit_mode", False)

        rows = [
            ("番號", v.num, "num"),
            ("片名", v.title, "title"),
            ("原始片名", v.originaltitle, "originaltitle"),
            ("主演", v.actor, "actor"),
            ("片商", v.maker, "maker"),
            ("發行日期", v.date, "date"),
            ("類型", v.genre, "genre"),
            ("系列", v.series, "series"),
            ("標籤", v.label, "label"),
            ("導演", v.director, "director"),
            ("時長", f"{v.duration // 60}:{v.duration % 60:02d}" if v.duration else "", "duration"),
        ]

        if edit_mode:
            with st.form(key="edit_detail_form"):
                field_values = {}
                for label, val, key in rows:
                    col_a, col_b = st.columns([1, 2])
                    with col_a:
                        st.markdown(f'<div style="padding:4px 8px;font-weight:700;color:#555;border-bottom:1px solid #eee">{label}</div>', unsafe_allow_html=True)
                    with col_b:
                        field_values[key] = st.text_input(label, value=val or "", key=f"ef_{key}", label_visibility="collapsed")

                saved = st.form_submit_button("💾 Save", type="primary", width='stretch')

            if st.button("✖ Cancel", width='stretch'):
                st.session_state.edit_mode = False
                st.rerun()

            if saved:
                v.num = field_values["num"]
                v.title = field_values["title"]
                v.originaltitle = field_values["originaltitle"]
                v.actor = field_values["actor"]
                v.maker = field_values["maker"]
                v.date = field_values["date"]
                v.genre = field_values["genre"]
                v.series = field_values["series"]
                v.label = field_values["label"]
                v.director = field_values["director"]
                try:
                    v.duration = int(field_values["duration"]) if field_values["duration"].strip() else None
                except ValueError:
                    v.duration = None

                if save_nfo(v):
                    st.success("NFO saved!")
                    st.session_state.edit_mode = False
                    st.rerun()
                else:
                    st.error("Save failed")
        else:
            html_tbl = '<table style="width:100%;border-collapse:collapse">'
            for label, val, _key in rows:
                html_tbl += (
                    f'<tr><td style="padding:4px 8px;font-weight:700;color:#555;'
                    f'white-space:nowrap;border-bottom:1px solid #eee">{label}</td>'
                    f'<td style="padding:4px 8px;border-bottom:1px solid #eee">'
                    f'{html.escape(val) if val else ""}</td></tr>'
                )
            html_tbl += '</table>'
            st.markdown(html_tbl, unsafe_allow_html=True)

            if st.button("✏ Edit", width='stretch'):
                st.session_state.edit_mode = True
                st.rerun()

    if v.extrafanart:
        st.markdown("### Extrafanart")
        ef_cols = st.columns(6)
        for i, img_path in enumerate(v.extrafanart):
            with ef_cols[i % 6]:
                st.image(img_path, width='stretch')

# ── main ───────────────────────────────────────────────────────────────

def main():
    for key, default in [("root_dir_raw", ""), ("scanned", False),
                          ("page", "grid"), ("detail_idx", 0), ("edit_mode", False)]:
        if key not in st.session_state:
            st.session_state[key] = default

    with st.sidebar:
        st.header("Settings")
        root_dir_raw = st.text_input(
            "Root directory",
            value=st.session_state.root_dir_raw,
            placeholder=r"\\wsl.localhost\Ubuntu\...",
            key="root_dir_input",
        )
        st.session_state.root_dir_raw = root_dir_raw

        if IN_WSL and root_dir_raw:
            root_dir = to_wsl_path(root_dir_raw)
            if root_dir != root_dir_raw:
                st.caption(f"→ `{root_dir}`")
        else:
            root_dir = root_dir_raw

        scan_btn = st.button("Scan", type="primary")
        st.divider()

        st.header("Filters")
        search_query = st.text_input("Search", placeholder="title / num / actor…")
        col1, col2 = st.columns(2)
        with col1:
            min_date = st.text_input("Min date")
        with col2:
            max_date = st.text_input("Max date")

        makers_available = st.session_state.get("makers", [])
        genres_available = st.session_state.get("genres", [])
        actors_available = st.session_state.get("actors", [])
        labels_available = st.session_state.get("labels", [])
        series_available = st.session_state.get("series_list", [])

        selected_makers = st.multiselect("Maker", makers_available)
        selected_genres = st.multiselect("Genre", genres_available)
        selected_actors = st.multiselect("Actor", actors_available)
        selected_labels = st.multiselect("Label", labels_available)
        selected_series = st.multiselect("Series", series_available)

        per_page = st.select_slider("Per page", options=[30, 60, 90, 120, 240], value=60)

    if not root_dir or not os.path.isdir(root_dir):
        st.info("Enter a valid root directory and click **Scan**.")
        return

    if scan_btn or not st.session_state.scanned:
        with st.spinner("Scanning NFO files…"):
            progress = st.progress(0)
            status = st.empty()
            videos = load_all_videos(root_dir, progress, status)
            st.session_state.videos = videos
            st.session_state.makers = sorted({v.maker for v in videos if v.maker})
            st.session_state.genres = sorted({g for v in videos for g in v.genre.split(',') if g})
            st.session_state.actors = sorted({a for v in videos for a in v.actor.split(',') if a})
            st.session_state.labels = sorted({v.label for v in videos if v.label})
            st.session_state.series_list = sorted({v.series for v in videos if v.series})
            st.session_state.scanned = True
            st.session_state.page = "grid"
            status.empty()
            progress.empty()

    videos = st.session_state.get("videos", [])
    if not videos:
        st.warning("No NFO files found.")
        return

    # Filter
    filtered = videos[:]
    if search_query:
        q = search_query.lower().strip()
        filtered = [v for v in filtered
                    if q in v.title.lower() or q in v.originaltitle.lower()
                    or q in v.num.lower() or q in v.actor.lower()
                    or q in v.maker.lower() or q in v.genre.lower()
                    or q in v.series.lower()]
    if selected_makers:
        filtered = [v for v in filtered if v.maker in selected_makers]
    if selected_genres:
        filtered = [v for v in filtered if any(g in selected_genres for g in v.genre.split(','))]
    if selected_actors:
        filtered = [v for v in filtered if any(a in selected_actors for a in v.actor.split(','))]
    if selected_labels:
        filtered = [v for v in filtered if v.label in selected_labels]
    if selected_series:
        filtered = [v for v in filtered if v.series in selected_series]
    if min_date:
        filtered = [v for v in filtered if v.date >= min_date]
    if max_date:
        filtered = [v for v in filtered if v.date <= max_date]

    # Page routing
    if st.session_state.page == "detail":
        idx = st.session_state.detail_idx
        if 0 <= idx < len(filtered):
            render_detail(filtered[idx])
        else:
            st.session_state.page = "grid"
        return

    # Grid view
    total_pages = max(1, (len(filtered) + per_page - 1) // per_page)
    page = st.sidebar.number_input("Page", min_value=1, max_value=total_pages, value=1)
    start = (page - 1) * per_page
    end = start + per_page

    st.markdown(f"**{len(filtered)}** videos found  (page {page}/{total_pages})")
    render_grid(filtered, start, end)

if __name__ == "__main__":
    main()
