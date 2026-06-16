"""Admin employee management routes."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from config import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload

from services.cache import cache_del_admin_stats, cache_del_home_stats, cache_del_user
from models import (
    get_db, School, Employee, StaffTitle, SchoolClass, Subject,
    Exam, Question, ExamResult, TeacherClass, TeacherSubject,
)
from dependencies import require_admin, flash, get_template_context, page_info

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory="templates")


def _no_access(request: Request):
    """Redirect a school admin who tried to reach an out-of-scope record."""
    flash(request, "Bu amal uchun ruxsat yo'q", 'danger')
    return RedirectResponse(url="/admin/employees", status_code=303)


@router.get("/employees", response_class=HTMLResponse)
async def employees_list(
    request: Request, school_id: Optional[str] = None, page: int = 1,
    db: AsyncSession = Depends(get_db),
    current_admin: Employee = Depends(require_admin),
):
    per_page = 10
    sid = None
    if school_id and school_id.strip():
        try:
            sid = int(school_id)
        except ValueError:
            pass

    # School admins are locked to their own school regardless of query params.
    if not current_admin.is_super_admin:
        sid = current_admin.school_id

    base_q = select(Employee).options(
        selectinload(Employee.school), selectinload(Employee.staff_title)
    )
    count_q = select(func.count(Employee.id))

    if sid:
        base_q = base_q.where(Employee.school_id == sid).order_by(Employee.last_name, Employee.first_name)
        count_q = count_q.where(Employee.school_id == sid)
    elif not current_admin.is_super_admin:
        # School admin without an assigned school sees nothing.
        base_q = base_q.where(Employee.id == -1)
        count_q = count_q.where(Employee.id == -1)
    else:
        base_q = base_q.order_by(Employee.created_at.desc())

    total = (await db.execute(count_q)).scalar()
    pg = page_info(total, page, per_page, request)
    employees = (await db.execute(base_q.offset(pg['row_offset']).limit(per_page))).scalars().all()
    schools = (await db.execute(select(School))).scalars().all()

    context = await get_template_context(request)
    context.update({'employees': employees, 'schools': schools, **pg})
    return templates.TemplateResponse('admin/employees.html', context)


@router.get("/employees/add", response_class=HTMLResponse)
async def add_employee_page(request: Request, db: AsyncSession = Depends(get_db),
                            current_admin: Employee = Depends(require_admin)):
    schools = (await db.execute(select(School))).scalars().all()
    titles = (await db.execute(select(StaffTitle))).scalars().all()
    classes_q = select(SchoolClass)
    if not current_admin.is_super_admin:
        classes_q = classes_q.where(SchoolClass.school_id == current_admin.school_id)
    classes = (await db.execute(classes_q)).scalars().all()
    subjects = (await db.execute(select(Subject))).scalars().all()
    context = await get_template_context(request)
    context.update({'employee': None, 'schools': schools, 'titles': titles,
                    'classes': classes, 'subjects': subjects})
    return templates.TemplateResponse('admin/employee_form.html', context)


@router.post("/employees/add")
async def add_employee(
    request: Request,
    username: str = Form(...), password: str = Form(...),
    first_name: str = Form(...), last_name: str = Form(...),
    email: str = Form(""), is_admin: bool = Form(False),
    is_active: bool = Form(False), school_id: Optional[int] = Form(None),
    staff_title_id: Optional[int] = Form(None),
    assigned_classes: list = Form([]), assigned_subjects: list = Form([]),
    db: AsyncSession = Depends(get_db),
    current_admin: Employee = Depends(require_admin),
):
    # School admins create only school-scoped staff for their own school —
    # they cannot grant admin rights or assign another school.
    if not current_admin.is_super_admin:
        school_id = current_admin.school_id
        is_admin = False

    emp = Employee(username=username, first_name=first_name, last_name=last_name,
                   email=email, is_admin=is_admin, is_active=is_active,
                   school_id=school_id, staff_title_id=staff_title_id)
    emp.set_password(password)
    db.add(emp)
    await db.flush()
    for cid in assigned_classes:
        db.add(TeacherClass(teacher_id=emp.id, class_id=int(cid)))
    for sid in assigned_subjects:
        db.add(TeacherSubject(teacher_id=emp.id, subject_id=int(sid)))
    await db.commit()
    await cache_del_admin_stats()
    await cache_del_home_stats()
    flash(request, "Xodim qo'shildi", 'success')
    return RedirectResponse(url="/admin/employees", status_code=303)


@router.get("/employees/edit/{id}", response_class=HTMLResponse)
async def edit_employee_page(request: Request, id: int, db: AsyncSession = Depends(get_db),
                             current_admin: Employee = Depends(require_admin)):
    emp = (await db.execute(
        select(Employee)
        .options(selectinload(Employee.assigned_classes), selectinload(Employee.assigned_subjects))
        .where(Employee.id == id)
    )).scalar_one_or_none()
    if not emp:
        flash(request, 'Xodim topilmadi', 'danger')
        return RedirectResponse(url="/admin/employees", status_code=303)
    # School admins may only edit non-admin staff within their own school.
    if not current_admin.is_super_admin and (emp.school_id != current_admin.school_id or emp.is_admin):
        return _no_access(request)
    schools = (await db.execute(select(School))).scalars().all()
    titles = (await db.execute(select(StaffTitle))).scalars().all()
    classes_q = select(SchoolClass)
    if not current_admin.is_super_admin:
        classes_q = classes_q.where(SchoolClass.school_id == current_admin.school_id)
    classes = (await db.execute(classes_q)).scalars().all()
    subjects = (await db.execute(select(Subject))).scalars().all()
    context = await get_template_context(request)
    context.update({'employee': emp, 'schools': schools, 'titles': titles,
                    'classes': classes, 'subjects': subjects})
    return templates.TemplateResponse('admin/employee_form.html', context)


@router.post("/employees/edit/{id}")
async def edit_employee(
    request: Request, id: int,
    username: str = Form(...), first_name: str = Form(...),
    last_name: str = Form(...), email: str = Form(""),
    is_admin: bool = Form(False), is_active: bool = Form(False),
    school_id: Optional[int] = Form(None), staff_title_id: Optional[int] = Form(None),
    assigned_classes: list = Form([]), assigned_subjects: list = Form([]),
    password: str = Form(""), db: AsyncSession = Depends(get_db),
    current_admin: Employee = Depends(require_admin),
):
    emp = (await db.execute(select(Employee).where(Employee.id == id))).scalar_one_or_none()
    if not emp:
        flash(request, 'Xodim topilmadi', 'danger')
        return RedirectResponse(url="/admin/employees", status_code=303)
    if not current_admin.is_super_admin:
        if emp.school_id != current_admin.school_id or emp.is_admin:
            return _no_access(request)
        school_id = current_admin.school_id
        is_admin = False
    emp.username = username
    emp.first_name = first_name
    emp.last_name = last_name
    emp.email = email
    emp.is_admin = is_admin
    emp.is_active = is_active
    emp.school_id = school_id
    emp.staff_title_id = staff_title_id
    emp.updated_at = datetime.utcnow()
    if password:
        emp.set_password(password)
    await db.execute(delete(TeacherClass).where(TeacherClass.teacher_id == id))
    for cid in assigned_classes:
        db.add(TeacherClass(teacher_id=id, class_id=int(cid)))
    await db.execute(delete(TeacherSubject).where(TeacherSubject.teacher_id == id))
    for sid in assigned_subjects:
        db.add(TeacherSubject(teacher_id=id, subject_id=int(sid)))
    await db.commit()
    flash(request, "Xodim ma'lumotlari yangilandi", 'success')
    return RedirectResponse(url="/admin/employees", status_code=303)


@router.post("/employees/delete/{id}")
async def delete_employee(request: Request, id: int, db: AsyncSession = Depends(get_db),
                          current_admin: Employee = Depends(require_admin)):
    if id == request.session.get('user_id'):
        flash(request, "O'zingizni o'chira olmaysiz", 'danger')
        return RedirectResponse(url="/admin/employees", status_code=303)
    emp = (await db.execute(select(Employee).where(Employee.id == id))).scalar_one_or_none()
    if not emp:
        flash(request, 'Xodim topilmadi', 'danger')
        return RedirectResponse(url="/admin/employees", status_code=303)
    if not current_admin.is_super_admin and (emp.school_id != current_admin.school_id or emp.is_admin):
        return _no_access(request)
    try:
        for exam in (await db.execute(select(Exam).where(Exam.teacher_id == id))).scalars().all():
            # Delete exam_results first (references questions.id via FK)
            await db.execute(delete(ExamResult).where(ExamResult.exam_id == exam.id))
            await db.execute(delete(Question).where(Question.exam_id == exam.id))
            await db.delete(exam)
        await db.delete(emp)
        await db.commit()
        await cache_del_admin_stats()
        await cache_del_home_stats()
        await cache_del_user(id)
        flash(request, "Xodim va uning yaratgan imtihonlari o'chirildi", 'success')
    except Exception as e:
        await db.rollback()
        flash(request, f"Xodimni o'chirishda xatolik: {e}", 'danger')
    return RedirectResponse(url="/admin/employees", status_code=303)


@router.post("/employees/toggle-status/{id}")
async def toggle_employee_status(request: Request, id: int, db: AsyncSession = Depends(get_db),
                                 current_admin: Employee = Depends(require_admin)):
    if id == request.session.get('user_id'):
        flash(request, "O'zingizni faolligini o'zgartira olmaysiz", 'danger')
        return RedirectResponse(url="/admin/employees", status_code=303)
    emp = (await db.execute(select(Employee).where(Employee.id == id))).scalar_one_or_none()
    if not emp:
        flash(request, 'Xodim topilmadi', 'danger')
        return RedirectResponse(url="/admin/employees", status_code=303)
    if not current_admin.is_super_admin and (emp.school_id != current_admin.school_id or emp.is_admin):
        return _no_access(request)
    emp.is_active = not emp.is_active
    emp.updated_at = datetime.utcnow()
    await db.commit()
    status = "faollashtirildi" if emp.is_active else "bloklandi"
    flash(request, f"Xodim {status}", 'success')
    return RedirectResponse(url="/admin/employees", status_code=303)
