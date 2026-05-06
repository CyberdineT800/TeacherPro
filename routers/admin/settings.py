"""Admin reference-table management (subjects, quarters, exam names/types, question types, staff titles, languages)."""
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from models import (
    get_db, Subject, Quarter, ExamName, ExamType, QuestionType, StaffTitle, Exam,
)
from dependencies import require_admin, flash, get_template_context, page_info
from language import language_manager

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory="templates")


# ── Language management ──────────────────────────────────────────────────────

@router.get("/languages", response_class=HTMLResponse)
async def manage_languages(request: Request, db: AsyncSession = Depends(get_db)):
    all_keys: set = set()
    for t in language_manager.translations.values():
        all_keys.update(t.keys())
    translations_data = [
        {'key': k,
         'uz': language_manager.get(k, 'uz', ''),
         'ru': language_manager.get(k, 'ru', ''),
         'en': language_manager.get(k, 'en', '')}
        for k in sorted(all_keys)
    ]
    context = await get_template_context(request, db)
    context.update({'translations': translations_data,
                    'languages': language_manager.get_available_languages()})
    return templates.TemplateResponse('admin/languages.html', context)


@router.post("/languages/save")
async def save_translation(
    request: Request,
    key: str = Form(...), value_uz: str = Form(""),
    value_ru: str = Form(""), value_en: str = Form(""),
    original_key: str = Form(""), db: AsyncSession = Depends(get_db)
):
    try:
        if original_key and original_key != key:
            for lang in ['uz', 'ru', 'en']:
                language_manager.delete_translation(lang, original_key)
        if value_uz:
            language_manager.save_translation('uz', key, value_uz)
        if value_ru:
            language_manager.save_translation('ru', key, value_ru)
        if value_en:
            language_manager.save_translation('en', key, value_en)
        flash(request, 'Tarjima saqlandi', 'success')
    except Exception as e:
        flash(request, f'Xatolik: {e}', 'danger')
    return RedirectResponse(url="/admin/languages", status_code=303)


@router.post("/languages/delete/{key}")
async def delete_translation(request: Request, key: str, db: AsyncSession = Depends(get_db)):
    try:
        for lang in ['uz', 'ru', 'en']:
            language_manager.delete_translation(lang, key)
        flash(request, "Tarjima o'chirildi", 'success')
    except Exception as e:
        flash(request, f'Xatolik: {e}', 'danger')
    return RedirectResponse(url="/admin/languages", status_code=303)


# ── Subjects ─────────────────────────────────────────────────────────────────

@router.get("/subjects", response_class=HTMLResponse)
async def subjects_list(request: Request, page: int = 1, db: AsyncSession = Depends(get_db)):
    per_page = 10
    total = (await db.execute(select(func.count(Subject.id)))).scalar()
    pg = page_info(total, page, per_page, request)
    subjects = (await db.execute(select(Subject).offset(pg['row_offset']).limit(per_page))).scalars().all()
    lang = request.session.get('language', 'uz')
    context = await get_template_context(request)
    context.update({'items': subjects, 'title': language_manager.get('subjects', lang),
                    'add_url': 'add_subject', 'delete_url': 'delete_subject', **pg})
    return templates.TemplateResponse('admin/simple_list.html', context)


@router.post("/subjects/add")
async def add_subject(request: Request, name: str = Form(...), db: AsyncSession = Depends(get_db)):
    if name:
        db.add(Subject(name=name))
        await db.commit()
        flash(request, "Fan qo'shildi", 'success')
    return RedirectResponse(url="/admin/subjects", status_code=303)


@router.post("/subjects/delete/{id}")
async def delete_subject(request: Request, id: int, db: AsyncSession = Depends(get_db)):
    subject = (await db.execute(select(Subject).where(Subject.id == id))).scalar_one_or_none()
    if not subject:
        flash(request, 'Fan topilmadi', 'danger')
        return RedirectResponse(url="/admin/subjects", status_code=303)
    if (await db.execute(select(Exam).where(Exam.subject_id == id).limit(1))).scalar_one_or_none():
        flash(request, "Bu fan hozirda imtihonlarda ishlatilmoqda.", 'danger')
        return RedirectResponse(url="/admin/subjects", status_code=303)
    try:
        await db.delete(subject)
        await db.commit()
        flash(request, "Fan o'chirildi", 'success')
    except Exception as e:
        await db.rollback()
        flash(request, f"Fanni o'chirishda xatolik: {e}", 'danger')
    return RedirectResponse(url="/admin/subjects", status_code=303)


