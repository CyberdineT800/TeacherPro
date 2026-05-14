"""Admin routes for Quiz Race game management.

All Quiz Race-specific admin routes live under /admin/games/quiz-race/
so it is unambiguous which game type they belong to.
"""
from typing import Optional

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from config import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from models import get_db, Employee, GameSession, GameParticipant
from dependencies import require_admin, flash, get_template_context, page_info

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory="templates")


@router.get("/games/quiz-race/settings", response_class=HTMLResponse)
async def admin_quiz_race_settings(request: Request, db: AsyncSession = Depends(get_db)):
    """Show all teachers with games_enabled toggle and recent game stats."""
    teachers = (await db.execute(
        select(Employee)
        .options(selectinload(Employee.school))
        .where(Employee.is_admin.is_(False))
        .order_by(Employee.first_name)
    )).scalars().all()

    session_counts = dict((await db.execute(
        select(GameSession.teacher_id, func.count(GameSession.id))
        .group_by(GameSession.teacher_id)
    )).all())

    context = await get_template_context(request, db)
    context.update({'teachers': teachers, 'session_counts': session_counts})
    return templates.TemplateResponse('admin/games/quiz_race/settings.html', context)


@router.post("/games/quiz-race/settings/{teacher_id}")
async def admin_quiz_race_settings_save(
    teacher_id: int, request: Request,
    games_enabled: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    teacher = (await db.execute(
        select(Employee).where(Employee.id == teacher_id)
    )).scalar_one_or_none()
    if not teacher:
        flash(request, "O'qituvchi topilmadi", 'danger')
        return RedirectResponse(url="/admin/games/quiz-race/settings", status_code=303)

    teacher.games_enabled = (games_enabled == 'on')
    await db.commit()
    status = "yoqildi" if teacher.games_enabled else "o'chirildi"
    flash(request, f"{teacher.first_name} {teacher.last_name} — o'yin {status}", 'success')
    return RedirectResponse(url="/admin/games/quiz-race/settings", status_code=303)


@router.get("/games/quiz-race", response_class=HTMLResponse)
async def admin_quiz_race_list(
    request: Request,
    teacher_id: Optional[str] = None,
    page: int = 1,
    db: AsyncSession = Depends(get_db),
):
    """Admin view of all completed Quiz Race sessions."""
    per_page = 10
    tid: Optional[int] = int(teacher_id) if teacher_id and teacher_id.strip().isdigit() else None

    count_q = select(func.count(GameSession.id)).where(GameSession.status == 'finished')
    data_q = (
        select(GameSession, Employee)
        .join(Employee, Employee.id == GameSession.teacher_id)
        .where(GameSession.status == 'finished')
        .order_by(GameSession.finished_at.desc())
    )
    if tid:
        count_q = count_q.where(GameSession.teacher_id == tid)
        data_q = data_q.where(GameSession.teacher_id == tid)

    total = (await db.execute(count_q)).scalar()
    pg = page_info(total, page, per_page, request)
    rows = (await db.execute(data_q.offset(pg['row_offset']).limit(per_page))).all()
    items = [{'gs': gs, 't': t} for gs, t in rows]

    teachers = (await db.execute(
        select(Employee).where(Employee.is_admin.is_(False)).order_by(Employee.first_name)
    )).scalars().all()

    context = await get_template_context(request, db)
    context.update({'items': items, 'teachers': teachers, 'selected_teacher_id': tid, **pg})
    return templates.TemplateResponse('admin/games/quiz_race/list.html', context)


@router.get("/games/quiz-race/{sid}/results", response_class=HTMLResponse)
async def admin_quiz_race_session_results(
    sid: int, request: Request, db: AsyncSession = Depends(get_db)
):
    """Admin view of one Quiz Race session's final results."""
    gs = (await db.execute(
        select(GameSession)
        .options(
            selectinload(GameSession.questions),
            selectinload(GameSession.participants),
            selectinload(GameSession.teacher),
        )
        .where(GameSession.id == sid)
    )).scalar_one_or_none()
    if not gs:
        flash(request, "O'yin sessiyasi topilmadi", 'danger')
        return RedirectResponse(url="/admin/games/quiz-race", status_code=303)

    participants = sorted(gs.participants, key=lambda p: (p.rank or 9999))
    context = await get_template_context(request, db)
    context.update({'gs': gs, 'participants': participants})
    return templates.TemplateResponse('admin/games/quiz_race/results.html', context)
