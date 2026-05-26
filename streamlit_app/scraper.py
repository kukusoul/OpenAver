"""DMM 番號搜尋 — Streamlit UI，核心邏輯委託 core.scrapers.dmm"""

import json
import re
import sys
import time
from pathlib import Path

import requests
import streamlit as st
from lxml import etree

# 確保 project root 在 sys.path 中（讓 streamlit run 能找到 core 模組）
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.scrapers import DMMScraper, Video, Actress
from core.scrapers.dmm import CACHE_FILE, PREFIX_FILE


# ================================================================
# Streamlit UI
# ================================================================

st.set_page_config(page_title="DMM Search", layout="wide")

st.markdown("# DMM 番號搜尋")
st.markdown("輸入番號查詢 DMM AV 資料庫，顯示影片資訊、封面與劇照。")

proxy_url = st.text_input(
    "Proxy URL（日本 IP 必填，例如 `http://127.0.0.1:7890`）",
    value=st.session_state.get("dmm_proxy", ""),
    placeholder="留空 = 直連（需日本 IP）",
    key="dmm_proxy_input",
)
st.session_state.dmm_proxy = proxy_url

with st.form("search_form", border=False):
    cols = st.columns([4, 1])
    with cols[0]:
        query = st.text_input(
            "番號",
            placeholder="例：SONE-205, STARS-804",
            label_visibility="collapsed",
        )
    with cols[1]:
        searched = st.form_submit_button("Search", type="primary", use_container_width=True)

if not searched and "dmm_result" not in st.session_state:
    st.info("請輸入番號後按下 Search 按鈕。")
    st.stop()

if searched and not query.strip():
    st.warning("請輸入番號")
    st.stop()

if searched:
    debug_lines = []
    number = query.strip()
    with st.spinner(f"正在從 DMM 查詢 {number.upper()} ..."):
        scraper = DMMScraper(proxy_url=proxy_url)

        # ── 診斷區 ──
        n = scraper.normalize_number(number)
        debug_lines.append(f"**normalize_number**: `{number}` → `{n}`")

        candidates = scraper._convert_with_hints(n)
        debug_lines.append(f"**Step 2 candidates**: {candidates}")
        for cid in candidates:
            if not cid:
                continue
            r = scraper._fetch_by_id(cid)
            debug_lines.append(f"  `_fetch_by_id({cid})` → {'OK' if r else 'None'}")

        cid3 = None
        search3 = scraper._search_content_with_data(n)
        if search3:
            cid3, data3 = search3
            debug_lines.append(f"**Step 3 search**: content_id=`{cid3}`")
            debug_lines.append(f"  search data ALL keys: {list(data3.keys())}")
            for k, v in data3.items():
                debug_lines.append(f"    {k}: {type(v).__name__} = {str(v)[:120]}")
            try:
                result3 = scraper._fetch_by_id(cid3)
                if result3:
                    debug_lines.append(f"  `_fetch_by_id` → OK (title={result3.title})")
                else:
                    debug_lines.append(f"  `_fetch_by_id` → None")
                    payload = {'query': scraper.DETAIL_QUERY, 'variables': {'id': cid3}}
                    sr = scraper._session.post(scraper.API_URL, json=payload, timeout=10)
                    debug_lines.append(f"  session post status: {sr.status_code}")
                    if sr.status_code == 200:
                        sj = sr.json()
                        debug_lines.append(f"  response keys: {list(sj.keys())}")
                        debug_lines.append(f"  errors: {sj.get('errors')}")
                        ppv = sj.get('data', {}).get('ppvContent')
                        debug_lines.append(f"  ppvContent: {str(ppv)[:200] if ppv else 'None/null'}")
            except Exception as e:
                debug_lines.append(f"  `_fetch_by_id` → EXCEPTION: {type(e).__name__}: {e}")
            result3 = scraper._build_video_from_search_data(cid3, data3, number_hint=n)
            debug_lines.append(f"  `_build_video_from_search_data` → {'OK' if result3 else 'None'}")
            if result3:
                debug_lines.append(f"    title={result3.title}, cover_url={result3.cover_url[:80]}...")
                debug_lines.append(f"    date={result3.date}, director={result3.director}")
                debug_lines.append(f"    duration={result3.duration}, series={result3.series}")
        else:
            debug_lines.append(f"**Step 3 search**: None")

        if cid3:
            q = "{ ppvContent(id: \"" + cid3 + "\") { makerReleasedAt saleStartDate } }"
            try:
                r = requests.post(
                    scraper.API_URL, json={'query': q},
                    headers={'User-Agent': scraper.config.user_agent, 'Content-Type': 'application/json', 'Accept': 'application/json'},
                    timeout=8
                )
                d = r.json() if r.text else {}
                data = d.get('data', {}).get('ppvContent')
                if data:
                    debug_lines.append(f"**Date probe**: makerReleasedAt={data.get('makerReleasedAt')}, saleStartDate={data.get('saleStartDate')}")
            except Exception as e:
                debug_lines.append(f"**Date probe**: ERROR {e}")

        result = scraper.search(number)

    if result:
        st.session_state.dmm_result = result
    else:
        st.error(f"找不到 {number.upper()} 的資料")
        st.session_state.pop("dmm_result", None)
        st.stop()

    st.session_state.debug_info = "\n".join(debug_lines)

if st.session_state.get("debug_info"):
    with st.expander("🔍 診斷資訊", expanded=True):
        st.code(st.session_state.debug_info, language="text")

result = st.session_state.get("dmm_result")
if result is None:
    st.stop()

st.divider()

c1, c2 = st.columns([1, 1.5])
with c1:
    if result.cover_url:
        st.image(result.cover_url, width="stretch")
    else:
        st.markdown(
            "<div style='height:300px;background:#eee;display:flex;"
            "align-items:center;justify-content:center;color:#999'>No Cover</div>",
            unsafe_allow_html=True,
        )

with c2:
    st.markdown(f"### {result.number} — {result.title}")
    rows = [
        ("番號", result.number),
        ("片名", result.title),
        ("主演", ", ".join(a.name for a in result.actresses)),
        ("片商", result.maker),
        ("發行日期", result.date),
        ("導演", result.director),
        ("時長", f"{result.duration} 分鐘" if result.duration else ""),
        ("系列", result.series),
        ("標籤", result.label),
        ("類型", ", ".join(result.tags) if result.tags else ""),
    ]
    html_tbl = '<table style="width:100%;border-collapse:collapse">'
    for label, val in rows:
        html_tbl += (
            f'<tr><td style="padding:4px 8px;font-weight:700;color:#555;'
            f'white-space:nowrap;border-bottom:1px solid #eee;width:100px">'
            f'{label}</td>'
            f'<td style="padding:4px 8px;border-bottom:1px solid #eee">'
            f'{val if val else ""}</td></tr>'
        )
    html_tbl += "</table>"
    st.markdown(html_tbl, unsafe_allow_html=True)

    if result.detail_url:
        st.markdown(
            f'<a href="{result.detail_url}" target="_blank" '
            f'style="display:inline-block;margin-top:12px;padding:8px 16px;'
            f'background:#e74c3c;color:#fff;text-decoration:none;border-radius:4px">'
            f"View on DMM</a>",
            unsafe_allow_html=True,
        )

if result.sample_images:
    st.markdown("### 劇照")
    thumbs = result.sample_images[:20]
    cols = st.columns(min(5, len(thumbs)))
    for i, img_url in enumerate(thumbs):
        with cols[i % 5]:
            st.image(img_url, width="stretch")
