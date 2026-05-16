"""Admin AI management routes (dashboard + AI presentation & question settings)."""
import json
import logging
import re
import traceback
from datetime import date
from io import BytesIO
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from config import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, defer

from models import get_db, Employee, School, SchoolClass, Student, Subject, AIPresentation, AIQuestionSet
from dependencies import require_admin, flash, get_template_context, page_info
from services.ai_shared import translate, TEMPLATES, LANGUAGE_DISPLAY, TYPE_DISPLAY
from services.cache import cache_get_admin_stats, cache_set_admin_stats

log = logging.getLogger("admin.ai")

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory="templates")

# ── Admin dashboard ──────────────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    # Try Redis cache first (TTL 60 s — stale counts are fine for a dashboard)
    stats = await cache_get_admin_stats()
    if stats is None:
        # Sequential queries — asyncio.gather on a shared session causes
        # "concurrent operations are not permitted" in SQLAlchemy async.
        stats = {
            'schools_count':   await db.scalar(select(func.count(School.id)))   or 0,
            'employees_count': await db.scalar(select(func.count(Employee.id))) or 0,
            'classes_count':   await db.scalar(select(func.count(SchoolClass.id))) or 0,
            'students_count':  await db.scalar(select(func.count(Student.id)))  or 0,
        }
        await cache_set_admin_stats(stats)
    context = await get_template_context(request)
    context.update(stats)
    return templates.TemplateResponse('admin_dashboard.html', context)


# ── AI Presentations (admin view) ─────────────────────────────────────────────

@router.get("/ai", response_class=HTMLResponse)
async def admin_ai_list(
    request: Request, teacher_id: Optional[str] = None,
    page: int = 1, db: AsyncSession = Depends(get_db)
):
    per_page = 6
    tid: Optional[int] = int(teacher_id) if teacher_id and teacher_id.strip().isdigit() else None

    count_q = select(func.count(AIPresentation.id))
    data_q = (
        select(AIPresentation, Employee)
        .options(defer(AIPresentation.content))
        .join(Employee, Employee.id == AIPresentation.teacher_id)
        .order_by(AIPresentation.created_at.desc())
    )
    if tid:
        count_q = count_q.where(AIPresentation.teacher_id == tid)
        data_q = data_q.where(AIPresentation.teacher_id == tid)

    total = (await db.execute(count_q)).scalar()
    pg = page_info(total, page, per_page, request)
    rows = (await db.execute(data_q.offset(pg['row_offset']).limit(per_page))).all()
    items = [{'p': p, 't': t} for p, t in rows]
    teachers = (await db.execute(
        select(Employee).where(Employee.is_admin.is_(False)).order_by(Employee.first_name)
    )).scalars().all()

    context = await get_template_context(request, db)
    context.update({'items': items, 'teachers': teachers, 'selected_teacher_id': tid,
                    'language_display': LANGUAGE_DISPLAY, 'presentation_templates': TEMPLATES, **pg})
    return templates.TemplateResponse('admin/ai_presentations.html', context)


@router.get("/ai/settings", response_class=HTMLResponse)
async def admin_ai_settings(request: Request, db: AsyncSession = Depends(get_db)):
    teachers = (await db.execute(
        select(Employee).options(selectinload(Employee.school))
        .where(Employee.is_admin.is_(False)).order_by(Employee.first_name)
    )).scalars().all()
    counts = dict((await db.execute(
        select(AIPresentation.teacher_id, func.count(AIPresentation.id)).group_by(AIPresentation.teacher_id)
    )).all())
    q_counts = dict((await db.execute(
        select(AIQuestionSet.teacher_id, func.count(AIQuestionSet.id)).group_by(AIQuestionSet.teacher_id)
    )).all())
    context = await get_template_context(request, db)
    context.update({'teachers': teachers, 'counts': counts, 'q_counts': q_counts})
    return templates.TemplateResponse('admin/ai_settings.html', context)


