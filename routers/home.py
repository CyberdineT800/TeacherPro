"""Public home / landing page."""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import RedirectResponse
from models import get_db, Announcement, Employee, School, SchoolClass, Student
from dependencies import get_template_context

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: AsyncSession = Depends(get_db)):
    # Already authenticated → dashboard
    user_id = request.session.get('user_id')
    if user_id:
        if request.session.get('is_admin'):
            return RedirectResponse(url="/admin/dashboard", status_code=303)
        return RedirectResponse(url="/teacher/dashboard", status_code=303)

    # Active announcements (ordered by admin-set order, then newest first)
    announcements = (await db.execute(
        select(Announcement)
        .where(Announcement.is_active.is_(True))
        .order_by(Announcement.order_num.asc(), Announcement.created_at.desc())
        .limit(12)
    )).scalars().all()

    # Platform stats
    schools  = (await db.scalar(select(func.count(School.id))))   or 0
    teachers = (await db.scalar(
        select(func.count(Employee.id)).where(Employee.is_admin.is_(False))
    )) or 0
    classes  = (await db.scalar(select(func.count(SchoolClass.id)))) or 0
    students = (await db.scalar(select(func.count(Student.id))))  or 0

    context = await get_template_context(request, db)
    context.update({
        'announcements': announcements,
        'stats': {
            'schools':  schools,
            'teachers': teachers,
            'classes':  classes,
            'students': students,
        },
    })
    return templates.TemplateResponse('home.html', context)
