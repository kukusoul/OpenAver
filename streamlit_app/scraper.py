"""DMM 番號搜尋 — 獨立版（無需 core 模組）"""

import re
import json
import time
import logging
import requests
import streamlit as st
from pathlib import Path
from typing import Optional
from lxml import etree
from abc import ABC, abstractmethod


# ================================================================
# 1. Data Models
# ================================================================

class Actress:
    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return f"Actress(name={self.name!r})"


class Video:
    def __init__(
        self,
        number: str,
        title: str = "",
        actresses: Optional[list[Actress]] = None,
        date: str = "",
        maker: str = "",
        cover_url: str = "",
        tags: Optional[list[str]] = None,
        source: str = "",
        detail_url: str = "",
        director: str = "",
        duration: Optional[int] = None,
        label: str = "",
        series: str = "",
        sample_images: Optional[list[str]] = None,
    ):
        self.number = number
        self.title = title
        self.actresses = actresses or []
        self.date = date
        self.maker = maker
        self.cover_url = cover_url
        self.tags = tags or []
        self.source = source
        self.detail_url = detail_url
        self.director = director
        self.duration = duration
        self.label = label
        self.series = series
        self.sample_images = sample_images or []


# ================================================================
# 2. Logger & Utilities
# ================================================================

_logger_initialized = False

def get_logger(name: str) -> logging.Logger:
    global _logger_initialized
    logger = logging.getLogger(f"OpenAver.{name}")
    if not _logger_initialized:
        logger.addHandler(logging.NullHandler())
        _logger_initialized = True
    return logger


def rate_limit(delay: float = 0.3) -> None:
    time.sleep(delay)


# ================================================================
# 3. Base Scraper
# ================================================================

class BaseScraper(ABC):
    def __init__(self, proxy_url: str = "", delay: float = 0.3):
        self.proxy_url = proxy_url
        self.delay = delay
        self.source_name = self._get_source_name()

    @abstractmethod
    def _get_source_name(self) -> str:
        pass

    @abstractmethod
    def search(self, number: str) -> Optional[Video]:
        pass

    def normalize_number(self, number: str) -> str:
        number = number.strip()
        number = re.sub(
            r'[-_](UC|UNCEN|UNCENSORED|LEAK|LEAKED)(?=[-_.\s]|$)',
            '', number, flags=re.IGNORECASE
        )
        number = number.upper()
        match = re.match(r'^([A-Z]+)(\d+)$', number)
        if match:
            return f"{match.group(1)}-{match.group(2)}"
        return number


# ================================================================
# 4. DMM Scraper
# ================================================================

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_FILE = PROJECT_ROOT / "dmm_content_ids.json"
PREFIX_FILE = PROJECT_ROOT / "dmm_prefix_hints.json"

_genres_supported: Optional[bool] = None
_sample_images_supported: Optional[bool] = None