@router.post("/ai/settings/{teacher_id}")
async def admin_ai_settings_save(
    teacher_id: int, request: Request,
    ai_enabled: Optional[str] = Form(None),
    ai_daily_limit: int = Form(3),
    ai_questions_daily_limit: int = Form(5),
    db: AsyncSession = Depends(get_db)
):
    teacher = (await db.execute(select(Employee).where(Employee.id == teacher_id))).scalar_one_or_none()
    if not teacher:
        raise HTTPException(404)
    teacher.ai_enabled = (ai_enabled == 'on')
    teacher.ai_daily_limit = max(0, min(50, ai_daily_limit))
    teacher.ai_questions_daily_limit = max(0, min(100, ai_questions_daily_limit))
    await db.commit()
    flash(request, f"{teacher.first_name} {teacher.last_name} — {translate(request, 'ai_settings_saved_suffix')}", 'success')
    return RedirectResponse(url="/admin/ai/settings", status_code=303)


@router.get("/ai/{pid}/download")
async def admin_ai_download(pid: int, db: AsyncSession = Depends(get_db)):
    from services.ai_shared import TEMPLATES as T
    from routers.teacher.ai_presentation import build_pptx as _build_pptx
    presentation = (await db.execute(
        select(AIPresentation).where(AIPresentation.id == pid)
    )).scalar_one_or_none()
    if not presentation:
        raise HTTPException(404)
    try:
        data = json.loads(presentation.content)
        tpl_key = presentation.template if presentation.template in T else 'cosmos'
        pptx_bytes = await _build_pptx(data, presentation, T[tpl_key]['pptx'])
    except Exception as e:
        log.error("PPTX build failed for presentation %s: %s\n%s", pid, e, traceback.format_exc())
        raise HTTPException(500, detail=f"PPTX yaratishda xatolik: {e}")
    ascii_name = re.sub(r'[^A-Za-z0-9_\- ]+', '_', presentation.topic)[:60].strip('_ ') or 'presentation'
    ascii_filename = f"{ascii_name}_grade{presentation.grade}.pptx"
    utf8_filename = quote(f"{presentation.topic[:60]}_{presentation.grade}sinf.pptx")
    return StreamingResponse(
        BytesIO(pptx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Disposition": f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{utf8_filename}',
            "Content-Length": str(len(pptx_bytes)),
        },
    )


# ── AI Questions (admin view) ─────────────────────────────────────────────────

@router.get("/ai-questions", response_class=HTMLResponse)
async def admin_questions_list(
    request: Request, teacher_id: Optional[str] = None,
    page: int = 1, db: AsyncSession = Depends(get_db)
):
    per_page = 6
    tid: Optional[int] = int(teacher_id) if teacher_id and teacher_id.strip().isdigit() else None
    count_q = select(func.count(AIQuestionSet.id))
    data_q = (
        select(AIQuestionSet, Employee)
        .join(Employee, Employee.id == AIQuestionSet.teacher_id)
        .order_by(AIQuestionSet.created_at.desc())
    )
    if tid:
        count_q = count_q.where(AIQuestionSet.teacher_id == tid)
        data_q = data_q.where(AIQuestionSet.teacher_id == tid)
    total = (await db.execute(count_q)).scalar()
    pg = page_info(total, page, per_page, request)
    rows = (await db.execute(data_q.offset(pg['row_offset']).limit(per_page))).all()
    items = [{'qs': qs, 't': t} for qs, t in rows]
    teachers = (await db.execute(
        select(Employee).where(Employee.is_admin.is_(False)).order_by(Employee.first_name)
    )).scalars().all()
    context = await get_template_context(request, db)
    context.update({'items': items, 'teachers': teachers, 'selected_teacher_id': tid,
                    'language_display': LANGUAGE_DISPLAY, 'type_display': TYPE_DISPLAY, **pg})
    return templates.TemplateResponse('admin/ai_questions.html', context)
