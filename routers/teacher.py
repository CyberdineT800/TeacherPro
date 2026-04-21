from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, delete, func
from typing import Optional
from io import BytesIO
import json

from models import (
    CHSBQuestionAssignment, get_db, Employee, School, SchoolClass, Student, Subject, Quarter, 
    ExamName, ExamType, QuestionType, Exam, Question, ExamResult
)
from dependencies import require_login, flash, get_template_context, page_info
from utils import generate_excel_report, generate_pdf_report, generate_word_report

router = APIRouter(prefix="/teacher", dependencies=[Depends(require_login)])
templates = Jinja2Templates(directory="templates")

# ============================================================================
# TEACHER DASHBOARD
# ============================================================================

@router.get("/dashboard", response_class=HTMLResponse)
async def teacher_dashboard(
    request: Request,
    page: int = 1,
    db: AsyncSession = Depends(get_db)
):
    """Teacher dashboard"""
    per_page = 10
    teacher_id = request.session.get('user_id')

    teacher_result = await db.execute(select(Employee).where(Employee.id == teacher_id))
    employee = teacher_result.scalar_one_or_none()

    total_exams = (await db.execute(
        select(func.count(Exam.id)).where(Exam.teacher_id == teacher_id)
    )).scalar()
    pg = page_info(total_exams, page, per_page, request)

    exams_result = await db.execute(
        select(Exam)
        .where(Exam.teacher_id == teacher_id)
        .order_by(Exam.created_at.desc())
        .offset(pg['row_offset']).limit(per_page)
    )
    exams = exams_result.scalars().all()
    
    # Prepare exam data with related info
    exams_data = []
    for exam in exams:
        class_result = await db.execute(select(SchoolClass).where(SchoolClass.id == exam.class_id))
        class_obj = class_result.scalar_one_or_none()
        
        subject_result = await db.execute(select(Subject).where(Subject.id == exam.subject_id))
        subject = subject_result.scalar_one_or_none()
        
        quarter_result = await db.execute(select(Quarter).where(Quarter.id == exam.quarter_id))
        quarter = quarter_result.scalar_one_or_none()
        
        exam_name_result = await db.execute(select(ExamName).where(ExamName.id == exam.exam_name_id))
        exam_name = exam_name_result.scalar_one_or_none()
        
        exams_data.append({
            'id': exam.id,
            'class_name': class_obj.name if class_obj else '',
            'subject_name': subject.name if subject else '',
            'quarter_name': quarter.name if quarter else '',
            'exam_name': exam_name.name if exam_name else '',
            'created_at': exam.created_at
        })
    
    # Get school info
    school = None
    if employee and employee.school_id:
        school_result = await db.execute(select(School).where(School.id == employee.school_id))
        school = school_result.scalar_one_or_none()
    
    context = await get_template_context(request, db)
    context.update({
        'employee': employee,
        'school': school,
        'exams': exams_data,
        **pg,
    })
    return templates.TemplateResponse('teacher_dashboard.html', context)

# ============================================================================
# CREATE EXAM
# ============================================================================

