"""Admin class management routes."""
from typing import Optional

from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from config import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func

from models import get_db, School, SchoolClass, Student, Exam, Question, ExamResult
from dependencies import require_admin, flash, get_template_context, page_info
from utils import process_student_excel

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory="templates")


@router.get("/classes", response_class=HTMLResponse)
async def classes_list(
    request: Request, school_id: Optional[str] = None, page: int = 1,
    db: AsyncSession = Depends(get_db)
):
    per_page = 10
    sid = None
    if school_id and school_id.strip():
        try:
            sid = int(school_id)
        except ValueError:
            pass

    base_q = select(SchoolClass)
    count_q = select(func.count(SchoolClass.id))
    if sid:
        base_q = base_q.where(SchoolClass.school_id == sid)
        count_q = count_q.where(SchoolClass.school_id == sid)
    else:
        base_q = base_q.order_by(SchoolClass.created_at.desc())

    total = (await db.execute(count_q)).scalar()
    pg = page_info(total, page, per_page, request)
    classes = (await db.execute(base_q.offset(pg['row_offset']).limit(per_page))).scalars().all()
    schools = (await db.execute(select(School))).scalars().all()

    class_ids = [c.id for c in classes]
    student_counts = dict(
        (await db.execute(
            select(Student.class_id, func.count(Student.id))
            .where(Student.class_id.in_(class_ids))
            .group_by(Student.class_id)
        )).all()
    ) if class_ids else {}

    context = await get_template_context(request)
    context.update({'classes': classes, 'schools': schools, 'student_counts': student_counts, **pg})
    return templates.TemplateResponse('admin/classes.html', context)


@router.get("/classes/add", response_class=HTMLResponse)
async def add_class_page(request: Request, db: AsyncSession = Depends(get_db)):
    schools = (await db.execute(select(School))).scalars().all()
    context = await get_template_context(request)
    context.update({'class_obj': None, 'schools': schools})
    return templates.TemplateResponse('admin/class_form.html', context)


@router.post("/classes/add")
async def add_class(
    request: Request,
    name: str = Form(...), school_id: int = Form(...),
    leader_first_name: Optional[str] = Form(None),
    leader_last_name: Optional[str] = Form(None),
    leader_phone: Optional[str] = Form(None),
    students_file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db)
):
    cls = SchoolClass(name=name, school_id=school_id,
                      leader_first_name=leader_first_name,
                      leader_last_name=leader_last_name,
                      leader_phone=leader_phone)
    db.add(cls)
    await db.flush()
    if students_file and students_file.filename:
        try:
            for s in await process_student_excel(students_file):
                db.add(Student(first_name=s['first_name'], last_name=s['last_name'],
                               gender=s['gender'], group_number=s['group_number'],
                               class_id=cls.id))
        except Exception as e:
            flash(request, f"Excel faylni o'qishda xatolik: {e}", 'danger')
    await db.commit()
    flash(request, "Sinf va o'quvchilar qo'shildi", 'success')
    return RedirectResponse(url="/admin/classes", status_code=303)


@router.get("/classes/edit/{id}", response_class=HTMLResponse)
async def edit_class_page(request: Request, id: int, db: AsyncSession = Depends(get_db)):
    cls = (await db.execute(select(SchoolClass).where(SchoolClass.id == id))).scalar_one_or_none()
    if not cls:
        flash(request, 'Sinf topilmadi', 'danger')
        return RedirectResponse(url="/admin/classes", status_code=303)
    schools = (await db.execute(select(School))).scalars().all()
    context = await get_template_context(request)
    context.update({'class_obj': cls, 'schools': schools})
    return templates.TemplateResponse('admin/class_form.html', context)


@router.post("/classes/edit/{id}")
async def edit_class(
    request: Request, id: int,
    name: str = Form(...), school_id: int = Form(...),
    leader_first_name: Optional[str] = Form(None),
    leader_last_name: Optional[str] = Form(None),
    leader_phone: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    cls = (await db.execute(select(SchoolClass).where(SchoolClass.id == id))).scalar_one_or_none()
    if not cls:
        flash(request, 'Sinf topilmadi', 'danger')
        return RedirectResponse(url="/admin/classes", status_code=303)
    cls.name = name
    cls.school_id = school_id
    cls.leader_first_name = leader_first_name
    cls.leader_last_name = leader_last_name
    cls.leader_phone = leader_phone
    await db.commit()
    flash(request, "Sinf ma'lumotlari yangilandi", 'success')
    return RedirectResponse(url="/admin/classes", status_code=303)


@router.post("/classes/delete/{id}")
async def delete_class(request: Request, id: int, db: AsyncSession = Depends(get_db)):
    cls = (await db.execute(select(SchoolClass).where(SchoolClass.id == id))).scalar_one_or_none()
    if not cls:
        flash(request, 'Sinf topilmadi', 'danger')
        return RedirectResponse(url="/admin/classes", status_code=303)
    try:
        for exam in (await db.execute(select(Exam).where(Exam.class_id == id))).scalars().all():
            await db.execute(delete(Question).where(Question.exam_id == exam.id))
            await db.execute(delete(ExamResult).where(ExamResult.exam_id == exam.id))
            await db.delete(exam)
        await db.execute(delete(Student).where(Student.class_id == id))
        await db.delete(cls)
        await db.commit()
        flash(request, "Sinf va unga bog'liq barcha ma'lumotlar o'chirildi", 'success')
    except Exception as e:
        await db.rollback()
        flash(request, f"Sinfni o'chirishda xatolik: {e}", 'danger')
    return RedirectResponse(url="/admin/classes", status_code=303)
