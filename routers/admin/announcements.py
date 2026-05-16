"""Admin CRUD for public announcements shown on the home page."""
import logging
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import RedirectResponse
from models import get_db, Announcement
from dependencies import require_admin, flash, get_template_context
from services.ai_shared import translate
from services.cache import cache_del_home_announcements



log = logging.getLogger("admin.announcements")
router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory="templates")

UPLOADS_DIR = os.path.join("static", "uploads")
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_SIZE = 5 * 1024 * 1024  # 5 MB


async def _save_image(image: Optional[UploadFile]) -> Optional[str]:
    """Save uploaded image; return URL path or None.

    Uses file extension for validation (not content-type) because some
    browsers send application/octet-stream for image files, which would
    cause a false rejection.
    """
    if not image or not image.filename:
        return None
    ext = os.path.splitext(image.filename)[1].lower()
    if not ext:
        ext = ".jpg"
    if ext not in ALLOWED_EXTS:
        log.warning("Rejected upload — bad ext: %s (ct=%s)", ext, image.content_type)
        return None
    data = await image.read()
    if not data:         
        return None
    if len(data) > MAX_SIZE:
        log.warning("Rejected upload — too large: %d bytes", len(data))
        return None
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    fname = uuid.uuid4().hex + ext
    path = os.path.join(UPLOADS_DIR, fname)
    with open(path, "wb") as f:
        f.write(data)
    log.info("Saved upload: %s (%d bytes)", fname, len(data))
    return f"/static/uploads/{fname}"


def _remove_file(url: Optional[str]) -> None:
    if url and url.startswith("/static/uploads/"):
        fpath = url.lstrip("/")
        if os.path.exists(fpath):
            os.remove(fpath)


@router.get("/announcements", response_class=HTMLResponse)
async def announcements_list(request: Request, db: AsyncSession = Depends(get_db)):
    items = (await db.execute(
        select(Announcement).order_by(Announcement.order_num.asc(), Announcement.created_at.desc())
    )).scalars().all()
    context = await get_template_context(request, db)
    context["announcements"] = items
    return templates.TemplateResponse("admin/announcements.html", context)


@router.post("/announcements/create")
async def announcement_create(
    request: Request,
    title:      str           = Form(...),
    body:       Optional[str] = Form(None),
    image:      Optional[UploadFile] = File(None),
    image2:     Optional[UploadFile] = File(None),
    image3:     Optional[UploadFile] = File(None),
    badge:      Optional[str] = Form(None),
    link_url:   Optional[str] = Form(None),
    order_num:  int           = Form(0),
    is_active:  Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    ann = Announcement(
        title=title.strip(),
        body=body.strip() if body and body.strip() else None,
        image_url=await _save_image(image),
        image_url_2=await _save_image(image2),
        image_url_3=await _save_image(image3),
        badge=badge.strip() if badge and badge.strip() else None,
        link_url=link_url.strip() if link_url and link_url.strip() else None,
        order_num=order_num,
        is_active=(is_active == "on"),
    )
    db.add(ann)
    await db.commit()
    await cache_del_home_announcements()
    flash(request, translate(request, "ann_added"), "success")
    return RedirectResponse(url="/admin/announcements", status_code=303)


@router.post("/announcements/{ann_id}/edit")
async def announcement_edit(
    ann_id: int,
    request: Request,
    title:       str           = Form(...),
    body:        Optional[str] = Form(None),
    image:       Optional[UploadFile] = File(None),
    image2:      Optional[UploadFile] = File(None),
    image3:      Optional[UploadFile] = File(None),
    keep_img1:   Optional[str] = Form(None),
    keep_img2:   Optional[str] = Form(None),
    keep_img3:   Optional[str] = Form(None),
    badge:       Optional[str] = Form(None),
    link_url:    Optional[str] = Form(None),
    order_num:   int           = Form(0),
    is_active:   Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    ann = (await db.execute(
        select(Announcement).where(Announcement.id == ann_id)
    )).scalar_one_or_none()
    if not ann:
        flash(request, "E'lon topilmadi", "danger")
        return RedirectResponse(url="/admin/announcements", status_code=303)

    new1 = await _save_image(image)
    new2 = await _save_image(image2)
    new3 = await _save_image(image3)

    if new1: _remove_file(ann.image_url)
    if new2: _remove_file(ann.image_url_2)
    if new3: _remove_file(ann.image_url_3)

    ann.image_url   = new1 if new1 else (keep_img1 or None)
    ann.image_url_2 = new2 if new2 else (keep_img2 or None)
    ann.image_url_3 = new3 if new3 else (keep_img3 or None)
    ann.title     = title.strip()
    ann.body      = body.strip() if body and body.strip() else None
    ann.badge     = badge.strip() if badge and badge.strip() else None
    ann.link_url  = link_url.strip() if link_url and link_url.strip() else None
    ann.order_num = order_num
    ann.is_active = (is_active == "on")
    ann.updated_at = datetime.utcnow()
    await db.commit()
    await cache_del_home_announcements()
    flash(request, translate(request, "ann_updated"), "success")
    return RedirectResponse(url="/admin/announcements", status_code=303)


@router.post("/announcements/{ann_id}/toggle")
async def announcement_toggle(ann_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    ann = (await db.execute(
        select(Announcement).where(Announcement.id == ann_id)
    )).scalar_one_or_none()
    if ann:
        ann.is_active = not ann.is_active
        ann.updated_at = datetime.utcnow()
        await db.commit()
        await cache_del_home_announcements()
    return RedirectResponse(url="/admin/announcements", status_code=303)


@router.post("/announcements/{ann_id}/delete")
async def announcement_delete(ann_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    ann = (await db.execute(
        select(Announcement).where(Announcement.id == ann_id)
    )).scalar_one_or_none()
    if ann:
        _remove_file(ann.image_url)
        _remove_file(ann.image_url_2)
        _remove_file(ann.image_url_3)
        await db.delete(ann)
        await db.commit()
        await cache_del_home_announcements()
        flash(request, translate(request, "ann_deleted"), "success")
    return RedirectResponse(url="/admin/announcements", status_code=303)