# ── Quarters ─────────────────────────────────────────────────────────────────

@router.get("/quarters", response_class=HTMLResponse)
async def quarters_list(request: Request, page: int = 1, db: AsyncSession = Depends(get_db)):
    per_page = 10
    total = (await db.execute(select(func.count(Quarter.id)))).scalar()
    pg = page_info(total, page, per_page, request)
    quarters = (await db.execute(
        select(Quarter).order_by(Quarter.order_num).offset(pg['row_offset']).limit(per_page)
    )).scalars().all()
    context = await get_template_context(request)
    context.update({'quarters': quarters, **pg})
    return templates.TemplateResponse('admin/quarters.html', context)


@router.post("/quarters/add")
async def add_quarter(request: Request, name: str = Form(...), order_num: int = Form(...),
                      db: AsyncSession = Depends(get_db)):
    if name and order_num:
        db.add(Quarter(name=name, order_num=order_num))
        await db.commit()
        flash(request, "Chorak qo'shildi", 'success')
    return RedirectResponse(url="/admin/quarters", status_code=303)


@router.post("/quarters/delete/{id}")
async def delete_quarter(request: Request, id: int, db: AsyncSession = Depends(get_db)):
    q = (await db.execute(select(Quarter).where(Quarter.id == id))).scalar_one_or_none()
    if q:
        await db.delete(q)
        await db.commit()
        flash(request, "Chorak o'chirildi", 'success')
    return RedirectResponse(url="/admin/quarters", status_code=303)


# ── Exam names ────────────────────────────────────────────────────────────────

@router.get("/exam-names", response_class=HTMLResponse)
async def exam_names_list(request: Request, page: int = 1, db: AsyncSession = Depends(get_db)):
    per_page = 10
    total = (await db.execute(select(func.count(ExamName.id)))).scalar()
    pg = page_info(total, page, per_page, request)
    items = (await db.execute(select(ExamName).offset(pg['row_offset']).limit(per_page))).scalars().all()
    lang = request.session.get('language', 'uz')
    context = await get_template_context(request)
    context.update({'items': items, 'title': language_manager.get('exam_names', lang),
                    'add_url': 'add_exam_name', 'delete_url': 'delete_exam_name', **pg})
    return templates.TemplateResponse('admin/simple_list.html', context)


@router.post("/exam-names/add")
async def add_exam_name(request: Request, name: str = Form(...), db: AsyncSession = Depends(get_db)):
    if name:
        db.add(ExamName(name=name))
        await db.commit()
        flash(request, "Imtihon nomi qo'shildi", 'success')
    return RedirectResponse(url="/admin/exam-names", status_code=303)


@router.post("/exam-names/delete/{id}")
async def delete_exam_name(request: Request, id: int, db: AsyncSession = Depends(get_db)):
    item = (await db.execute(select(ExamName).where(ExamName.id == id))).scalar_one_or_none()
    if item:
        await db.delete(item)
        await db.commit()
        flash(request, "Imtihon nomi o'chirildi", 'success')
    return RedirectResponse(url="/admin/exam-names", status_code=303)


# ── Exam types ────────────────────────────────────────────────────────────────

@router.get("/exam-types", response_class=HTMLResponse)
async def exam_types_list(request: Request, page: int = 1, db: AsyncSession = Depends(get_db)):
    per_page = 10
    total = (await db.execute(select(func.count(ExamType.id)))).scalar()
    pg = page_info(total, page, per_page, request)
    items = (await db.execute(select(ExamType).offset(pg['row_offset']).limit(per_page))).scalars().all()
    lang = request.session.get('language', 'uz')
    context = await get_template_context(request)
    context.update({'items': items, 'title': language_manager.get('exam_types', lang),
                    'add_url': 'add_exam_type', 'delete_url': 'delete_exam_type', **pg})
    return templates.TemplateResponse('admin/simple_list.html', context)


