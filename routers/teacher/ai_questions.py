"""Teacher AI question-set routes."""
import json
import logging
import traceback
from datetime import date
from io import BytesIO
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from config import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from models import get_db, Employee, Subject, AIQuestionSet
from dependencies import require_login, flash, get_template_context, page_info
from services.ai_service import generate_questions
from services.ai_shared import translate, reset_if_new_day, LANGUAGE_DISPLAY, TYPE_DISPLAY

log = logging.getLogger("teacher.ai_questions")
router = APIRouter(prefix="/teacher", dependencies=[Depends(require_login)])
templates = Jinja2Templates(directory="templates")



def reset_if_new_day(teacher: Employee):
    today = date.today()
    if teacher.ai_questions_last_reset != today:
        teacher.ai_questions_used_today = 0
        teacher.ai_questions_last_reset = today


@router.get("/ai-questions", response_class=HTMLResponse)
async def teacher_questions_list(request: Request, page: int = 1, db: AsyncSession = Depends(get_db)):
    per_page = 6
    teacher_id = request.session.get('user_id')
    teacher = (await db.execute(select(Employee).where(Employee.id == teacher_id))).scalar_one()

    if not teacher.ai_enabled:
        flash(request, translate(request, 'ai_disabled_for_you'), 'warning')
        return RedirectResponse(url="/teacher/dashboard", status_code=303)

    reset_if_new_day(teacher)
    await db.commit()

    total = (await db.execute(
        select(func.count(AIQuestionSet.id)).where(AIQuestionSet.teacher_id == teacher_id)
    )).scalar()
    pg = page_info(total, page, per_page, request)
    question_sets = (await db.execute(
        select(AIQuestionSet)
        .options(defer(AIQuestionSet.content))
        .where(AIQuestionSet.teacher_id == teacher_id)
        .order_by(AIQuestionSet.created_at.desc())
        .offset(pg['row_offset']).limit(per_page)
    )).scalars().all()

    context = await get_template_context(request, db)
    context.update({
        'question_sets': question_sets, 'teacher': teacher,
        'remaining': max(0, teacher.ai_questions_daily_limit - teacher.ai_questions_used_today),
        'language_display': LANGUAGE_DISPLAY, 'type_display': TYPE_DISPLAY, **pg,
    })
    return templates.TemplateResponse('teacher/ai_questions_list.html', context)


@router.get("/ai-questions/create", response_class=HTMLResponse)
async def teacher_questions_create_form(request: Request, db: AsyncSession = Depends(get_db)):
    teacher_id = request.session.get('user_id')
    teacher = (await db.execute(select(Employee).where(Employee.id == teacher_id))).scalar_one()

    if not teacher.ai_enabled:
        flash(request, translate(request, 'ai_disabled_short'), 'warning')
        return RedirectResponse(url="/teacher/dashboard", status_code=303)

    reset_if_new_day(teacher)
    await db.commit()

    if teacher.ai_questions_used_today >= teacher.ai_questions_daily_limit:
        flash(request, translate(request, 'ai_limit_reached_msg'), 'warning')
        return RedirectResponse(url="/teacher/ai-questions", status_code=303)

    subjects = (await db.execute(select(Subject).order_by(Subject.name))).scalars().all()
    context = await get_template_context(request, db)
    context.update({
        'subjects': subjects,
        'remaining': teacher.ai_questions_daily_limit - teacher.ai_questions_used_today,
    })
    return templates.TemplateResponse('teacher/ai_questions_create.html', context)


