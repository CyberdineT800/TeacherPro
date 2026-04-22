"""AI question/test generator routes (teacher + admin)."""
import json
import logging
import traceback
from datetime import date
from io import BytesIO
from typing import Optional
from urllib.parse import quote

log = logging.getLogger("ai_questions")

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import get_db, Employee, Subject, AIQuestionSet
from dependencies import require_login, require_admin, flash, get_template_context, page_info
from ai_service import generate_questions
from language import language_manager

router = APIRouter()
templates = Jinja2Templates(directory="templates")

LANGUAGE_DISPLAY = {
    'uz': "O'zbekcha",
    'ru': "Русский",
    'en': "English",
}

TYPE_DISPLAY = {
    'test': "Test (MCQ)",
    'open': "Ochiq savollar",
}


def _t(request: Request, key: str) -> str:
    lang = request.session.get('language', 'uz')
    return language_manager.get(key, lang)


def _reset_if_new_day(teacher: Employee):
    today = date.today()
    if teacher.ai_questions_last_reset != today:
        teacher.ai_questions_used_today = 0
        teacher.ai_questions_last_reset = today


# ============================================================================
# TEACHER ROUTES
# ============================================================================

@router.get("/teacher/ai-questions", response_class=HTMLResponse, dependencies=[Depends(require_login)])
async def teacher_questions_list(request: Request, page: int = 1, db: AsyncSession = Depends(get_db)):
    per_page = 6
    teacher_id = request.session.get('user_id')
    teacher = (await db.execute(select(Employee).where(Employee.id == teacher_id))).scalar_one()

    if not teacher.ai_enabled:
        flash(request, _t(request, 'ai_disabled_for_you'), 'warning')
        return RedirectResponse(url="/teacher/dashboard", status_code=303)

    _reset_if_new_day(teacher)
    await db.commit()

    total = (await db.execute(
        select(func.count(AIQuestionSet.id)).where(AIQuestionSet.teacher_id == teacher_id)
    )).scalar()
    pg = page_info(total, page, per_page, request)

    question_sets = (await db.execute(
        select(AIQuestionSet)
        .where(AIQuestionSet.teacher_id == teacher_id)
        .order_by(AIQuestionSet.created_at.desc())
        .offset(pg['row_offset']).limit(per_page)
    )).scalars().all()

    context = await get_template_context(request, db)
    context.update({
        'question_sets': question_sets,
        'teacher': teacher,
        'remaining': max(0, teacher.ai_questions_daily_limit - teacher.ai_questions_used_today),
        'language_display': LANGUAGE_DISPLAY,
        'type_display': TYPE_DISPLAY,
        **pg,
    })
    return templates.TemplateResponse('teacher/ai_questions_list.html', context)


@router.get("/teacher/ai-questions/create", response_class=HTMLResponse, dependencies=[Depends(require_login)])
async def teacher_questions_create_form(request: Request, db: AsyncSession = Depends(get_db)):
    teacher_id = request.session.get('user_id')
    teacher = (await db.execute(select(Employee).where(Employee.id == teacher_id))).scalar_one()

    if not teacher.ai_enabled:
        flash(request, _t(request, 'ai_disabled_short'), 'warning')
        return RedirectResponse(url="/teacher/dashboard", status_code=303)

    _reset_if_new_day(teacher)
    await db.commit()

    if teacher.ai_questions_used_today >= teacher.ai_questions_daily_limit:
        flash(request, _t(request, 'ai_limit_reached_msg'), 'warning')
        return RedirectResponse(url="/teacher/ai-questions", status_code=303)

    subjects = (await db.execute(select(Subject).order_by(Subject.name))).scalars().all()

    context = await get_template_context(request, db)
    context.update({
        'subjects': subjects,
        'remaining': teacher.ai_questions_daily_limit - teacher.ai_questions_used_today,
    })
    return templates.TemplateResponse('teacher/ai_questions_create.html', context)


