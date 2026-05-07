"""Admin school management routes."""
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from config import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func

from models import get_db, School, Employee, SchoolClass, Student, Exam, Question, ExamResult
from dependencies import require_admin, flash, get_template_context, page_info

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory="templates")


@router.get("/schools", response_class=HTMLResponse)
async def schools_list(request: Request, page: int = 1, db: AsyncSession = Depends(get_db)):
    per_page = 10
    total = (await db.execute(select(func.count(School.id)))).scalar()
    pg = page_info(total, page, per_page, request)
    result = await db.execute(
        select(School).order_by(School.created_at.desc())
        .offset(pg['row_offset']).limit(per_page)
    )
    schools = result.scalars().all()
    context = await get_template_context(request)
    context.update({'schools': schools, **pg})
    return templates.TemplateResponse('admin/schools.html', context)


@router.get("/schools/add", response_class=HTMLResponse)
async def add_school_page(request: Request):
    context = await get_template_context(request)
    context['school'] = None
    return templates.TemplateResponse('admin/school_form.html', context)


@router.post("/schools/add")
async def add_school(
    request: Request,
    name: str = Form(...), address: str = Form(""),
    phone: str = Form(""), email: str = Form(""),
    db: AsyncSession = Depends(get_db)
):
    db.add(School(name=name, address=address, phone=phone, email=email))
    await db.commit()
    flash(request, "Maktab muvaffaqiyatli qo'shildi", 'success')
    return RedirectResponse(url="/admin/schools", status_code=303)


@router.get("/schools/edit/{id}", response_class=HTMLResponse)
async def edit_school_page(request: Request, id: int, db: AsyncSession = Depends(get_db)):
    school = (await db.execute(select(School).where(School.id == id))).scalar_one_or_none()
    if not school:
        flash(request, 'Maktab topilmadi', 'danger')
        return RedirectResponse(url="/admin/schools", status_code=303)
    context = await get_template_context(request)
    context['school'] = school
    return templates.TemplateResponse('admin/school_form.html', context)


@router.post("/schools/edit/{id}")
async def edit_school(
    request: Request, id: int,
    name: str = Form(...), address: str = Form(""),
    phone: str = Form(""), email: str = Form(""),
    db: AsyncSession = Depends(get_db)
):
    school = (await db.execute(select(School).where(School.id == id))).scalar_one_or_none()
    if not school:
        flash(request, 'Maktab topilmadi', 'danger')
        return RedirectResponse(url="/admin/schools", status_code=303)
    school.name, school.address, school.phone, school.email = name, address, phone, email
    await db.commit()
    flash(request, "Maktab ma'lumotlari yangilandi", 'success')
    return RedirectResponse(url="/admin/schools", status_code=303)


@router.post("/schools/delete/{id}")
async def delete_school(request: Request, id: int, db: AsyncSession = Depends(get_db)):
    school = (await db.execute(select(School).where(School.id == id))).scalar_one_or_none()
    if not school:
        flash(request, 'Maktab topilmadi', 'danger')
        return RedirectResponse(url="/admin/schools", status_code=303)
    try:
        classes_in_school = (await db.execute(
            select(SchoolClass).where(SchoolClass.school_id == id)
        )).scalars().all()
        for cls in classes_in_school:
            for exam in (await db.execute(select(Exam).where(Exam.class_id == cls.id))).scalars().all():
                await db.execute(delete(Question).where(Question.exam_id == exam.id))
                await db.execute(delete(ExamResult).where(ExamResult.exam_id == exam.id))
                await db.delete(exam)
            await db.execute(delete(Student).where(Student.class_id == cls.id))
            await db.delete(cls)
        for emp in (await db.execute(select(Employee).where(Employee.school_id == id))).scalars().all():
            emp.school_id = None
        await db.delete(school)
        await db.commit()
        flash(request, "Maktab va unga bog'liq barcha ma'lumotlar o'chirildi", 'success')
    except Exception as e:
        await db.rollback()
        flash(request, f"Maktabni o'chirishda xatolik: {e}", 'danger')
    return RedirectResponse(url="/admin/schools", status_code=303)