@router.post("/ai-questions/generate")
async def teacher_questions_generate(
    request: Request,
    subject_id: int = Form(...), grade: int = Form(...),
    topic: str = Form(...), language: str = Form('uz'),
    question_type: str = Form('test'), question_count: int = Form(10),
    db: AsyncSession = Depends(get_db),
):
    teacher_id = request.session.get('user_id')
    teacher = (await db.execute(select(Employee).where(Employee.id == teacher_id))).scalar_one()

    if not teacher.ai_enabled:
        return JSONResponse({'ok': False, 'error': translate(request, 'ai_disabled_short')}, status_code=403)

    reset_if_new_day(teacher)
    if teacher.ai_questions_used_today >= teacher.ai_questions_daily_limit:
        return JSONResponse({'ok': False, 'error': translate(request, 'ai_limit_reached_short')}, status_code=429)

    if not (1 <= grade <= 11):
        return JSONResponse({'ok': False, 'error': translate(request, 'ai_invalid_grade')}, status_code=400)
    topic = (topic or '').strip()
    if not topic or len(topic) > 300:
        return JSONResponse({'ok': False, 'error': translate(request, 'ai_invalid_topic')}, status_code=400)
    if language not in ('uz', 'ru', 'en'):
        language = 'uz'
    if question_type == 'test':
        question_count = max(10, min(30, question_count))
    else:
        question_type = 'open'
        question_count = max(10, min(15, question_count))

    subject = (await db.execute(select(Subject).where(Subject.id == subject_id))).scalar_one_or_none()
    if not subject:
        return JSONResponse({'ok': False, 'error': translate(request, 'ai_subject_not_found')}, status_code=400)

    try:
        data = await generate_questions(subject.name, grade, topic, language, question_type, question_count)
    except Exception as e:
        log.error("Question generation failed: %s\n%s", e, traceback.format_exc())
        return JSONResponse({'ok': False, 'error': f"{translate(request, 'ai_error_prefix')}: {str(e)[:200]}"}, status_code=500)

    actual_count = len(data.get('questions', []))
    qs = AIQuestionSet(
        teacher_id=teacher_id, subject_name=subject.name, grade=grade,
        topic=topic, language=language, question_type=question_type,
        question_count=actual_count, content=json.dumps(data, ensure_ascii=False),
    )
    db.add(qs)
    teacher.ai_questions_used_today += 1
    teacher.ai_questions_last_reset = date.today()
    await db.commit()
    await db.refresh(qs)
    return JSONResponse({'ok': True, 'id': qs.id, 'redirect': f"/teacher/ai-questions/{qs.id}"})


@router.get("/ai-questions/{qid}", response_class=HTMLResponse)
async def teacher_questions_view(qid: int, request: Request, db: AsyncSession = Depends(get_db)):
    teacher_id = request.session.get('user_id')
    qs = (await db.execute(select(AIQuestionSet).where(AIQuestionSet.id == qid))).scalar_one_or_none()
    if not qs:
        raise HTTPException(404)
    is_admin = request.session.get('is_admin', False)
    if not is_admin and qs.teacher_id != teacher_id:
        raise HTTPException(403)

    data = json.loads(qs.content)
    context = await get_template_context(request, db)
    context.update({
        'qs': qs, 'data': data,
        'language_display': LANGUAGE_DISPLAY, 'type_display': TYPE_DISPLAY, 'is_admin': is_admin,
    })
    return templates.TemplateResponse('teacher/ai_questions_view.html', context)


@router.get("/ai-questions/{qid}/pdf")
async def teacher_questions_pdf(qid: int, request: Request, db: AsyncSession = Depends(get_db)):
    teacher_id = request.session.get('user_id')
    qs = (await db.execute(select(AIQuestionSet).where(AIQuestionSet.id == qid))).scalar_one_or_none()
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
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{utf8_filename}",
                 "Content-Length": str(len(pdf_bytes))})