@router.post("/teacher/ai-questions/generate", dependencies=[Depends(require_login)])
async def teacher_questions_generate(
    request: Request,
    subject_id: int = Form(...),
    grade: int = Form(...),
    topic: str = Form(...),
    language: str = Form('uz'),
    question_type: str = Form('test'),
    question_count: int = Form(10),
    db: AsyncSession = Depends(get_db),
):
    teacher_id = request.session.get('user_id')
    teacher = (await db.execute(select(Employee).where(Employee.id == teacher_id))).scalar_one()

    if not teacher.ai_enabled:
        return JSONResponse({'ok': False, 'error': _t(request, 'ai_disabled_short')}, status_code=403)

    _reset_if_new_day(teacher)

    if teacher.ai_questions_used_today >= teacher.ai_questions_daily_limit:
        return JSONResponse({'ok': False, 'error': _t(request, 'ai_limit_reached_short')}, status_code=429)

    if not (1 <= grade <= 11):
        return JSONResponse({'ok': False, 'error': _t(request, 'ai_invalid_grade')}, status_code=400)

    topic = (topic or '').strip()
    if not topic or len(topic) > 300:
        return JSONResponse({'ok': False, 'error': _t(request, 'ai_invalid_topic')}, status_code=400)

    if language not in ('uz', 'ru', 'en'):
        language = 'uz'

    if question_type == 'test':
        question_count = max(10, min(30, question_count))
    else:
        question_type = 'open'
        question_count = max(10, min(15, question_count))

    subject = (await db.execute(select(Subject).where(Subject.id == subject_id))).scalar_one_or_none()
    if not subject:
        return JSONResponse({'ok': False, 'error': _t(request, 'ai_subject_not_found')}, status_code=400)

    try:
        data = await generate_questions(subject.name, grade, topic, language, question_type, question_count)
    except Exception as e:
        log.error("Question generation failed: %s\n%s", e, traceback.format_exc())
        return JSONResponse({'ok': False, 'error': f"{_t(request, 'ai_error_prefix')}: {str(e)[:200]}"}, status_code=500)

    actual_count = len(data.get('questions', []))

    qs = AIQuestionSet(
        teacher_id=teacher_id,
        subject_name=subject.name,
        grade=grade,
        topic=topic,
        language=language,
        question_type=question_type,
        question_count=actual_count,
        content=json.dumps(data, ensure_ascii=False),
    )
    db.add(qs)

    teacher.ai_questions_used_today += 1
    teacher.ai_questions_last_reset = date.today()

    await db.commit()
    await db.refresh(qs)

    return JSONResponse({'ok': True, 'id': qs.id, 'redirect': f"/teacher/ai-questions/{qs.id}"})


@router.get("/teacher/ai-questions/{qid}", response_class=HTMLResponse, dependencies=[Depends(require_login)])
async def teacher_questions_view(qid: int, request: Request, db: AsyncSession = Depends(get_db)):
    teacher_id = request.session.get('user_id')
    qs = (await db.execute(
        select(AIQuestionSet).where(AIQuestionSet.id == qid)
    )).scalar_one_or_none()

    if not qs:
        raise HTTPException(404)

    is_admin = request.session.get('is_admin', False)
    if not is_admin and qs.teacher_id != teacher_id:
        raise HTTPException(403)

    data = json.loads(qs.content)

    context = await get_template_context(request, db)
    context.update({
        'qs': qs,
        'data': data,
        'language_display': LANGUAGE_DISPLAY,
        'type_display': TYPE_DISPLAY,
        'is_admin': is_admin,
    })
    return templates.TemplateResponse('teacher/ai_questions_view.html', context)


