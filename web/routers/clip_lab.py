"""
clip_lab.py — Constellation Lab 動畫沙盒路由
GET /clip-lab：56b-T1 開發用沙盒，include_in_schema=False（不污染 API 文件）
56b-T3 刪除此檔案並移至 motion-lab section
"""

from fastapi import APIRouter, Request

router = APIRouter(prefix="", tags=["clip-lab"])


@router.get("/clip-lab", include_in_schema=False)
async def clip_lab_page(request: Request):
    """Constellation Lab 動畫沙盒頁（HTML）"""
    from web.app import get_common_context, templates
    context = get_common_context(request)
    context["page"] = "clip-lab"
    return templates.TemplateResponse("clip_lab.html", context)
