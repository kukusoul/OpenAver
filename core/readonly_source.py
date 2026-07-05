"""
唯讀來源判定 — 純資料流層（無 IO、無 load_config、無 UI 文案）。

供 (a) scraper `_readonly_source_error`（單檔端點 guard）與 (b) showcase video
payload 的 `is_readonly_source` 旗標共用同一段比對邏輯（CD-90b-9 Codex 修正）。

模組定位：leaf-consumer，同時 import `iter_gallery_sources`（core.config）+
`coerce_to_file_uri`/`is_path_under_dir`（core.path_utils）。config 與 path_utils
互不 import、亦不 import 本模組 → 無循環。
"""

from core.config import iter_gallery_sources
from core.path_utils import coerce_to_file_uri, is_path_under_dir


def is_path_readonly(file_uri: str, readonly_prefixes, writable_prefixes=None) -> bool:
    """純比對、無 IO：file_uri 落在唯讀前綴下 **且不落任一可寫前綴** → True。

    可寫來源巢狀在唯讀夾之下時（唯讀 D:/media + 可寫 D:/media/local），可寫子夾的片
    同落唯讀前綴，但它屬可寫來源、不該被標唯讀 / 擋寫入。可寫前綴 override（PR #93
    Codex P2；語意對齊 switch_external_manager 的 writable_prefixes 扣除）。

    file_uri / readonly_prefixes / writable_prefixes 皆須為呼叫端已 coerce 的 file:/// URI。
    writable_prefixes 預設 None → 退回「純唯讀前綴比對」的舊行為（相容既有呼叫）。
    """
    if not any(is_path_under_dir(file_uri, prefix) for prefix in readonly_prefixes):
        return False
    return not any(is_path_under_dir(file_uri, wp) for wp in (writable_prefixes or []))


def readonly_source_prefixes(gallery_config, path_mappings) -> list:
    """枚舉唯讀來源、coerce 成 file:/// URI 前綴集（每 request 算一次）。

    iter_gallery_sources → 過濾 s.readonly and s.path → coerce_to_file_uri(s.path, mappings)；
    coerce 拋 ValueError 的髒來源 skip（mirror showcase _get_configured_dirs）。
    """
    prefixes = []
    for source in iter_gallery_sources(gallery_config):
        if not source.readonly or not source.path:
            continue
        try:
            prefixes.append(coerce_to_file_uri(source.path, path_mappings))
        except ValueError:
            continue
    return prefixes


def writable_source_prefixes(gallery_config, path_mappings) -> list:
    """枚舉可寫（非唯讀）來源、coerce 成 file:/// URI 前綴集（每 request 算一次）。

    供 is_path_readonly 的 override 語意用（可寫來源巢狀在唯讀夾下時，其片不算唯讀）。
    鏡射 readonly_source_prefixes，僅 filter 反過來（not source.readonly）；coerce 拋
    ValueError 的髒來源同樣 skip。
    """
    prefixes = []
    for source in iter_gallery_sources(gallery_config):
        if source.readonly or not source.path:
            continue
        try:
            prefixes.append(coerce_to_file_uri(source.path, path_mappings))
        except ValueError:
            continue
    return prefixes
