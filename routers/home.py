"""Public home / landing page."""
import types
from datetime import datetime
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import RedirectResponse
from models import get_db, Announcement, Employee, School, SchoolClass, Student
from dependencies import get_template_context
from services.cache import (
    cache_get_home_stats, cache_set_home_stats,
    cache_get_home_announcements, cache_set_home_announcements,
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _ann_to_dict(a) -> dict:
    """Serialize an Announcement ORM object to a plain dict for caching."""
    return {
        'id':          a.id,
        'title':       a.title,
        'body':        a.body,
        'image_url':   a.image_url,
        'image_url_2': a.image_url_2,
        'image_url_3': a.image_url_3,
        'badge':       a.badge,
        'link_url':    a.link_url,
        'order_num':   a.order_num,
        'created_at':  str(a.created_at) if a.created_at else None,
    }


def _dict_to_ann(d: dict):
    """Reconstruct a SimpleNamespace that templates treat like an Announcement ORM object."""
    ns = types.SimpleNamespace(**d)
    if ns.created_at and isinstance(ns.created_at, str):
        try:
            ns.created_at = datetime.fromisoformat(ns.created_at)
        except ValueError:
            pass
    return ns


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: AsyncSession = Depends(get_db)):
    # Already authenticated → dashboard
    user_id = request.session.get('user_id')
    if user_id:
        if request.session.get('is_admin'):
            return RedirectResponse(url="/admin/dashboard", status_code=303)
        return RedirectResponse(url="/teacher/dashboard", status_code=303)

    # ── Announcements (Redis cache → DB fallback) ─────────────────────────
    ann_cached = await cache_get_home_announcements()
    if ann_cached is not None:
        announcements = [_dict_to_ann(d) for d in ann_cached]
    else:
        ann_rows = (await db.execute(
            select(Announcement)
            .where(Announcement.is_active.is_(True))
            .order_by(Announcement.order_num.asc(), Announcement.created_at.desc())
            .limit(12)
        )).scalars().all()
        announcements = list(ann_rows)
        await cache_set_home_announcements([_ann_to_dict(a) for a in announcements])

    # ── Platform stats (Redis cache → DB fallback) ────────────────────────
    stats = await cache_get_home_stats()
    if stats is None:
        schools  = (await db.scalar(select(func.count(School.id))))   or 0
        teachers = (await db.scalar(
            select(func.count(Employee.id)).where(Employee.is_admin.is_(False))
        )) or 0
        classes  = (await db.scalar(select(func.count(SchoolClass.id)))) or 0
        students = (await db.scalar(select(func.count(Student.id))))  or 0
        stats = {
            'schools':  schools,
            'teachers': teachers,
            'classes':  classes,
            'students': students,
        }
        await cache_set_home_stats(stats)

    context = await get_template_context(request, db)
    context.update({'announcements': announcements, 'stats': stats})
    return templates.TemplateResponse('home.html', context)