@router.post("/ai-questions/{qid}/delete")
async def teacher_questions_delete(qid: int, request: Request, db: AsyncSession = Depends(get_db)):
    teacher_id = request.session.get('user_id')
    qs = (await db.execute(select(AIQuestionSet).where(AIQuestionSet.id == qid))).scalar_one_or_none()
    if not qs:
        raise HTTPException(404)
    is_admin = request.session.get('is_admin', False)
    if not is_admin and qs.teacher_id != teacher_id:
        raise HTTPException(403)
    await db.delete(qs)
    await db.commit()
    flash(request, translate(request, 'ai_presentation_deleted'), 'success')
    return RedirectResponse(url="/teacher/ai-questions", status_code=303)


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
    doc = SimpleDocTemplate(output, pagesize=A4,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        leftMargin=0.8 * inch, rightMargin=0.8 * inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('QTitle', parent=styles['Normal'],
        fontName=_PDF_FONT_BOLD, fontSize=13, alignment=TA_CENTER, spaceAfter=4)
    sub_style = ParagraphStyle('QSub', parent=styles['Normal'],
        fontName=_PDF_FONT, fontSize=10, alignment=TA_CENTER, spaceAfter=2,
        textColor=colors.HexColor('#555555'))
    q_style = ParagraphStyle('QBody', parent=styles['Normal'],
        fontName=_PDF_FONT_BOLD, fontSize=11, spaceAfter=4, spaceBefore=10, leading=15)
    opt_style = ParagraphStyle('QOpt', parent=styles['Normal'],
        fontName=_PDF_FONT, fontSize=10, spaceAfter=3, leftIndent=16, leading=14)
    section_style = ParagraphStyle('QSection', parent=styles['Normal'],
        fontName=_PDF_FONT_BOLD, fontSize=12, spaceBefore=12, spaceAfter=8,
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
    elements.append(Table([['']], colWidths=[6.4 * inch],
        style=[('LINEABOVE', (0, 0), (-1, 0), 1.2, colors.HexColor('#CCCCCC'))]))
    elements.append(Spacer(1, 0.1 * inch))

    questions = data.get('questions', [])
    if qs.question_type == 'test':
        elements.append(Paragraph("Savollar", section_style))
        for q in questions:
            elements.append(Paragraph(f"{q.get('number', '')}. {q.get('question', '')}", q_style))
            for opt in q.get('options', []):
                elements.append(Paragraph(opt, opt_style))
            elements.append(Spacer(1, 0.05 * inch))

        elements.append(PageBreak())
        elements.append(Paragraph(title_text, title_style))
        elements.append(Paragraph(f"{qs.subject_name}  |  {qs.grade}-sinf  —  Javoblar kaliti", sub_style))
        elements.append(Spacer(1, 0.15 * inch))
        elements.append(Table([['']], colWidths=[6.4 * inch],
            style=[('LINEABOVE', (0, 0), (-1, 0), 1.2, colors.HexColor('#CCCCCC'))]))
        elements.append(Spacer(1, 0.1 * inch))
        elements.append(Paragraph("Javoblar kaliti", section_style))

        letters = ['A', 'B', 'C', 'D']
        key_data = [['Savol', 'Javob']]
        for q in questions:
            ci = q.get('correct', 0)
            key_data.append([str(q.get('number', '')), letters[ci] if 0 <= ci < 4 else str(ci)])

        mid = (len(key_data) - 1 + 3) // 4
        cols = [key_data[1:][s:s + mid] for s in range(0, len(key_data) - 1, mid)]
        max_rows = max(len(c) for c in cols)
        table_data_key = [['Savol', 'Javob'] * len(cols)]
        for i in range(max_rows):
            row = []
            for col in cols:
                row.extend(col[i] if i < len(col) else ['', ''])
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
            elements.append(Paragraph(f"{q.get('number', '')}. {q.get('question', '')}", q_style))
            hint = q.get('hint', '')
            if hint:
                elements.append(Paragraph(f"   [{hint}]", opt_style))
            elements.append(Spacer(1, 0.08 * inch))

    elements.append(Spacer(1, 0.25 * inch))
    elements.append(Table([['']], colWidths=[6.4 * inch],
        style=[('LINEABOVE', (0, 0), (-1, 0), 0.8, colors.HexColor('#CCCCCC'))]))
    elements.append(Spacer(1, 0.05 * inch))
    footer_style = ParagraphStyle('QFooter', parent=styles['Normal'],
        fontName=_PDF_FONT, fontSize=9, textColor=colors.HexColor('#666666'))
    elements.append(Paragraph(f"O'qituvchi: {teacher_name}", footer_style))

    doc.build(elements)
    return output.getvalue()