@router.post("/exam-types/add")
async def add_exam_type(request: Request, name: str = Form(...), db: AsyncSession = Depends(get_db)):
    if name:
        db.add(ExamType(name=name))
        await db.commit()
        flash(request, "Imtihon turi qo'shildi", 'success')
    return RedirectResponse(url="/admin/exam-types", status_code=303)


@router.post("/exam-types/delete/{id}")
async def delete_exam_type(request: Request, id: int, db: AsyncSession = Depends(get_db)):
    item = (await db.execute(select(ExamType).where(ExamType.id == id))).scalar_one_or_none()
    if item:
        await db.delete(item)
        await db.commit()
        flash(request, "Imtihon turi o'chirildi", 'success')
    return RedirectResponse(url="/admin/exam-types", status_code=303)


# ── Question types ────────────────────────────────────────────────────────────

@router.get("/question-types", response_class=HTMLResponse)
async def question_types_list(request: Request, page: int = 1, db: AsyncSession = Depends(get_db)):
    per_page = 10
    total = (await db.execute(select(func.count(QuestionType.id)))).scalar()
    pg = page_info(total, page, per_page, request)
    items = (await db.execute(select(QuestionType).offset(pg['row_offset']).limit(per_page))).scalars().all()
    lang = request.session.get('language', 'uz')
    context = await get_template_context(request)
    context.update({'items': items, 'title': language_manager.get('question_types', lang),
                    'add_url': 'add_question_type', 'delete_url': 'delete_question_type', **pg})
    return templates.TemplateResponse('admin/simple_list.html', context)


@router.post("/question-types/add")
async def add_question_type(request: Request, name: str = Form(...), db: AsyncSession = Depends(get_db)):
    if name:
        db.add(QuestionType(name=name))
        await db.commit()
        flash(request, "Savol turi qo'shildi", 'success')
    return RedirectResponse(url="/admin/question-types", status_code=303)


@router.post("/question-types/delete/{id}")
async def delete_question_type(request: Request, id: int, db: AsyncSession = Depends(get_db)):
    item = (await db.execute(select(QuestionType).where(QuestionType.id == id))).scalar_one_or_none()
    if item:
        await db.delete(item)
        await db.commit()
        flash(request, "Savol turi o'chirildi", 'success')
    return RedirectResponse(url="/admin/question-types", status_code=303)


# ── Staff titles ──────────────────────────────────────────────────────────────

@router.get("/staff-titles", response_class=HTMLResponse)
async def staff_titles_list(request: Request, page: int = 1, db: AsyncSession = Depends(get_db)):
    per_page = 10
    total = (await db.execute(select(func.count(StaffTitle.id)))).scalar()
    pg = page_info(total, page, per_page, request)
    items = (await db.execute(select(StaffTitle).offset(pg['row_offset']).limit(per_page))).scalars().all()
    lang = request.session.get('language', 'uz')
    context = await get_template_context(request)
    context.update({'items': items, 'title': language_manager.get('staff_titles', lang),
                    'add_url': 'add_staff_title', 'delete_url': 'delete_staff_title', **pg})
    return templates.TemplateResponse('admin/simple_list.html', context)


@router.post("/staff-titles/add")
async def add_staff_title(request: Request, name: str = Form(...), db: AsyncSession = Depends(get_db)):
    if name:
        db.add(StaffTitle(title=name))
        await db.commit()
        flash(request, "Lavozim qo'shildi", 'success')
    return RedirectResponse(url="/admin/staff-titles", status_code=303)


@router.post("/staff-titles/delete/{id}")
async def delete_staff_title(request: Request, id: int, db: AsyncSession = Depends(get_db)):
    item = (await db.execute(select(StaffTitle).where(StaffTitle.id == id))).scalar_one_or_none()
    if item:
        await db.delete(item)
        await db.commit()
        flash(request, "Lavozim o'chirildi", 'success')
    return RedirectResponse(url="/admin/staff-titles", status_code=303)