@router.get("/teacher/ai-questions/{qid}/pdf", dependencies=[Depends(require_login)])
async def teacher_questions_pdf(qid: int, request: Request, db: AsyncSession = Depends(get_db)):
    teacher_id = request.session.get('user_id')
    qs = (await db.execute(
        select(AIQuestionSet).where(AIQuestionSet.id == qid)
    )).scalar_one_or_none()

    if not qs:
        raise HTTPException(404)

    is_admin = request.session.get('is_admin', False)
    if not is_admin and qs.teacher_id != teacher_id:
        raise HTTPException(403)

    try:
        data = json.loads(qs.content)
        teacher = (await db.execute(select(Employee).where(Employee.id == qs.teacher_id))).scalar_one()
        teacher_name = f"{teacher.first_name} {teacher.last_name}"
        pdf_bytes = _build_question_pdf(data, qs, teacher_name)
    except Exception as e:
        log.error("PDF build failed for question set %s: %s\n%s", qid, e, traceback.format_exc())
        raise HTTPException(500, detail=f"PDF yaratishda xatolik: {e}")

    ascii_name = ''.join(c if c.isascii() and c.isalnum() else '_' for c in qs.topic)[:50] or 'questions'
    ascii_filename = f"{ascii_name}_grade{qs.grade}.pdf"
    utf8_filename = quote(f"{qs.topic[:50]}_{qs.grade}sinf.pdf")

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{utf8_filename}",
            "Content-Length": str(len(pdf_bytes)),
        },
    )


@router.post("/teacher/ai-questions/{qid}/delete", dependencies=[Depends(require_login)])
async def teacher_questions_delete(qid: int, request: Request, db: AsyncSession = Depends(get_db)):
    teacher_id = request.session.get('user_id')
    qs = (await db.execute(
        select(AIQuestionSet).where(AIQuestionSet.id == qid)
    )).scalar_one_or_none()

    if not qs:
        raise HTTPException(404)

    is_admin = request.session.get('is_admin', False)
    if not is_admin and qs.teacher_id != teacher_id:
        raise HTTPException(403)

    await db.delete(qs)
    await db.commit()
    flash(request, _t(request, 'ai_presentation_deleted'), 'success')

    redirect = "/admin/ai-questions" if is_admin else "/teacher/ai-questions"
    return RedirectResponse(url=redirect, status_code=303)


# ============================================================================
# ADMIN ROUTES
# ============================================================================

