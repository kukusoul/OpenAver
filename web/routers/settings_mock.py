"""
Settings Mock router — Visual POC for feature/61-settings-ia-sources B1 (task 61b-1).

Purpose: provide a clickable HTML prototype at `/settings-mock` so the user can
pin down tab IA, source-pill density, and Metatube greyed-area direction before
P3/P4 implementation work begins. Mock data only — no config.json read, no DB
write. Hidden from sidebar nav (CD-61-13); not registered in capabilities.

⚠️ Long-term plan: keep this route until B4 ships as a visual regression
reference; delete with `tools/` after feature/64 (per plan-61 CD-61-13).
"""

from fastapi import APIRouter, Request

from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="", tags=["settings-mock"])


# 8 builtin sources — order mirrors `core/scraper.py::SCRAPER_CLASSES` + DMM.
# Source of truth for the real feature is `core/source_config.py::get_builtin_sources()`
# (built in P2 task 61a-1). This list is a POC mock only.
_MOCK_BUILTIN_SOURCES = [
    {"id": "javbus", "name": "JavBus", "is_censored": True, "order": 0},
    {"id": "jav321", "name": "Jav321", "is_censored": True, "order": 1},
    {"id": "javdb", "name": "JavDB", "is_censored": True, "order": 2},
    {"id": "dmm", "name": "DMM", "is_censored": True, "order": 3},
    {"id": "d2pass", "name": "D2Pass", "is_censored": False, "order": 4},
    {"id": "heyzo", "name": "HEYZO", "is_censored": False, "order": 5},
    {"id": "fc2", "name": "FC2", "is_censored": False, "order": 6},
    {"id": "avsox", "name": "AVSOX", "is_censored": False, "order": 7},
]

# Metatube provider preview — used in viewpoint C "connected preview".
# These names are illustrative for the POC visual only.
_MOCK_METATUBE_SOURCES = [
    {"id": "mt_fanza", "name": "FANZA"},
    {"id": "mt_mgs", "name": "MGS"},
    {"id": "mt_duga", "name": "DUGA"},
    {"id": "mt_sod", "name": "SOD"},
    {"id": "mt_1pondo", "name": "1Pondo"},
    {"id": "mt_10musume", "name": "10musume"},
    {"id": "mt_caribbeancom", "name": "Caribbeancom"},
    {"id": "mt_heyzo", "name": "HEYZO"},
    {"id": "mt_fc2", "name": "FC2"},
    {"id": "mt_pacopacomama", "name": "Pacopacomama"},
    {"id": "mt_muramura", "name": "Muramura"},
    {"id": "mt_tokyohot", "name": "Tokyo-Hot"},
    {"id": "mt_kin8", "name": "Kin8tengoku"},
    {"id": "mt_naturalhigh", "name": "NaturalHigh"},
    {"id": "mt_xcity", "name": "X-City"},
    {"id": "mt_h4610", "name": "H4610"},
    {"id": "mt_gachinco", "name": "Gachinco"},
    {"id": "mt_javbus", "name": "JavBus"},
    {"id": "mt_arzon", "name": "Arzon"},
    {"id": "mt_avbase", "name": "AVBase"},
    {"id": "mt_aventertainments", "name": "AV-E"},
    {"id": "mt_fc2hub", "name": "FC2Hub"},
    {"id": "mt_jav321", "name": "Jav321"},
    {"id": "mt_javdb", "name": "JavDB"},
    {"id": "mt_njav", "name": "NJav"},
    {"id": "mt_prestige", "name": "Prestige"},
    {"id": "mt_sehuatang", "name": "色花堂"},
    {"id": "mt_tameikegoro", "name": "Tameike Goro"},
    {"id": "mt_xslist", "name": "XsList"},
    {"id": "mt_javlibrary", "name": "JavLibrary"},
]


# Six proposed Settings tabs (CD-61-1).
# id stays single-word; labels here are PLACEHOLDER copy for the mock — final
# i18n keys land in settings.tabs.* at P3 entry.
_MOCK_TABS = [
    {"id": "display", "icon": "bi-palette", "label_key": "settings.mock.tab.display"},
    {"id": "scraping", "icon": "bi-gear", "label_key": "settings.mock.tab.scraping"},
    {"id": "sources", "icon": "bi-collection", "label_key": "settings.mock.tab.sources"},
    {"id": "organize", "icon": "bi-folder", "label_key": "settings.mock.tab.organize"},
    {"id": "translate", "icon": "bi-translate", "label_key": "settings.mock.tab.translate"},
    {"id": "advanced", "icon": "bi-tools", "label_key": "settings.mock.tab.advanced"},
]


@router.get("/settings-mock")
async def settings_mock_page(request: Request):
    """Visual POC for the Settings IA + Source Pills redesign (task 61b-1)."""
    # 延遲 import 避免 circular
    from web.app import get_common_context, templates

    context = get_common_context(request)
    # 故意傳一個不存在於 sidebar 的 page key — base.html `{% if page == ... %}active`
    # 不會 match 任何 nav item，達成 CD-61-13「隱藏於正常導航」的視覺效果。
    context["page"] = "settings-mock"
    context["mock_tabs"] = _MOCK_TABS
    context["mock_builtin_sources"] = _MOCK_BUILTIN_SOURCES
    context["mock_metatube_sources"] = _MOCK_METATUBE_SOURCES

    return templates.TemplateResponse(request, "settings_mock.html", context)