class DMMScraper(BaseScraper):

    API_URL = "https://api.video.dmm.co.jp/graphql"

    DETAIL_QUERY = """
        query ContentPageData($id: ID!) {
            ppvContent(id: $id) {
                id
                title
                description
                packageImage { largeUrl }
                makerReleasedAt
                saleStartDate
                duration
                actresses { name }
                directors { name }
                series { name }
                maker { name }
                makerContentId
            }
        }
    """

    SEARCH_QUERY = """
        query AvSearch($limit: Int!, $sort: ContentSearchPPVSort!, $queryWord: String) {
            legacySearchPPV(limit: $limit, sort: $sort, queryWord: $queryWord) {
                result { contents { id } }
            }
        }
    """

    SEARCH_LIST_QUERY = """
        query AvSearch($limit: Int!, $offset: Int!, $sort: ContentSearchPPVSort!, $queryWord: String) {
            legacySearchPPV(limit: $limit, offset: $offset, sort: $sort, queryWord: $queryWord) {
                result {
                    contents {
                        id
                        title
                        packageImage { largeUrl }
                        actresses { name }
                        maker { name }
                    }
                }
            }
        }
    """

    SEARCH_DETAIL_QUERY = """
        query AvSearch($limit: Int!, $offset: Int!, $sort: ContentSearchPPVSort!, $queryWord: String) {
            legacySearchPPV(limit: $limit, offset: $offset, sort: $sort, queryWord: $queryWord) {
                result {
                    contents {
                        id
                        title
                        packageImage { largeUrl }
                        actresses { name }
                        maker { name }
                        makerReleasedAt
                        directors { name }
                        duration
                        series { name }
                    }
                }
            }
        }
    """

    GENRES_PROBE_QUERY = """
        query ProbeGenres($id: ID!) {
            ppvContent(id: $id) {
                genres { name }
                label { name }
            }
        }
    """

    SAMPLE_IMAGES_PROBE_QUERY = """
        query ProbeSampleImages($id: ID!) {
            ppvContent(id: $id) {
                sampleImages { imageUrl }
            }
        }
    """

    SCHEMA_ERROR_PATTERNS = ('Unknown field', 'Cannot query field')

    def __init__(
        self,
        proxy_url: str = "",
        delay: float = 0.3,
        user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        timeout: int = 15,
    ):
        super().__init__(proxy_url=proxy_url, delay=delay)
        self.user_agent = user_agent
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': self.user_agent,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })
        if self.proxy_url:
            self._session.proxies = {
                'http': self.proxy_url,
                'https': self.proxy_url,
            }
        else:
            self._session.trust_env = False

    def _get_source_name(self) -> str:
        return "dmm"

    # ---- probe ----

    def _probe_genres(self, content_id: str) -> tuple[list[str], str]:
        global _genres_supported
        if _genres_supported is False:
            return [], ''
        try:
            payload = {
                'query': self.GENRES_PROBE_QUERY,
                'variables': {'id': content_id}
            }
            resp = self._session.post(self.API_URL, json=payload, timeout=5)
            if resp.status_code != 200:
                return [], ''
            resp_json = resp.json()
            errors = resp_json.get('errors', [])
            if any(
                any(pat in (e.get('message', '') or '') for pat in self.SCHEMA_ERROR_PATTERNS)
                for e in errors
            ):
                _genres_supported = False
                return [], ''
            data = resp_json.get('data') or {}
            item = data.get('ppvContent')
            if item is None:
                return [], ''
            _genres_supported = True
            genres = item.get('genres') or []
            tags = [g['name'] for g in genres if g.get('name')]
            label = (item.get('label') or {}).get('name', '')
            return tags, label
        except Exception:
            return [], ''

    def _probe_sample_images(self, content_id: str) -> list[str]:
        global _sample_images_supported
        if _sample_images_supported is False:
            return []
        try:
            payload = {
                'query': self.SAMPLE_IMAGES_PROBE_QUERY,
                'variables': {'id': content_id}
            }
            resp = self._session.post(self.API_URL, json=payload, timeout=5)
            if resp.status_code != 200:
                return []
            resp_json = resp.json()
            errors = resp_json.get('errors', [])
            if any(
                any(pat in (e.get('message', '') or '') for pat in self.SCHEMA_ERROR_PATTERNS)
                for e in errors
            ):
                _sample_images_supported = False
                return []
            data = resp_json.get('data') or {}
            item = data.get('ppvContent')
            if item is None:
                return []
            _sample_images_supported = True
            raw_samples = item.get('sampleImages') or []
            return [re.sub(r'(?<!jp)-(\d+)\.jpg$', r'jp-\1.jpg', s['imageUrl']) for s in raw_samples if s.get('imageUrl')]
        except Exception:
            return []

    def _fetch_tags_from_html(self, content_id: str) -> list[str]:
        url = f"https://www.dmm.co.jp/digital/videoa/-/detail/=/cid={content_id}/"
        try:
            resp = self._session.get(
                url,
                timeout=self.timeout,
                cookies={"age_check_done": "1"}
            )
            if resp.status_code != 200:
                return []
            html = etree.fromstring(resp.content, etree.HTMLParser())
            for script in html.xpath('//script[@type="application/ld+json"]/text()'):
                try:
                    ld = json.loads(script)
                    if isinstance(ld, dict) and ld.get('@type') == 'VideoObject':
                        genre = ld.get('genre')
                        if genre and isinstance(genre, list):
                            return [g for g in genre if isinstance(g, str)]
                except json.JSONDecodeError:
                    continue
            tags = html.xpath(
                '//th[contains(.//text(),"ジャンル")]/following-sibling::td//a/text()'
            )
            return [t.strip() for t in tags if t.strip()]
        except Exception:
            return []

    # ---- cache ----

    def _load_json(self, path: Path) -> dict:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding='utf-8'))
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_json(self, path: Path, data: dict):
        try:
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
        except IOError:
            pass

    def _load_cache(self) -> dict:
        return self._load_json(CACHE_FILE)

    def _save_cache(self, number: str, content_id: str):
        cache = self._load_cache()
        cache[number.upper()] = content_id
        self._save_json(CACHE_FILE, cache)

    def _load_prefix_hints(self) -> dict:
        return self._load_json(PREFIX_FILE)

    def _save_prefix_hint(self, prefix: str, dmm_prefix: str):
        hints = self._load_prefix_hints()
        hints[prefix.lower()] = dmm_prefix
        self._save_json(PREFIX_FILE, hints)

    # ---- content_id conversion ----

    def _parse_number(self, number: str) -> tuple[str, str]:
        number = number.upper().strip()
        match = re.match(r'^([A-Z]+)-?(\d+)$', number)
        if match:
            return match.group(1).lower(), match.group(2)
        return "", ""

    def _convert_with_hints(self, number: str) -> list[str]:
        prefix, num = self._parse_number(number)
        if not prefix or not num:
            return []
        hints = self._load_prefix_hints()
        dmm_prefix = hints.get(prefix, "")
        candidates = []
        candidates.append(f"{dmm_prefix}{prefix}{num.zfill(5)}")
        candidates.append(f"{dmm_prefix}{prefix}{num}")
        if len(num) < 3:
            candidates.append(f"{dmm_prefix}{prefix}{num.zfill(3)}")
        seen = set()
        return [c for c in candidates if not (c in seen or seen.add(c))]

    def _learn_prefix(self, number: str, content_id: str):
        prefix, _ = self._parse_number(number)
        if not prefix:
            return
        idx = content_id.lower().find(prefix)
        if idx >= 0:
            dmm_prefix = content_id[:idx]
            if dmm_prefix:
                self._save_prefix_hint(prefix, dmm_prefix)

    def _result_matches_number(self, result: Video, number: str) -> bool:
        """用 DMM API 回傳的實際 product number 比對輸入番號"""
        _, input_num = self._parse_number(number)
        _, result_num = self._parse_number(result.number)
        if not input_num or not result_num:
            return True
        return input_num.lstrip('0') == result_num.lstrip('0')

    def _content_id_matches_number(self, content_id: str, number: str) -> bool:
        _, input_num = self._parse_number(number)
        if not input_num:
            return True
        m = re.search(r'(\d+)$', content_id)
        if not m:
            return True
        return m.group(1).lstrip('0') == input_num.lstrip('0')

    def _content_id_to_number(self, content_id: str) -> str:
        m = re.match(r'^(\d*)([a-z]+)(\d+)$', content_id.lower())
        if m:
            alpha = m.group(2).upper()
            num = m.group(3)
            stripped = num.lstrip('0') or '0'
            if len(stripped) < 3 and len(num) >= 3:
                stripped = num[-3:]
            elif len(stripped) < 2 and len(num) >= 2:
                stripped = num[-2:]
            return f"{alpha}-{stripped}"
        m2 = re.match(r'^[a-z0-9]+_([a-z]+)(\d+)$', content_id.lower())
        if m2:
            return f"{m2.group(1).upper()}-{m2.group(2)}"
        return content_id

    def _search_content_id(self, number: str) -> Optional[str]:
        result = self._search_content_with_data(number)
        return result[0] if result else None

    def _search_content_with_data(self, number: str) -> Optional[tuple[str, dict]]:
        query_word = number.upper().replace('-', '')
        prefix, num = self._parse_number(number)
        if not prefix:
            return None

        for query_tpl in [(self.SEARCH_DETAIL_QUERY, True), (self.SEARCH_LIST_QUERY, False)]:
            query_str = query_tpl[0]
            try:
                payload = {
                    'query': query_str,
                    'variables': {
                        'limit': 5,
                        'offset': 0,
                        'sort': 'RELEASE_DATE',
                        'queryWord': query_word
                    }
                }
                resp = self._session.post(self.API_URL, json=payload, timeout=10)

                if resp.status_code != 200:
                    continue

                data = resp.json()
                errors = data.get('errors', [])
                if errors and any(
                    any(pat in (e.get('message', '') or '') for pat in self.SCHEMA_ERROR_PATTERNS)
                    for e in errors
                ):
                    continue

                if not data.get('data') or not data['data'].get('legacySearchPPV'):
                    continue

                contents = data['data']['legacySearchPPV']['result']['contents']
                if not contents:
                    continue

                for content in contents:
                    cid = content['id']
                    if prefix in cid.lower():
                        m = re.search(r'(\d+)$', cid)
                        if m and m.group(1).lstrip('0') == num.lstrip('0'):
                            return cid, content

                continue

            except Exception:
                continue

        return None

    # ---- video construction ----

    def _build_video_from_search_data(self, content_id: str, search_data: dict, number_hint: str = '') -> Optional[Video]:
        try:
            number = number_hint if number_hint else self._content_id_to_number(content_id)
            actresses = [
                Actress(name=a['name'])
                for a in (search_data.get('actresses') or [])
                if a.get('name')
            ]
            date = (search_data.get('makerReleasedAt') or search_data.get('saleStartDate') or '')
            if date and 'T' in date:
                date = date.split('T')[0]
            directors_list = search_data.get('directors') or []
            director = directors_list[0]['name'] if directors_list else ''
            raw_duration = search_data.get('duration')
            duration = raw_duration // 60 if raw_duration is not None else None
            series = (search_data.get('series') or {}).get('name', '')

            video = Video(
                number=number,
                title=search_data.get('title', ''),
                actresses=actresses,
                maker=(search_data.get('maker') or {}).get('name', ''),
                cover_url=(search_data.get('packageImage') or {}).get('largeUrl', ''),
                date=date,
                director=director,
                duration=duration,
                series=series,
                source=self.source_name,
                detail_url=f"https://www.dmm.co.jp/digital/videoa/-/detail/=/cid={content_id}/",
            )
            return video
        except Exception:
            return None

    def _fetch_by_id(self, content_id: str) -> Optional[Video]:
        if not content_id:
            return None

        try:
            payload = {
                'query': self.DETAIL_QUERY,
                'variables': {'id': content_id}
            }

            response = self._session.post(
                self.API_URL,
                json=payload,
                timeout=self.timeout
            )

            if response.status_code != 200:
                return None

            data = response.json()

            if not data.get('data') or not data['data'].get('ppvContent'):
                return None

            item = data['data']['ppvContent']

            actresses = [
                Actress(name=a['name'])
                for a in (item.get('actresses') or [])
            ]

            release_date = (item.get('makerReleasedAt') or item.get('saleStartDate') or '')
            if release_date and 'T' in release_date:
                release_date = release_date.split('T')[0]

            tags, label = self._probe_genres(content_id)
            if not tags:
                tags = self._fetch_tags_from_html(content_id)

            sample_images = self._probe_sample_images(content_id)

            directors_list = item.get('directors') or []
            director = directors_list[0]['name'] if directors_list else ''

            raw_duration = item.get('duration')
            duration = raw_duration // 60 if raw_duration is not None else None

            series = (item.get('series') or {}).get('name', '')

            number = item.get('makerContentId') or self._content_id_to_number(content_id)

            video = Video(
                number=number,
                title=item.get('title', ''),
                actresses=actresses,
                date=release_date,
                maker=(item.get('maker') or {}).get('name', ''),
                cover_url=(item.get('packageImage') or {}).get('largeUrl', ''),
                tags=tags,
                source=self.source_name,
                detail_url=f"https://www.dmm.co.jp/digital/videoa/-/detail/=/cid={content_id}/",
                director=director,
                duration=duration,
                label=label,
                series=series,
                sample_images=sample_images,
            )

            return video

        except requests.Timeout:
            raise TimeoutError(f"DMM API timeout for {content_id}")
        except Exception:
            return None

    # ---- HTML helpers ----

    def _html_get(self, url: str, **kwargs) -> Optional[requests.Response]:
        try:
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
            }
            proxies = None
            if self.proxy_url:
                proxies = {'http': self.proxy_url, 'https': self.proxy_url}

            resp = requests.get(
                url, headers=headers, timeout=self.timeout,
                cookies={"age_check_done": "1"},
                proxies=proxies,
                **kwargs
            )
            if resp.status_code == 200:
                return resp
            return None
        except Exception:
            return None

    def _search_content_id_from_html(self, number: str) -> Optional[str]:
        for query in [number.lower().replace('-', ''), number.lower()]:
            url = f"https://video.dmm.co.jp/list/?key={query}"
            resp = self._html_get(url)
            if resp is None:
                continue

            m_url = re.search(r'av/content/\?id=([a-zA-Z0-9_]+)', resp.url)
            if m_url:
                return m_url.group(1)

            m = re.search(r'av/content/\?id=([a-zA-Z0-9_]+)', resp.text)
            if m:
                return m.group(1)

            for m_json in re.finditer(r'"(?:contentId|productId|cid)"\s*:\s*"([^"]+)"', resp.text):
                cid = m_json.group(1)
                if re.search(r'[a-z]', cid):
                    return cid
        return None

    @staticmethod
    def _next_data_search(obj: object, *keys: str) -> object:
        for key in keys:
            if isinstance(obj, dict) and key in obj:
                obj = obj[key]
            else:
                return None
        return obj

    @staticmethod
    def _next_data_find(obj: object, target_key: str) -> list[object]:
        results = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == target_key:
                    results.append(v)
                else:
                    results.extend(DMMScraper._next_data_find(v, target_key))
        elif isinstance(obj, list):
            for item in obj:
                results.extend(DMMScraper._next_data_find(item, target_key))
        return results

    def _fetch_from_video_html(self, content_id: str) -> Optional[Video]:
        import html as _html

        url = f"https://video.dmm.co.jp/av/content/?id={content_id}"
        resp = self._html_get(url)
        if resp is None:
            old_url = f"https://www.dmm.co.jp/digital/videoa/-/detail/=/cid={content_id}/"
            resp = self._html_get(old_url)
            if resp is None:
                return None
            url = old_url

        try:
            title = ''
            cover_url = ''
            tags = []
            actresses = []
            text = resp.text

            m_next = re.search(
                r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
                text, re.DOTALL
            )
            if m_next:
                try:
                    next_data = json.loads(_html.unescape(m_next.group(1).strip()))
                    page_props = self._next_data_search(next_data, 'props', 'pageProps')
                    if page_props:
                        candidates = self._next_data_find(page_props, 'title')
                        if candidates:
                            title = str(candidates[0])
                        candidates = self._next_data_find(page_props, 'coverUrl')
                        if not candidates:
                            candidates = self._next_data_find(page_props, 'cover')
                        if not candidates:
                            candidates = self._next_data_find(page_props, 'packageImage')
                        if candidates:
                            cv = candidates[0]
                            if isinstance(cv, str):
                                cover_url = cv
                            elif isinstance(cv, dict):
                                cover_url = cv.get('largeUrl', cv.get('url', ''))
                        candidates = self._next_data_find(page_props, 'actresses')
                        if not candidates:
                            candidates = self._next_data_find(page_props, 'actors')
                        if candidates:
                            for a in (candidates[0] if isinstance(candidates[0], list) else [candidates[0]]):
                                if isinstance(a, dict):
                                    actresses.append(Actress(name=a.get('name', '')))
                                elif isinstance(a, str):
                                    actresses.append(Actress(name=a))
                        candidates = self._next_data_find(page_props, 'genres')
                        if not candidates:
                            candidates = self._next_data_find(page_props, 'tags')
                        if candidates:
                            g = candidates[0]
                            if isinstance(g, list):
                                for item in g:
                                    if isinstance(item, dict):
                                        tags.append(item.get('name', ''))
                                    elif isinstance(item, str):
                                        tags.append(item)
                            elif isinstance(g, str):
                                tags = [g]
                except (json.JSONDecodeError, Exception):
                    pass

            if not title:
                for m_ld in re.finditer(
                    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                    text, re.DOTALL
                ):
                    raw = _html.unescape(m_ld.group(1).strip())
                    try:
                        ld = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    for item in (ld if isinstance(ld, list) else [ld]):
                        if isinstance(item, dict) and item.get('@type') in ('VideoObject', 'Product'):
                            title = item.get('name', '') or ''
                            image = item.get('image') or ''
                            if isinstance(image, str):
                                cover_url = image
                            elif isinstance(image, dict):
                                cover_url = image.get('url', '')
                            genre = item.get('genre') or []
                            tags = genre if isinstance(genre, list) else [genre] if genre else []
                            break
                    if title:
                        break

            if not title:
                m_t = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', text)
                if m_t:
                    title = _html.unescape(m_t.group(1))
                m_c = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', text)
                if m_c:
                    cover_url = m_c.group(1)

            if not title:
                m_t = re.search(r'<title>([^<]+)</title>', text)
                if m_t:
                    title = _html.unescape(m_t.group(1).strip())

            if not title:
                m_t = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', text)
                if m_t:
                    title = _html.unescape(m_t.group(1))

            if not title and not cover_url:
                return None

            number = self._content_id_to_number(content_id)

            video = Video(
                number=number,
                title=title,
                actresses=actresses,
                cover_url=cover_url,
                tags=tags,
                source=self.source_name,
                detail_url=url,
            )
            return video

        except Exception:
            return None

    # ---- main search ----

    def search(self, number: str) -> Optional[Video]:
        number = self.normalize_number(number)
        number_upper = number.upper()

        if 'FC2' in number_upper:
            return None

        # 1. cache
        cache = self._load_cache()
        if number_upper in cache:
            cached_cid = cache[number_upper]
            result = self._fetch_by_id(cached_cid)
            if result:
                if self._result_matches_number(result, number):
                    rate_limit(self.delay)
                    return result
                cache.pop(number_upper, None)
                self._save_json(CACHE_FILE, cache)

        # 2. prefix hints
        for cid in self._convert_with_hints(number):
            if not cid:
                continue
            result = self._fetch_by_id(cid)
            if result and self._result_matches_number(result, number):
                self._save_cache(number, cid)
                rate_limit(self.delay)
                return result

        # 3. search API
        search_result = self._search_content_with_data(number)
        discovered_cid = search_result[0] if search_result else None
        if discovered_cid and self._content_id_matches_number(discovered_cid, number):
            result = self._fetch_by_id(discovered_cid)
            if not result and search_result:
                result = self._build_video_from_search_data(discovered_cid, search_result[1], number_hint=number)
            if result and self._result_matches_number(result, number):
                self._save_cache(number, discovered_cid)
                self._learn_prefix(number, discovered_cid)
                rate_limit(self.delay)
                return result

        # 4. HTML fallback
        html_cid = self._search_content_id_from_html(number)
        if html_cid and self._content_id_matches_number(html_cid, number):
            result = self._fetch_by_id(html_cid)
            if not result:
                result = self._fetch_from_video_html(html_cid)
            if result and self._result_matches_number(result, number):
                self._save_cache(number, html_cid)
                self._learn_prefix(number, html_cid)
                rate_limit(self.delay)
                return result

        return None

    # ---- keyword search (unused by search.py but needed for interface) ----

    def search_by_keyword(self, keyword: str, limit: int = 20, offset: int = 0) -> list[Video]:
        return []


# ================================================================
# 5. Streamlit UI
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