@router.get("/admin/ai-questions", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def admin_questions_list(
    request: Request,
    teacher_id: Optional[str] = None,
    page: int = 1,
    db: AsyncSession = Depends(get_db),
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
    context.update({
        'items': items,
        'teachers': teachers,
        'selected_teacher_id': tid,
        'language_display': LANGUAGE_DISPLAY,
        'type_display': TYPE_DISPLAY,
        **pg,
    })
    return templates.TemplateResponse('admin/ai_questions.html', context)


# ============================================================================
# PDF BUILDER
# ============================================================================

def _build_question_pdf(data: dict, qs: AIQuestionSet, teacher_name: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib import colors
    from utils import _PDF_FONT, _PDF_FONT_BOLD

    output = BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=A4,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        leftMargin=0.8 * inch, rightMargin=0.8 * inch,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('QTitle', parent=styles['Normal'],
        fontName=_PDF_FONT_BOLD, fontSize=13, alignment=TA_CENTER, spaceAfter=4)
    sub_style = ParagraphStyle('QSub', parent=styles['Normal'],
        fontName=_PDF_FONT, fontSize=10, alignment=TA_CENTER, spaceAfter=2, textColor=colors.HexColor('#555555'))
    q_style = ParagraphStyle('QBody', parent=styles['Normal'],
        fontName=_PDF_FONT_BOLD, fontSize=11, spaceAfter=4, spaceBefore=10, leading=15)
    opt_style = ParagraphStyle('QOpt', parent=styles['Normal'],
        fontName=_PDF_FONT, fontSize=10, spaceAfter=3, leftIndent=16, leading=14)
    key_style = ParagraphStyle('QKey', parent=styles['Normal'],
        fontName=_PDF_FONT, fontSize=10, spaceAfter=3, leading=14)
    section_style = ParagraphStyle('QSection', parent=styles['Normal'],
        fontName=_PDF_FONT_BOLD, fontSize=12, spaceBefore=12, spaceAfter=8,
        borderPad=4, backColor=colors.HexColor('#E8F0FF'),
        borderColor=colors.HexColor('#2244AA'), borderWidth=0,
        leftIndent=0, alignment=TA_LEFT)

    lang_name = {'uz': "O'zbekcha", 'ru': "Ruscha", 'en': "Inglizcha"}.get(qs.language, qs.language)
    type_name = "Test (MCQ)" if qs.question_type == 'test' else "Ochiq savollar"

    elements = []

    title_text = data.get('title') or qs.topic
    elements.append(Paragraph(title_text, title_style))
    elements.append(Paragraph(
        f"{qs.subject_name}  |  {qs.grade}-sinf  |  {lang_name}  |  {type_name}  |  {qs.question_count} ta savol",
        sub_style))
    elements.append(Spacer(1, 0.15 * inch))

    # Horizontal rule
    elements.append(Table([['']], colWidths=[6.4 * inch],
        style=[('LINEABOVE', (0, 0), (-1, 0), 1.2, colors.HexColor('#CCCCCC'))]))
    elements.append(Spacer(1, 0.1 * inch))

    questions = data.get('questions', [])

    if qs.question_type == 'test':
        elements.append(Paragraph("Savollar", section_style))
        for q in questions:
            num = q.get('number', '')
            qtext = q.get('question', '')
            elements.append(Paragraph(f"{num}. {qtext}", q_style))
            for opt in q.get('options', []):
                elements.append(Paragraph(opt, opt_style))
            elements.append(Spacer(1, 0.05 * inch))

        # Answer key on new page
        elements.append(PageBreak())
        elements.append(Paragraph(title_text, title_style))
        elements.append(Paragraph(
            f"{qs.subject_name}  |  {qs.grade}-sinf  —  Javoblar kaliti",
            sub_style))
        elements.append(Spacer(1, 0.15 * inch))
        elements.append(Table([['']], colWidths=[6.4 * inch],
            style=[('LINEABOVE', (0, 0), (-1, 0), 1.2, colors.HexColor('#CCCCCC'))]))
        elements.append(Spacer(1, 0.1 * inch))
        elements.append(Paragraph("Javoblar kaliti", section_style))

        letters = ['A', 'B', 'C', 'D']
        key_data = [['Savol', 'Javob']]
        for q in questions:
            correct_idx = q.get('correct', 0)
            letter = letters[correct_idx] if 0 <= correct_idx < 4 else str(correct_idx)
            key_data.append([str(q.get('number', '')), letter])

        # Arrange in 4 columns to save space
        mid = (len(key_data) - 1 + 3) // 4
        cols = []
        for col_start in range(0, len(key_data) - 1, mid):
            col = key_data[1:][col_start:col_start + mid]
            cols.append(col)

        max_rows = max(len(c) for c in cols)
        table_data_key = [['Savol', 'Javob'] * len(cols)]
        for i in range(max_rows):
            row = []
            for col in cols:
                if i < len(col):
                    row.extend(col[i])
                else:
                    row.extend(['', ''])
            table_data_key.append(row)

        col_w = 6.4 * inch / (len(cols) * 2)
        key_table = Table(table_data_key, colWidths=[col_w] * (len(cols) * 2))
        key_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), _PDF_FONT_BOLD),
            ('FONTNAME', (0, 1), (-1, -1), _PDF_FONT),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D9E8FF')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#AAAAAA')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')]),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(key_table)

    else:
        elements.append(Paragraph("Savollar", section_style))
        for q in questions:
            num = q.get('number', '')
            qtext = q.get('question', '')
            elements.append(Paragraph(f"{num}. {qtext}", q_style))
            hint = q.get('hint', '')
            if hint:
                elements.append(Paragraph(f"   [{hint}]", opt_style))
            elements.append(Spacer(1, 0.08 * inch))

    # Footer
    elements.append(Spacer(1, 0.25 * inch))
    elements.append(Table([['']], colWidths=[6.4 * inch],
        style=[('LINEABOVE', (0, 0), (-1, 0), 0.8, colors.HexColor('#CCCCCC'))]))
    elements.append(Spacer(1, 0.05 * inch))
    footer_style = ParagraphStyle('QFooter', parent=styles['Normal'],
        fontName=_PDF_FONT, fontSize=9, textColor=colors.HexColor('#666666'))
    elements.append(Paragraph(f"O'qituvchi: {teacher_name}", footer_style))

    doc.build(elements)
    output.seek(0)
    return output.getvalue()