@router.get("/create-exam", response_class=HTMLResponse)
async def create_exam_page(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    teacher_id = request.session.get('user_id')

    teacher_result = await db.execute(
        select(Employee)
        .options(selectinload(Employee.assigned_classes), selectinload(Employee.assigned_subjects))
        .where(Employee.id == teacher_id)
    )
    teacher = teacher_result.scalar_one_or_none()

    classes = teacher.assigned_classes if teacher else []
    subjects = teacher.assigned_subjects if teacher else []

    quarters_result = await db.execute(select(Quarter).order_by(Quarter.order_num))
    quarters = quarters_result.scalars().all()

    question_types_result = await db.execute(select(QuestionType))
    question_types = question_types_result.scalars().all()

    exam_types_result = await db.execute(select(ExamType))
    exam_types = exam_types_result.scalars().all()

    # Find default exam names for BSB and CHSB
    bsb_name_result = await db.execute(
        select(ExamName).where(ExamName.name.ilike('bsb%')).limit(1)
    )
    bsb_exam_name = bsb_name_result.scalar_one_or_none()

    chsb_name_result = await db.execute(
        select(ExamName).where(ExamName.name.ilike('chsb%')).limit(1)
    )
    chsb_exam_name = chsb_name_result.scalar_one_or_none()

    default_exam_type_id = exam_types[0].id if exam_types else 1

    context = await get_template_context(request)
    context.update({
        'classes': classes,
        'subjects': subjects,
        'quarters': quarters,
        'question_types': question_types,
        'question_types_json': json.dumps([{'id': qt.id, 'name': qt.name} for qt in question_types]),
        'bsb_exam_name_id': bsb_exam_name.id if bsb_exam_name else None,
        'chsb_exam_name_id': chsb_exam_name.id if chsb_exam_name else None,
        'default_exam_type_id': default_exam_type_id,
    })

    if not classes or not subjects:
        flash(request, "Sizga sinf yoki fan biriktirilmagan. Administrator bilan bog'laning.", 'warning')

    return templates.TemplateResponse('teacher/create_exam.html', context)

@router.post("/create-exam")
async def create_exam(
    request: Request,
    class_id: int = Form(...),
    subject_id: int = Form(...),
    exam_name_id: int = Form(...),
    exam_type_id: int = Form(...),
    quarter_id: Optional[int] = Form(None),
    period: Optional[str] = Form(None),
    difficulty: Optional[str] = Form(None),
    gender_filter: int = Form(0),
    group_filter: int = Form(0),
    variant: int = Form(1),
    num_q_rows: int = Form(0),
    db: AsyncSession = Depends(get_db)
):
    teacher_id = request.session.get('user_id')

    teacher_result = await db.execute(
        select(Employee)
        .options(selectinload(Employee.assigned_classes), selectinload(Employee.assigned_subjects))
        .where(Employee.id == teacher_id)
    )
    teacher = teacher_result.scalar_one_or_none()

    if not teacher:
        flash(request, 'Foydalanuvchi topilmadi', 'danger')
        return RedirectResponse(url="/teacher/dashboard", status_code=303)

    assigned_class_ids = [cls.id for cls in teacher.assigned_classes]
    if class_id not in assigned_class_ids:
        flash(request, 'Siz bu sinf uchun imtihon yarata olmaysiz', 'danger')
        return RedirectResponse(url="/teacher/create-exam", status_code=303)

    assigned_subject_ids = [subj.id for subj in teacher.assigned_subjects]
    if subject_id not in assigned_subject_ids:
        flash(request, 'Siz bu fan uchun imtihon yarata olmaysiz', 'danger')
        return RedirectResponse(url="/teacher/create-exam", status_code=303)

    exam_name_result = await db.execute(select(ExamName).where(ExamName.id == exam_name_id))
    exam_name = exam_name_result.scalar_one_or_none()

    exam_name_lower = exam_name.name.lower() if exam_name else ""
    is_bsb_exam = "bsb" in exam_name_lower
    is_chsb_exam = "chsb" in exam_name_lower
    is_project_exam = "project" in exam_name_lower or "loyiha" in exam_name_lower

    exam = Exam(
        class_id=class_id,
        subject_id=subject_id,
        quarter_id=quarter_id,
        period=period,
        difficulty=difficulty,
        exam_name_id=exam_name_id,
        exam_type_id=exam_type_id,
        teacher_id=teacher_id,
        is_bsb_exam=is_bsb_exam,
        is_chsb_exam=is_chsb_exam,
        is_project_exam=is_project_exam,
        gender_filter=gender_filter,
        group_filter=group_filter,
        variant=variant,
    )
    db.add(exam)
    await db.flush()

    form_data = await request.form()

    # Build questions from distribution rows (works for BSB, CHSB, and custom exams)
    question_number = 1
    for i in range(1, num_q_rows + 1):
        type_id_str = form_data.get(f'q_type_id_{i}')
        count_str = form_data.get(f'q_count_{i}')
        score_str = form_data.get(f'q_score_{i}')
        if not (type_id_str and count_str and score_str):
            continue
        try:
            type_id = int(type_id_str)
            count = int(count_str)
            score = float(score_str)
        except (ValueError, TypeError):
            continue
        for _ in range(count):
            db.add(Question(
                exam_id=exam.id,
                question_number=question_number,
                question_type_id=type_id,
                max_score=score,
            ))
            question_number += 1

    # Fallback: if no distribution rows sent, use legacy defaults
    if question_number == 1:
        default_type_id = 1
        if is_bsb_exam:
            for i in range(1, 6):
                db.add(Question(exam_id=exam.id, question_number=i,
                                question_type_id=default_type_id, max_score=5.0))
        elif is_chsb_exam:
            for i in range(1, 11):
                db.add(Question(exam_id=exam.id, question_number=i,
                                question_type_id=default_type_id, max_score=4.0))

    await db.commit()
    flash(request, 'Imtihon yaratildi', 'success')
    return RedirectResponse(url=f"/teacher/enter-scores/{exam.id}", status_code=303)

# ============================================================================
# ENTER SCORES
# ============================================================================

@router.get("/enter-scores/{exam_id}", response_class=HTMLResponse)
async def enter_scores_page(
    request: Request,
    exam_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Display enter scores form"""
    exam_result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = exam_result.scalar_one_or_none()
    if not exam:
        flash(request, 'Imtihon topilmadi', 'danger')
        return RedirectResponse(url="/teacher/dashboard", status_code=303)
    
    student_query = select(Student).where(Student.class_id == exam.class_id)
    
    if exam.gender_filter != 0:
        student_query = student_query.where(Student.gender == exam.gender_filter)
    if exam.group_filter != 0:
        student_query = student_query.where(Student.group_number == exam.group_filter)
    
    student_query = student_query.order_by(Student.group_number, Student.last_name, Student.first_name)
    students_result = await db.execute(student_query)
    students = students_result.scalars().all()

    questions_result = await db.execute(
        select(Question)
        .where(Question.exam_id == exam_id)
        .order_by(Question.question_number)
    )
    questions = questions_result.scalars().all()

    class_result = await db.execute(select(SchoolClass).where(SchoolClass.id == exam.class_id))
    class_obj = class_result.scalar_one_or_none()

    subject_result = await db.execute(select(Subject).where(Subject.id == exam.subject_id))
    subject = subject_result.scalar_one_or_none()

    quarter_result = await db.execute(select(Quarter).where(Quarter.id == exam.quarter_id)) if exam.quarter_id else (None, None)
    if exam.quarter_id:
        quarter_result = await db.execute(select(Quarter).where(Quarter.id == exam.quarter_id))
        quarter = quarter_result.scalar_one_or_none()
    else:
        quarter = None

    exam_name_result = await db.execute(select(ExamName).where(ExamName.id == exam.exam_name_id))
    exam_name = exam_name_result.scalar_one_or_none()

    exam_type_result = await db.execute(select(ExamType).where(ExamType.id == exam.exam_type_id))
    exam_type = exam_type_result.scalar_one_or_none()

    period_label = exam.period or (quarter.name if quarter else '')
    total_max_score = sum(q.max_score for q in questions)

    exam_info = {
        'class_name': class_obj.name if class_obj else '',
        'leader_fullname': f"{class_obj.leader_first_name} {class_obj.leader_last_name}" if class_obj else '',
        'leader_phone': class_obj.leader_phone if class_obj else '',
        'group_filter': exam.group_filter,
        'gender_filter': exam.gender_filter,
        'subject_name': subject.name if subject else '',
        'quarter_name': period_label,
        'exam_name': exam_name.name if exam_name else '',
        'exam_type_name': exam_type.name if exam_type else '',
        'difficulty': exam.difficulty or '',
    }

    question_types_summary = []
    if exam.is_chsb_exam:
        type_groups: dict = {}
        for q in questions:
            tid = q.question_type_id
            if tid not in type_groups:
                qt_result = await db.execute(select(QuestionType).where(QuestionType.id == tid))
                qt = qt_result.scalar_one_or_none()
                type_groups[tid] = {'name': qt.name if qt else '', 'questions': [], 'total_max_score': 0.0}
            type_groups[tid]['questions'].append(q.question_number)
            type_groups[tid]['total_max_score'] += q.max_score
        for tid, group in type_groups.items():
            count = len(group['questions'])
            tms = round(group['total_max_score'], 4)
            question_types_summary.append({
                'id': tid,
                'name': group['name'],
                'count': count,
                'question_numbers': sorted(group['questions']),
                'total_max_score': tms,
                'score_per_question': round(tms / count, 4) if count else 0,
            })

    existing_rows = (await db.execute(
        select(ExamResult).where(ExamResult.exam_id == exam_id)
    )).scalars().all()

    existing_scores: dict = {}
    chsb_existing: dict = {}
    if existing_rows:
        q_to_type = {q.id: q.question_type_id for q in questions}
        for er in existing_rows:
            existing_scores[(er.student_id, er.question_id)] = er.score
            tid = q_to_type.get(er.question_id)
            if tid is not None:
                key = (er.student_id, tid)
                chsb_existing[key] = chsb_existing.get(key, 0.0) + er.score

    context = await get_template_context(request)
    context.update({
        'exam': exam,
        'exam_info': exam_info,
        'students': students,
        'questions': questions,
        'question_types_summary': question_types_summary,
        'total_max_score': total_max_score,
        'group_filter': exam.group_filter,
        'existing_scores': existing_scores,
        'chsb_existing': chsb_existing,
        'is_edit': bool(existing_rows),
    })

    return templates.TemplateResponse('teacher/enter_scores.html', context)

@router.post("/enter-scores/{exam_id}")
async def enter_scores(
    request: Request,
    exam_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Save exam scores"""
    exam_result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = exam_result.scalar_one_or_none()
    if not exam:
        flash(request, 'Imtihon topilmadi', 'danger')
        return RedirectResponse(url="/teacher/dashboard", status_code=303)
    
    student_query = select(Student).where(Student.class_id == exam.class_id)
    if exam.gender_filter != 0:
        student_query = student_query.where(Student.gender == exam.gender_filter)
    if exam.group_filter != 0:
        student_query = student_query.where(Student.group_number == exam.group_filter)
    
    students_result = await db.execute(student_query)
    students = students_result.scalars().all()
    
    questions_result = await db.execute(select(Question).where(Question.exam_id == exam_id))
    questions = questions_result.scalars().all()
    
    await db.execute(delete(ExamResult).where(ExamResult.exam_id == exam_id))

    form_data = await request.form()

    # Save the selected date onto the exam record
    exam_date_val = form_data.get('exam_date', '').strip()
    if exam_date_val:
        # Convert from HTML date format YYYY-MM-DD to DD.MM.YYYY
        try:
            from datetime import datetime as _dt
            exam.exam_date = _dt.strptime(exam_date_val, '%Y-%m-%d').strftime('%d.%m.%Y')
        except ValueError:
            exam.exam_date = exam_date_val
    
    # CHSB: grouped by question type; BSB + others: per-question
    questions_by_type: dict = {}
    if exam.is_chsb_exam:
        for q in questions:
            tid = q.question_type_id
            if tid not in questions_by_type:
                questions_by_type[tid] = []
            questions_by_type[tid].append(q)

    for student in students:
        if exam.is_chsb_exam:
            for question_type_id, qs in questions_by_type.items():
                score_key = f'chsb_score_{student.id}_{question_type_id}'
                score_value = form_data.get(score_key)
                if score_value:
                    total = float(score_value)
                    per_q = total / len(qs) if qs else 0
                    for q in qs:
                        db.add(ExamResult(
                            exam_id=exam_id,
                            student_id=student.id,
                            question_id=q.id,
                            score=per_q,
                        ))
        else:
            for question in questions:
                score_key = f'score_{student.id}_{question.id}'
                score_value = form_data.get(score_key)
                if score_value:
                    db.add(ExamResult(
                        exam_id=exam_id,
                        student_id=student.id,
                        question_id=question.id,
                        score=float(score_value),
                    ))
    
    await db.commit()
    flash(request, 'Natijalar saqlandi', 'success')
    return RedirectResponse(url=f"/teacher/results/{exam_id}", status_code=303)

# ============================================================================
# VIEW RESULTS
# ============================================================================

@router.get("/results/{exam_id}", response_class=HTMLResponse)
async def view_results(
    request: Request,
    exam_id: int,
    db: AsyncSession = Depends(get_db)
):
    """View exam results"""
    exam_result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = exam_result.scalar_one_or_none()
    if not exam:
        flash(request, 'Imtihon topilmadi', 'danger')
        return RedirectResponse(url="/teacher/dashboard", status_code=303)
    
    student_query = select(Student).where(Student.class_id == exam.class_id)
    if exam.gender_filter != 0:
        student_query = student_query.where(Student.gender == exam.gender_filter)
    if exam.group_filter != 0:
        student_query = student_query.where(Student.group_number == exam.group_filter)
    
    student_query = student_query.order_by(Student.group_number, Student.last_name, Student.first_name)
    students_result = await db.execute(student_query)
    students = students_result.scalars().all()

    questions_result = await db.execute(
        select(Question).where(Question.exam_id == exam_id).order_by(Question.question_number)
    )
    questions = questions_result.scalars().all()

    class_result = await db.execute(select(SchoolClass).where(SchoolClass.id == exam.class_id))
    class_obj = class_result.scalar_one_or_none()

    subject_result = await db.execute(select(Subject).where(Subject.id == exam.subject_id))
    subject = subject_result.scalar_one_or_none()

    if exam.quarter_id:
        quarter_result = await db.execute(select(Quarter).where(Quarter.id == exam.quarter_id))
        quarter = quarter_result.scalar_one_or_none()
    else:
        quarter = None

    exam_type_result = await db.execute(select(ExamType).where(ExamType.id == exam.exam_type_id))
    exam_type = exam_type_result.scalar_one_or_none()

    exam_name_result = await db.execute(select(ExamName).where(ExamName.id == exam.exam_name_id))
    exam_name = exam_name_result.scalar_one_or_none()

    teacher_result = await db.execute(select(Employee).where(Employee.id == exam.teacher_id))
    teacher = teacher_result.scalar_one_or_none()

    period_label = exam.period or (quarter.name if quarter else '')
    exam_info = {
        'class_name': class_obj.name if class_obj else '',
        'leader_fullname': f"{class_obj.leader_first_name} {class_obj.leader_last_name}" if class_obj else '',
        'leader_phone': class_obj.leader_phone if class_obj else '',
        'group_filter': exam.group_filter,
        'gender_filter': exam.gender_filter,
        'subject_name': subject.name if subject else '',
        'quarter_name': period_label,
        'exam_type_name': exam_type.name if exam_type else '',
        'exam_name': exam_name.name if exam_name else '',
        'teacher_name': f"{teacher.last_name} {teacher.first_name}" if teacher else '',
        'difficulty': exam.difficulty or '',
    }

    total_max_score = sum(q.max_score for q in questions)

    # CHSB only: group by question type with score_per_question
    question_types_summary = []
    if exam.is_chsb_exam:
        type_groups: dict = {}
        for q in questions:
            tid = q.question_type_id
            if tid not in type_groups:
                qt_res = await db.execute(select(QuestionType).where(QuestionType.id == tid))
                qt = qt_res.scalar_one_or_none()
                type_groups[tid] = {'name': qt.name if qt else '', 'questions': [], 'total_max_score': 0.0}
            type_groups[tid]['questions'].append(q.question_number)
            type_groups[tid]['total_max_score'] += q.max_score
        for tid, group in type_groups.items():
            count = len(group['questions'])
            question_types_summary.append({
                'id': tid,
                'name': group['name'],
                'count': count,
                'question_numbers': sorted(group['questions']),
                'total_max_score': group['total_max_score'],
                'score_per_question': group['total_max_score'] / count if count else 0,
            })

    results = []
    for student in students:
        student_results_query = await db.execute(
            select(ExamResult).where(ExamResult.exam_id == exam_id, ExamResult.student_id == student.id)
        )
        student_results = student_results_query.scalars().all()

        if exam.is_chsb_exam:
            question_scores = []
            total_score = 0.0
            for qtype_summary in question_types_summary:
                type_score = 0.0
                for q_num in qtype_summary['question_numbers']:
                    question = next((q for q in questions if q.question_number == q_num), None)
                    if question:
                        result = next((r for r in student_results if r.question_id == question.id), None)
                        type_score += result.score if result else 0
                question_scores.append(type_score)
                total_score += type_score
        else:
            question_scores = []
            total_score = 0.0
            for question in questions:
                result = next((r for r in student_results if r.question_id == question.id), None)
                question_scores.append(result.score if result else 0)
                total_score += result.score if result else 0

        percentage = (total_score / total_max_score * 100) if total_max_score > 0 else 0
        results.append({
            'student_name': f"{student.last_name} {student.first_name}",
            'group_number': student.group_number,
            'question_scores': question_scores,
            'total_score': total_score,
            'percentage': round(percentage, 1),
        })

    context = await get_template_context(request)
    context.update({
        'exam': exam,
        'exam_info': exam_info,
        'questions': questions,
        'results': results,
        'total_max_score': total_max_score,
        'question_types_summary': question_types_summary,
    })
    return templates.TemplateResponse('teacher/view_results.html', context)

# ============================================================================
# DOWNLOAD RESULTS
# ============================================================================

@router.get("/download/{exam_id}/{format}")
async def download_results(
    request: Request,
    exam_id: int,
    format: str,
    db: AsyncSession = Depends(get_db)
):
    """Download exam results in specified format"""
    exam_result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = exam_result.scalar_one_or_none()
    if not exam:
        flash(request, 'Imtihon topilmadi', 'danger')
        return RedirectResponse(url="/teacher/dashboard", status_code=303)
    
    student_query = select(Student).where(Student.class_id == exam.class_id)
    if exam.gender_filter != 0:
        student_query = student_query.where(Student.gender == exam.gender_filter)
    if exam.group_filter != 0:
        student_query = student_query.where(Student.group_number == exam.group_filter)
    
    student_query = student_query.order_by(Student.group_number, Student.last_name, Student.first_name)
    students_result = await db.execute(student_query)
    students = students_result.scalars().all()

    questions_result = await db.execute(
        select(Question)
        .where(Question.exam_id == exam_id)
        .order_by(Question.question_number)
    )
    questions = questions_result.scalars().all()

    class_result = await db.execute(select(SchoolClass).where(SchoolClass.id == exam.class_id))
    class_obj = class_result.scalar_one_or_none()

    subject_result = await db.execute(select(Subject).where(Subject.id == exam.subject_id))
    subject = subject_result.scalar_one_or_none()

    if exam.quarter_id:
        quarter_result = await db.execute(select(Quarter).where(Quarter.id == exam.quarter_id))
        quarter = quarter_result.scalar_one_or_none()
    else:
        quarter = None

    exam_type_result = await db.execute(select(ExamType).where(ExamType.id == exam.exam_type_id))
    exam_type = exam_type_result.scalar_one_or_none()

    exam_name_result = await db.execute(select(ExamName).where(ExamName.id == exam.exam_name_id))
    exam_name = exam_name_result.scalar_one_or_none()
    
    teacher_result = await db.execute(select(Employee).where(Employee.id == exam.teacher_id))
    teacher = teacher_result.scalar_one_or_none()
    
    school = None
    if class_obj and class_obj.school_id:
        school_result = await db.execute(select(School).where(School.id == class_obj.school_id))
        school = school_result.scalar_one_or_none()
    
    period_label = exam.period or (quarter.name if quarter else '')
    group_label = f" ({exam.group_filter}-guruh)" if exam.group_filter else ""
    header = f"{class_obj.name if class_obj else ''}-sinfida {subject.name if subject else ''} fanidan o'tkazilgan {period_label}\n"
    header += f"N{exam.variant} {exam_name.name if exam_name else ''} tahlili{group_label}"
    
    teacher_name = f"{teacher.first_name} {teacher.last_name}" if teacher else ''
    exam_date = exam.exam_date or (exam.created_at.strftime('%d.%m.%Y') if exam.created_at else '')
    
    total_max_score = sum(q.max_score for q in questions)
    
    students_by_group = {}
    show_groups = exam.group_filter != 0  
    
    for student in students:
        group = student.group_number if show_groups else 0
        if group not in students_by_group:
            students_by_group[group] = []
        students_by_group[group].append(student)
    
    question_types_summary = []
    if exam.is_chsb_exam:
        type_groups: dict = {}
        for q in questions:
            tid = q.question_type_id
            if tid not in type_groups:
                qt_res = await db.execute(select(QuestionType).where(QuestionType.id == tid))
                qt = qt_res.scalar_one_or_none()
                type_groups[tid] = {'name': qt.name if qt else '', 'questions': [], 'total_max_score': 0.0}
            type_groups[tid]['questions'].append(q.question_number)
            type_groups[tid]['total_max_score'] += q.max_score
        for tid, group in type_groups.items():
            count = len(group['questions'])
            tms = round(group['total_max_score'], 4)
            question_types_summary.append({
                'id': tid,
                'name': group['name'],
                'count': count,
                'question_numbers': sorted(group['questions']),
                'total_max_score': tms,
                'score_per_question': round(tms / count, 4) if count else 0,
            })

    students_data = []
    for group_num in sorted(students_by_group.keys()):
        for student in students_by_group[group_num]:
            student_results_query = await db.execute(
                select(ExamResult)
                .where(ExamResult.exam_id == exam_id, ExamResult.student_id == student.id)
            )
            student_results = student_results_query.scalars().all()

            scores = []
            total_score = 0.0

            if exam.is_chsb_exam:
                for qtype_summary in question_types_summary:
                    type_score = 0.0
                    for q_num in qtype_summary['question_numbers']:
                        question = next((q for q in questions if q.question_number == q_num), None)
                        if question:
                            result = next((r for r in student_results if r.question_id == question.id), None)
                            type_score += result.score if result else 0
                    scores.append(type_score)
                    total_score += type_score
            else:
                for question in questions:
                    result = next((r for r in student_results if r.question_id == question.id), None)
                    score = result.score if result else 0
                    scores.append(score)
                    total_score += score
            
            percentage = (total_score / total_max_score * 100) if total_max_score > 0 else 0
            
            student_row = {
                'Ism': student.first_name,
                'Familiya': student.last_name,
                'Guruh': student.group_number if show_groups else None,
                'Jami ball': total_score,
                'Foiz': f"{round(percentage, 1)}%",
                'scores': scores
            }
            
            students_data.append(student_row)
    
    exam_data = {
        'header': header,
        'teacher': teacher_name,
        'date': exam_date,
        'students': students_data,
        'questions': questions,
        'question_types_summary': question_types_summary,
        'is_bsb_exam': exam.is_bsb_exam,
        'is_chsb_exam': exam.is_chsb_exam,
        'is_project_exam': exam.is_project_exam,
        'show_groups': show_groups,
        'variant': exam.variant,
        'total_max_score': total_max_score
    }
    
    try:
        quarter_name = (exam.period or quarter.name if quarter else 'chorak').replace(' ', '_')
        class_name = class_obj.name.replace(' ', '_').replace('-', '') if class_obj else 'sinf'
        exam_name_str = exam_name.name.replace(' ', '_') if exam_name else 'imtihon'
        
        safe_quarter = ''.join(c for c in quarter_name if c.isalnum() or c == '_')
        safe_class = ''.join(c for c in class_name if c.isalnum() or c == '_')
        safe_exam = ''.join(c for c in exam_name_str if c.isalnum() or c == '_')
        
        base_filename = f"{safe_quarter}_{safe_class}_{safe_exam}"
        
        if format == 'excel':
            output = await generate_excel_report(exam_data)
            return StreamingResponse(
                BytesIO(output.getvalue()),
                media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                headers={'Content-Disposition': f'attachment; filename={base_filename}.xlsx'}
            )
        elif format == 'pdf':
            output = await generate_pdf_report(exam_data)
            return StreamingResponse(
                BytesIO(output.getvalue()),
                media_type='application/pdf',
                headers={'Content-Disposition': f'attachment; filename={base_filename}.pdf'}
            )
        elif format == 'word':
            output = await generate_word_report(exam_data)
            return StreamingResponse(
                BytesIO(output.getvalue()),
                media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                headers={'Content-Disposition': f'attachment; filename={base_filename}.docx'}
            )
        else:
            flash(request, "Noto'g'ri format", 'danger')
            return RedirectResponse(url=f"/teacher/results/{exam_id}", status_code=303)
    except Exception as e:
        flash(request, f'Xatolik yuz berdi: {str(e)}', 'danger')
        return RedirectResponse(url=f"/teacher/results/{exam_id}", status_code=303)
