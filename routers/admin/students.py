"""Admin student management routes."""
from typing import Optional

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from config import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload

from services.cache import cache_del_admin_stats
from models import get_db, Employee, SchoolClass, Student, ExamResult
from dependencies import require_admin, flash, get_template_context, page_info

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory="templates")


def _no_access(request: Request):
    """Redirect a school admin who tried to reach an out-of-scope student."""
    flash(request, "Bu amal uchun ruxsat yo'q", 'danger')
    return RedirectResponse(url="/admin/students", status_code=303)


async def _class_in_scope(db: AsyncSession, class_id: int, admin: Employee) -> bool:
    """True if the class belongs to the admin's school (always True for super admins)."""
    if admin.is_super_admin:
        return True
    school_id = (await db.execute(
        select(SchoolClass.school_id).where(SchoolClass.id == class_id)
    )).scalar_one_or_none()
    return school_id == admin.school_id


@router.get("/students", response_class=HTMLResponse)
async def students_list(
    request: Request, class_id: Optional[str] = None, page: int = 1,
    db: AsyncSession = Depends(get_db),
    current_admin: Employee = Depends(require_admin),
):
    per_page = 10
    cid = None
    if class_id and class_id.strip():
        try:
            cid = int(class_id)
        except ValueError:
            pass

    if cid and not await _class_in_scope(db, cid, current_admin):
        return _no_access(request)

    classes_q = select(SchoolClass).options(selectinload(SchoolClass.school))
    scope_class_ids = None
    if not current_admin.is_super_admin:
        classes_q = classes_q.where(SchoolClass.school_id == current_admin.school_id)
        scope_class_ids = select(SchoolClass.id).where(SchoolClass.school_id == current_admin.school_id)

    if cid:
        students = (await db.execute(select(Student).where(Student.class_id == cid))).scalars().all()
        selected_class = (await db.execute(
            select(SchoolClass).options(selectinload(SchoolClass.school)).where(SchoolClass.id == cid)
        )).scalar_one_or_none()
        pg = page_info(len(students), 1, len(students) or 1, request)
    else:
        count_q = select(func.count(Student.id))
        data_q = select(Student).order_by(Student.created_at.desc())
        if scope_class_ids is not None:
            count_q = count_q.where(Student.class_id.in_(scope_class_ids))
            data_q = data_q.where(Student.class_id.in_(scope_class_ids))
        total = (await db.execute(count_q)).scalar()
        pg = page_info(total, page, per_page, request)
        students = (await db.execute(
            data_q.offset(pg['row_offset']).limit(per_page)
        )).scalars().all()
        selected_class = None

    classes = (await db.execute(classes_q)).scalars().all()

    context = await get_template_context(request)
    context.update({'students': students, 'classes': classes, 'selected_class': selected_class, **pg})
    return templates.TemplateResponse('admin/students.html', context)


@router.get("/students/add", response_class=HTMLResponse)
async def add_student_page(request: Request, db: AsyncSession = Depends(get_db),
                           current_admin: Employee = Depends(require_admin)):
    classes_q = select(SchoolClass).options(selectinload(SchoolClass.school))
    if not current_admin.is_super_admin:
        classes_q = classes_q.where(SchoolClass.school_id == current_admin.school_id)
    classes = (await db.execute(classes_q)).scalars().all()
    context = await get_template_context(request)
    context.update({'student': None, 'classes': classes})
    return templates.TemplateResponse('admin/student_form.html', context)


@router.post("/students/add")
async def add_student(
    request: Request,
    first_name: str = Form(...), last_name: str = Form(...),
    gender: int = Form(...), group_number: int = Form(...),
    class_id: int = Form(...), db: AsyncSession = Depends(get_db),
    current_admin: Employee = Depends(require_admin),
):
    if not await _class_in_scope(db, class_id, current_admin):
        return _no_access(request)
    db.add(Student(first_name=first_name, last_name=last_name,
                   gender=gender, group_number=group_number, class_id=class_id))
    await db.commit()
    await cache_del_admin_stats()
    flash(request, "O'quvchi qo'shildi", 'success')
    return RedirectResponse(url=f"/admin/students?class_id={class_id}", status_code=303)


@router.get("/students/edit/{id}", response_class=HTMLResponse)
async def edit_student_page(request: Request, id: int, db: AsyncSession = Depends(get_db),
                            current_admin: Employee = Depends(require_admin)):
    student = (await db.execute(select(Student).where(Student.id == id))).scalar_one_or_none()
    if not student:
        flash(request, "O'quvchi topilmadi", 'danger')
        return RedirectResponse(url="/admin/students", status_code=303)
    if not await _class_in_scope(db, student.class_id, current_admin):
        return _no_access(request)
    classes_q = select(SchoolClass).options(selectinload(SchoolClass.school))
    if not current_admin.is_super_admin:
        classes_q = classes_q.where(SchoolClass.school_id == current_admin.school_id)
    classes = (await db.execute(classes_q)).scalars().all()
    context = await get_template_context(request)
    context.update({'student': student, 'classes': classes})
    return templates.TemplateResponse('admin/student_form.html', context)


@router.post("/students/edit/{id}")
async def edit_student(
    request: Request, id: int,
    first_name: str = Form(...), last_name: str = Form(...),
    gender: int = Form(...), group_number: int = Form(...),
    class_id: int = Form(...), db: AsyncSession = Depends(get_db),
    current_admin: Employee = Depends(require_admin),
):
    student = (await db.execute(select(Student).where(Student.id == id))).scalar_one_or_none()
    if not student:
        flash(request, "O'quvchi topilmadi", 'danger')
        return RedirectResponse(url="/admin/students", status_code=303)
    if not await _class_in_scope(db, student.class_id, current_admin):
        return _no_access(request)
    if not await _class_in_scope(db, class_id, current_admin):
        return _no_access(request)
    student.first_name = first_name
    student.last_name = last_name
    student.gender = gender
    student.group_number = group_number
    student.class_id = class_id
    await db.commit()
    flash(request, "O'quvchi ma'lumotlari yangilandi", 'success')
    return RedirectResponse(url=f"/admin/students?class_id={class_id}", status_code=303)


@router.post("/students/delete/{id}")
async def delete_student(request: Request, id: int, db: AsyncSession = Depends(get_db),
                         current_admin: Employee = Depends(require_admin)):
    student = (await db.execute(select(Student).where(Student.id == id))).scalar_one_or_none()
    if not student:
        flash(request, "O'quvchi topilmadi", 'danger')
        return RedirectResponse(url="/admin/students", status_code=303)
    if not await _class_in_scope(db, student.class_id, current_admin):
        return _no_access(request)
    cid = student.class_id
    try:
        await db.execute(delete(ExamResult).where(ExamResult.student_id == id))
        await db.delete(student)
        await db.commit()
        await cache_del_admin_stats()
        flash(request, "O'quvchi va uning natijalari o'chirildi", 'success')
    except Exception as e:
        await db.rollback()
        flash(request, f"O'quvchini o'chirishda xatolik: {e}", 'danger')
    return RedirectResponse(url=f"/admin/students?class_id={cid}", status_code=303)
