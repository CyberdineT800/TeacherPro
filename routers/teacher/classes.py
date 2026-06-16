"""Teacher views for assigned classes and their students."""
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from config import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from models import get_db, Employee, SchoolClass, Student
from dependencies import require_login, flash, get_template_context

router = APIRouter(prefix="/teacher", dependencies=[Depends(require_login)])
templates = Jinja2Templates(directory="templates")


async def _assigned_class_ids(db: AsyncSession, teacher_id: int) -> set:
    teacher = (await db.execute(
        select(Employee).options(selectinload(Employee.assigned_classes))
        .where(Employee.id == teacher_id)
    )).scalar_one_or_none()
    return {c.id for c in teacher.assigned_classes} if teacher else set()


@router.get("/classes", response_class=HTMLResponse)
async def teacher_classes(request: Request, db: AsyncSession = Depends(get_db)):
    teacher_id = request.session.get('user_id')
    teacher = (await db.execute(
        select(Employee)
        .options(selectinload(Employee.assigned_classes).selectinload(SchoolClass.school))
        .where(Employee.id == teacher_id)
    )).scalar_one_or_none()
    classes = sorted(teacher.assigned_classes, key=lambda c: c.name) if teacher else []

    class_ids = [c.id for c in classes]
    student_counts = dict(
        (await db.execute(
            select(Student.class_id, func.count(Student.id))
            .where(Student.class_id.in_(class_ids))
            .group_by(Student.class_id)
        )).all()
    ) if class_ids else {}

    context = await get_template_context(request, db)
    context.update({'classes': classes, 'student_counts': student_counts})
    return templates.TemplateResponse('teacher/my_classes.html', context)


@router.get("/classes/{class_id}/students", response_class=HTMLResponse)
async def teacher_class_students(request: Request, class_id: int, db: AsyncSession = Depends(get_db)):
    teacher_id = request.session.get('user_id')
    if class_id not in await _assigned_class_ids(db, teacher_id):
        flash(request, 'Bu sinf sizga biriktirilmagan', 'danger')
        return RedirectResponse(url="/teacher/classes", status_code=303)

    school_class = (await db.execute(
        select(SchoolClass).options(selectinload(SchoolClass.school)).where(SchoolClass.id == class_id)
    )).scalar_one_or_none()
    students = (await db.execute(
        select(Student).where(Student.class_id == class_id)
        .order_by(Student.group_number, Student.last_name, Student.first_name)
    )).scalars().all()

    context = await get_template_context(request, db)
    context.update({'school_class': school_class, 'students': students})
    return templates.TemplateResponse('teacher/class_students.html', context)


@router.get("/students/{id}/edit", response_class=HTMLResponse)
async def teacher_edit_student_page(request: Request, id: int, db: AsyncSession = Depends(get_db)):
    teacher_id = request.session.get('user_id')
    student = (await db.execute(select(Student).where(Student.id == id))).scalar_one_or_none()
    if not student:
        flash(request, "O'quvchi topilmadi", 'danger')
        return RedirectResponse(url="/teacher/classes", status_code=303)
    if student.class_id not in await _assigned_class_ids(db, teacher_id):
        flash(request, 'Bu sinf sizga biriktirilmagan', 'danger')
        return RedirectResponse(url="/teacher/classes", status_code=303)

    school_class = (await db.execute(
        select(SchoolClass).options(selectinload(SchoolClass.school)).where(SchoolClass.id == student.class_id)
    )).scalar_one_or_none()

    context = await get_template_context(request, db)
    context.update({'student': student, 'school_class': school_class})
    return templates.TemplateResponse('teacher/student_edit.html', context)


@router.post("/students/{id}/edit")
async def teacher_edit_student(
    request: Request, id: int,
    first_name: str = Form(...), last_name: str = Form(...),
    gender: int = Form(...), group_number: int = Form(...),
    db: AsyncSession = Depends(get_db),
):
    teacher_id = request.session.get('user_id')
    student = (await db.execute(select(Student).where(Student.id == id))).scalar_one_or_none()
    if not student:
        flash(request, "O'quvchi topilmadi", 'danger')
        return RedirectResponse(url="/teacher/classes", status_code=303)
    if student.class_id not in await _assigned_class_ids(db, teacher_id):
        flash(request, 'Bu sinf sizga biriktirilmagan', 'danger')
        return RedirectResponse(url="/teacher/classes", status_code=303)

    student.first_name = first_name
    student.last_name = last_name
    student.gender = gender
    student.group_number = group_number
    await db.commit()
    flash(request, "O'quvchi ma'lumotlari yangilandi", 'success')
    return RedirectResponse(url=f"/teacher/classes/{student.class_id}/students", status_code=303)
