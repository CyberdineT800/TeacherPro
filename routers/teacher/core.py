"""Teacher dashboard, exam creation, score entry, results, and downloads."""
from datetime import datetime as _dt
from io import BytesIO
from typing import Optional
import json

from fastapi import APIRouter, Request, Depends, Form
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, StreamingResponse
from config import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, delete, func

from models import (
    CHSBQuestionAssignment, get_db, Employee, School, SchoolClass, Student, Subject, Quarter,
    ExamName, ExamType, QuestionType, Exam, Question, ExamResult,
)
from dependencies import require_login, flash, get_template_context, page_info
from utils import generate_excel_report, generate_pdf_report, generate_word_report

router = APIRouter(prefix="/teacher", dependencies=[Depends(require_login)])
templates = Jinja2Templates(directory="templates")


# ============================================================================
# TEACHER DASHBOARD
# ============================================================================

@router.get("/dashboard", response_class=HTMLResponse)
async def teacher_dashboard(request: Request, page: int = 1, db: AsyncSession = Depends(get_db)):
    per_page = 10
    teacher_id = request.session.get('user_id')

    employee = (await db.execute(select(Employee).where(Employee.id == teacher_id))).scalar_one_or_none()

    total_exams = (await db.execute(
        select(func.count(Exam.id)).where(Exam.teacher_id == teacher_id)
    )).scalar()
    pg = page_info(total_exams, page, per_page, request)

    exams = (await db.execute(
        select(Exam)
        .options(
            selectinload(Exam.school_class),
            selectinload(Exam.subject),
            selectinload(Exam.quarter),
            selectinload(Exam.exam_name),
        )
        .where(Exam.teacher_id == teacher_id)
        .order_by(Exam.created_at.desc())
        .offset(pg['row_offset']).limit(per_page)
    )).scalars().all()

    exams_data = [
        {
            'id': exam.id,
            'class_name': exam.school_class.name if exam.school_class else '',
            'subject_name': exam.subject.name if exam.subject else '',
            'quarter_name': exam.quarter.name if exam.quarter else '',
            'exam_name': exam.exam_name.name if exam.exam_name else '',
            'created_at': exam.created_at,
        }
        for exam in exams
    ]

    school = None
    if employee and employee.school_id:
        school = (await db.execute(select(School).where(School.id == employee.school_id))).scalar_one_or_none()

    context = await get_template_context(request, db)
    context.update({'employee': employee, 'school': school, 'exams': exams_data, **pg})
    return templates.TemplateResponse('teacher_dashboard.html', context)


# ============================================================================
# CREATE EXAM
# ============================================================================

@router.get("/create-exam", response_class=HTMLResponse)
async def create_exam_page(request: Request, db: AsyncSession = Depends(get_db)):
    teacher_id = request.session.get('user_id')
    teacher = (await db.execute(
        select(Employee)
        .options(selectinload(Employee.assigned_classes), selectinload(Employee.assigned_subjects))
        .where(Employee.id == teacher_id)
    )).scalar_one_or_none()

    classes = teacher.assigned_classes if teacher else []
    subjects = teacher.assigned_subjects if teacher else []
    quarters = (await db.execute(select(Quarter).order_by(Quarter.order_num))).scalars().all()
    question_types = (await db.execute(select(QuestionType))).scalars().all()
    exam_types = (await db.execute(select(ExamType))).scalars().all()

    bsb_exam_name = (await db.execute(
        select(ExamName).where(ExamName.name.ilike('bsb%')).limit(1)
    )).scalar_one_or_none()
    chsb_exam_name = (await db.execute(
        select(ExamName).where(ExamName.name.ilike('chsb%')).limit(1)
    )).scalar_one_or_none()

    context = await get_template_context(request)
    context.update({
        'classes': classes, 'subjects': subjects, 'quarters': quarters,
        'question_types': question_types,
        'question_types_json': json.dumps([{'id': qt.id, 'name': qt.name} for qt in question_types]),
        'bsb_exam_name_id': bsb_exam_name.id if bsb_exam_name else None,
        'chsb_exam_name_id': chsb_exam_name.id if chsb_exam_name else None,
        'default_exam_type_id': exam_types[0].id if exam_types else 1,
    })

    if not classes or not subjects:
        flash(request, "Sizga sinf yoki fan biriktirilmagan. Administrator bilan bog'laning.", 'warning')

    return templates.TemplateResponse('teacher/create_exam.html', context)


@router.post("/create-exam")
async def create_exam(
    request: Request,
    class_id: int = Form(...), subject_id: int = Form(...),
    exam_name_id: int = Form(...), exam_type_id: int = Form(...),
    quarter_id: Optional[int] = Form(None), period: Optional[str] = Form(None),
    difficulty: Optional[str] = Form(None),
    gender_filter: int = Form(0), group_filter: int = Form(0),
    variant: int = Form(1), num_q_rows: int = Form(0),
    db: AsyncSession = Depends(get_db),
):
    teacher_id = request.session.get('user_id')
    teacher = (await db.execute(
        select(Employee)
        .options(selectinload(Employee.assigned_classes), selectinload(Employee.assigned_subjects))
        .where(Employee.id == teacher_id)
    )).scalar_one_or_none()

    if not teacher:
        flash(request, 'Foydalanuvchi topilmadi', 'danger')
        return RedirectResponse(url="/teacher/dashboard", status_code=303)

    if class_id not in [c.id for c in teacher.assigned_classes]:
        flash(request, 'Siz bu sinf uchun imtihon yarata olmaysiz', 'danger')
        return RedirectResponse(url="/teacher/create-exam", status_code=303)

    if subject_id not in [s.id for s in teacher.assigned_subjects]:
        flash(request, 'Siz bu fan uchun imtihon yarata olmaysiz', 'danger')
        return RedirectResponse(url="/teacher/create-exam", status_code=303)

    exam_name = (await db.execute(select(ExamName).where(ExamName.id == exam_name_id))).scalar_one_or_none()
    name_lower = exam_name.name.lower() if exam_name else ""

    exam = Exam(
        class_id=class_id, subject_id=subject_id,
        quarter_id=quarter_id, period=period, difficulty=difficulty,
        exam_name_id=exam_name_id, exam_type_id=exam_type_id,
        teacher_id=teacher_id,
        is_bsb_exam="bsb" in name_lower,
        is_chsb_exam="chsb" in name_lower,
        is_project_exam="project" in name_lower or "loyiha" in name_lower,
        gender_filter=gender_filter, group_filter=group_filter, variant=variant,
    )
    db.add(exam)
    await db.flush()

    form_data = await request.form()
    question_number = 1
    for i in range(1, num_q_rows + 1):
        tid_s = form_data.get(f'q_type_id_{i}')
        cnt_s = form_data.get(f'q_count_{i}')
        scr_s = form_data.get(f'q_score_{i}')
        if not (tid_s and cnt_s and scr_s):
            continue
        try:
            tid, cnt, scr = int(tid_s), int(cnt_s), float(scr_s)
        except (ValueError, TypeError):
            continue
        for _ in range(cnt):
            db.add(Question(exam_id=exam.id, question_number=question_number,
                            question_type_id=tid, max_score=scr))
            question_number += 1

    if question_number == 1:
        if exam.is_bsb_exam:
            for i in range(1, 6):
                db.add(Question(exam_id=exam.id, question_number=i, question_type_id=1, max_score=5.0))
        elif exam.is_chsb_exam:
            for i in range(1, 11):
                db.add(Question(exam_id=exam.id, question_number=i, question_type_id=1, max_score=4.0))

    await db.commit()
    flash(request, 'Imtihon yaratildi', 'success')
    return RedirectResponse(url=f"/teacher/enter-scores/{exam.id}", status_code=303)


# ============================================================================
# ENTER SCORES
# ============================================================================

@router.get("/enter-scores/{exam_id}", response_class=HTMLResponse)
async def enter_scores_page(request: Request, exam_id: int, db: AsyncSession = Depends(get_db)):
    exam = (await db.execute(select(Exam).where(Exam.id == exam_id))).scalar_one_or_none()
    if not exam:
        flash(request, 'Imtihon topilmadi', 'danger')
        return RedirectResponse(url="/teacher/dashboard", status_code=303)

    sq = select(Student).where(Student.class_id == exam.class_id)
    if exam.gender_filter != 0:
        sq = sq.where(Student.gender == exam.gender_filter)
    if exam.group_filter != 0:
        sq = sq.where(Student.group_number == exam.group_filter)
    students = (await db.execute(sq.order_by(Student.group_number, Student.last_name, Student.first_name))).scalars().all()
    questions = (await db.execute(
        select(Question).where(Question.exam_id == exam_id).order_by(Question.question_number)
    )).scalars().all()

    class_obj = (await db.execute(select(SchoolClass).where(SchoolClass.id == exam.class_id))).scalar_one_or_none()
    subject = (await db.execute(select(Subject).where(Subject.id == exam.subject_id))).scalar_one_or_none()
    quarter = (await db.execute(select(Quarter).where(Quarter.id == exam.quarter_id))).scalar_one_or_none() if exam.quarter_id else None
    exam_name = (await db.execute(select(ExamName).where(ExamName.id == exam.exam_name_id))).scalar_one_or_none()
    exam_type = (await db.execute(select(ExamType).where(ExamType.id == exam.exam_type_id))).scalar_one_or_none()

    period_label = exam.period or (quarter.name if quarter else '')
    total_max_score = sum(q.max_score for q in questions)
    exam_info = {
        'class_name': class_obj.name if class_obj else '',
        'leader_fullname': f"{class_obj.leader_first_name} {class_obj.leader_last_name}" if class_obj else '',
        'leader_phone': class_obj.leader_phone if class_obj else '',
        'group_filter': exam.group_filter, 'gender_filter': exam.gender_filter,
        'subject_name': subject.name if subject else '',
        'quarter_name': period_label,
        'exam_name': exam_name.name if exam_name else '',
        'exam_type_name': exam_type.name if exam_type else '',
        'difficulty': exam.difficulty or '',
    }

    question_types_summary = []
    if exam.is_chsb_exam:
        # Load all QuestionTypes in one query instead of per-question queries
        all_qt_ids = list({q.question_type_id for q in questions})
        qt_map = {
            qt.id: qt for qt in (await db.execute(
                select(QuestionType).where(QuestionType.id.in_(all_qt_ids))
            )).scalars().all()
        }
        type_groups: dict = {}
        for q in questions:
            tid = q.question_type_id
            if tid not in type_groups:
                qt = qt_map.get(tid)
                type_groups[tid] = {'name': qt.name if qt else '', 'questions': [], 'total_max_score': 0.0}
            type_groups[tid]['questions'].append(q.question_number)
            type_groups[tid]['total_max_score'] += q.max_score
        for tid, grp in type_groups.items():
            cnt = len(grp['questions'])
            tms = round(grp['total_max_score'], 4)
            question_types_summary.append({
                'id': tid, 'name': grp['name'], 'count': cnt,
                'question_numbers': sorted(grp['questions']), 'total_max_score': tms,
                'score_per_question': round(tms / cnt, 4) if cnt else 0,
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
        'exam': exam, 'exam_info': exam_info, 'students': students,
        'questions': questions, 'question_types_summary': question_types_summary,
        'total_max_score': total_max_score, 'group_filter': exam.group_filter,
        'existing_scores': existing_scores, 'chsb_existing': chsb_existing,
        'is_edit': bool(existing_rows),
    })
    return templates.TemplateResponse('teacher/enter_scores.html', context)


@router.post("/enter-scores/{exam_id}")
async def enter_scores(request: Request, exam_id: int, db: AsyncSession = Depends(get_db)):
    exam = (await db.execute(select(Exam).where(Exam.id == exam_id))).scalar_one_or_none()
    if not exam:
        flash(request, 'Imtihon topilmadi', 'danger')
        return RedirectResponse(url="/teacher/dashboard", status_code=303)

    sq = select(Student).where(Student.class_id == exam.class_id)
    if exam.gender_filter != 0:
        sq = sq.where(Student.gender == exam.gender_filter)
    if exam.group_filter != 0:
        sq = sq.where(Student.group_number == exam.group_filter)
    students = (await db.execute(sq)).scalars().all()
    questions = (await db.execute(select(Question).where(Question.exam_id == exam_id))).scalars().all()

    await db.execute(delete(ExamResult).where(ExamResult.exam_id == exam_id))
    form_data = await request.form()

    exam_date_val = form_data.get('exam_date', '').strip()
    if exam_date_val:
        try:
            exam.exam_date = _dt.strptime(exam_date_val, '%Y-%m-%d').strftime('%d.%m.%Y')
        except ValueError:
            exam.exam_date = exam_date_val

    questions_by_type: dict = {}
    if exam.is_chsb_exam:
        for q in questions:
            questions_by_type.setdefault(q.question_type_id, []).append(q)

    for student in students:
        if exam.is_chsb_exam:
            for qt_id, qs in questions_by_type.items():
                val = form_data.get(f'chsb_score_{student.id}_{qt_id}')
                if val:
                    per_q = float(val) / len(qs) if qs else 0
                    for q in qs:
                        db.add(ExamResult(exam_id=exam_id, student_id=student.id,
                                          question_id=q.id, score=per_q))
        else:
            for question in questions:
                val = form_data.get(f'score_{student.id}_{question.id}')
                if val:
                    db.add(ExamResult(exam_id=exam_id, student_id=student.id,
                                      question_id=question.id, score=float(val)))

    await db.commit()
    flash(request, 'Natijalar saqlandi', 'success')
    return RedirectResponse(url=f"/teacher/results/{exam_id}", status_code=303)


# ============================================================================
# VIEW RESULTS
# ============================================================================

@router.get("/results/{exam_id}", response_class=HTMLResponse)
async def view_results(request: Request, exam_id: int, db: AsyncSession = Depends(get_db)):
    exam = (await db.execute(select(Exam).where(Exam.id == exam_id))).scalar_one_or_none()
    if not exam:
        flash(request, 'Imtihon topilmadi', 'danger')
        return RedirectResponse(url="/teacher/dashboard", status_code=303)

    sq = select(Student).where(Student.class_id == exam.class_id)
    if exam.gender_filter != 0:
        sq = sq.where(Student.gender == exam.gender_filter)
    if exam.group_filter != 0:
        sq = sq.where(Student.group_number == exam.group_filter)
    students = (await db.execute(
        sq.order_by(Student.group_number, Student.last_name, Student.first_name)
    )).scalars().all()

    questions = (await db.execute(
        select(Question).where(Question.exam_id == exam_id).order_by(Question.question_number)
    )).scalars().all()
    class_obj = (await db.execute(select(SchoolClass).where(SchoolClass.id == exam.class_id))).scalar_one_or_none()
    subject = (await db.execute(select(Subject).where(Subject.id == exam.subject_id))).scalar_one_or_none()
    quarter = (await db.execute(select(Quarter).where(Quarter.id == exam.quarter_id))).scalar_one_or_none() if exam.quarter_id else None
    exam_type = (await db.execute(select(ExamType).where(ExamType.id == exam.exam_type_id))).scalar_one_or_none()
    exam_name = (await db.execute(select(ExamName).where(ExamName.id == exam.exam_name_id))).scalar_one_or_none()
    teacher = (await db.execute(select(Employee).where(Employee.id == exam.teacher_id))).scalar_one_or_none()

    period_label = exam.period or (quarter.name if quarter else '')
    total_max_score = sum(q.max_score for q in questions)
    exam_info = {
        'class_name': class_obj.name if class_obj else '',
        'leader_fullname': f"{class_obj.leader_first_name} {class_obj.leader_last_name}" if class_obj else '',
        'leader_phone': class_obj.leader_phone if class_obj else '',
        'group_filter': exam.group_filter, 'gender_filter': exam.gender_filter,
        'subject_name': subject.name if subject else '',
        'quarter_name': period_label,
        'exam_type_name': exam_type.name if exam_type else '',
        'exam_name': exam_name.name if exam_name else '',
        'teacher_name': f"{teacher.last_name} {teacher.first_name}" if teacher else '',
        'difficulty': exam.difficulty or '',
    }

    question_types_summary = []
    if exam.is_chsb_exam:
        all_qt_ids = list({q.question_type_id for q in questions})
        qt_map = {
            qt.id: qt for qt in (await db.execute(
                select(QuestionType).where(QuestionType.id.in_(all_qt_ids))
            )).scalars().all()
        }
        type_groups: dict = {}
        for q in questions:
            tid = q.question_type_id
            if tid not in type_groups:
                qt = qt_map.get(tid)
                type_groups[tid] = {'name': qt.name if qt else '', 'questions': [], 'total_max_score': 0.0}
            type_groups[tid]['questions'].append(q.question_number)
            type_groups[tid]['total_max_score'] += q.max_score
        for tid, grp in type_groups.items():
            cnt = len(grp['questions'])
            question_types_summary.append({
                'id': tid, 'name': grp['name'], 'count': cnt,
                'question_numbers': sorted(grp['questions']),
                'total_max_score': grp['total_max_score'],
                'score_per_question': grp['total_max_score'] / cnt if cnt else 0,
            })

    # Load all results for this exam at once — eliminates N+1 per student
    all_exam_results = (await db.execute(
        select(ExamResult).where(ExamResult.exam_id == exam_id)
    )).scalars().all()
    results_by_student: dict = {}
    for er in all_exam_results:
        results_by_student.setdefault(er.student_id, []).append(er)

    results = []
    for student in students:
        student_results = results_by_student.get(student.id, [])

        if exam.is_chsb_exam:
            question_scores, total_score = [], 0.0
            for qts in question_types_summary:
                ts = sum(
                    next((r.score for r in student_results
                          if r.question_id == next((q.id for q in questions if q.question_number == qn), None)), 0)
                    for qn in qts['question_numbers']
                )
                question_scores.append(ts)
                total_score += ts
        else:
            question_scores, total_score = [], 0.0
            for question in questions:
                r = next((r for r in student_results if r.question_id == question.id), None)
                s = r.score if r else 0
                question_scores.append(s)
                total_score += s

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
        'exam': exam, 'exam_info': exam_info, 'questions': questions,
        'results': results, 'total_max_score': total_max_score,
        'question_types_summary': question_types_summary,
    })
    return templates.TemplateResponse('teacher/view_results.html', context)


# ============================================================================
# DOWNLOAD RESULTS
# ============================================================================

@router.get("/download/{exam_id}/{format}")
async def download_results(
    request: Request, exam_id: int, format: str,
    db: AsyncSession = Depends(get_db),
):
    exam = (await db.execute(select(Exam).where(Exam.id == exam_id))).scalar_one_or_none()
    if not exam:
        flash(request, 'Imtihon topilmadi', 'danger')
        return RedirectResponse(url="/teacher/dashboard", status_code=303)

    sq = select(Student).where(Student.class_id == exam.class_id)
    if exam.gender_filter != 0:
        sq = sq.where(Student.gender == exam.gender_filter)
    if exam.group_filter != 0:
        sq = sq.where(Student.group_number == exam.group_filter)
    students = (await db.execute(
        sq.order_by(Student.group_number, Student.last_name, Student.first_name)
    )).scalars().all()

    questions = (await db.execute(
        select(Question).where(Question.exam_id == exam_id).order_by(Question.question_number)
    )).scalars().all()
    class_obj = (await db.execute(select(SchoolClass).where(SchoolClass.id == exam.class_id))).scalar_one_or_none()
    subject = (await db.execute(select(Subject).where(Subject.id == exam.subject_id))).scalar_one_or_none()
    quarter = (await db.execute(select(Quarter).where(Quarter.id == exam.quarter_id))).scalar_one_or_none() if exam.quarter_id else None
    exam_type = (await db.execute(select(ExamType).where(ExamType.id == exam.exam_type_id))).scalar_one_or_none()
    exam_name = (await db.execute(select(ExamName).where(ExamName.id == exam.exam_name_id))).scalar_one_or_none()
    teacher = (await db.execute(select(Employee).where(Employee.id == exam.teacher_id))).scalar_one_or_none()
    school = None
    if class_obj and class_obj.school_id:
        school = (await db.execute(select(School).where(School.id == class_obj.school_id))).scalar_one_or_none()

    period_label = exam.period or (quarter.name if quarter else '')
    group_label = f" ({exam.group_filter}-guruh)" if exam.group_filter else ""
    header = (f"{class_obj.name if class_obj else ''}-sinfida {subject.name if subject else ''} "
              f"fanidan o'tkazilgan {period_label}\n"
              f"N{exam.variant} {exam_name.name if exam_name else ''} tahlili{group_label}")
    teacher_name = f"{teacher.first_name} {teacher.last_name}" if teacher else ''
    exam_date = exam.exam_date or (exam.created_at.strftime('%d.%m.%Y') if exam.created_at else '')
    total_max_score = sum(q.max_score for q in questions)
    show_groups = exam.group_filter != 0

    students_by_group: dict = {}
    for student in students:
        grp = student.group_number if show_groups else 0
        students_by_group.setdefault(grp, []).append(student)

    question_types_summary = []
    if exam.is_chsb_exam:
        all_qt_ids = list({q.question_type_id for q in questions})
        qt_map = {
            qt.id: qt for qt in (await db.execute(
                select(QuestionType).where(QuestionType.id.in_(all_qt_ids))
            )).scalars().all()
        }
        type_groups: dict = {}
        for q in questions:
            tid = q.question_type_id
            if tid not in type_groups:
                qt = qt_map.get(tid)
                type_groups[tid] = {'name': qt.name if qt else '', 'questions': [], 'total_max_score': 0.0}
            type_groups[tid]['questions'].append(q.question_number)
            type_groups[tid]['total_max_score'] += q.max_score
        for tid, grp in type_groups.items():
            cnt = len(grp['questions'])
            tms = round(grp['total_max_score'], 4)
            question_types_summary.append({
                'id': tid, 'name': grp['name'], 'count': cnt,
                'question_numbers': sorted(grp['questions']), 'total_max_score': tms,
                'score_per_question': round(tms / cnt, 4) if cnt else 0,
            })

    # Load all results once — eliminates per-student queries
    all_exam_results = (await db.execute(
        select(ExamResult).where(ExamResult.exam_id == exam_id)
    )).scalars().all()
    results_by_student: dict = {}
    for er in all_exam_results:
        results_by_student.setdefault(er.student_id, []).append(er)

    students_data = []
    for grp_num in sorted(students_by_group.keys()):
        for student in students_by_group[grp_num]:
            student_results = results_by_student.get(student.id, [])

            scores, total_score = [], 0.0
            if exam.is_chsb_exam:
                for qts in question_types_summary:
                    ts = 0.0
                    for qn in qts['question_numbers']:
                        q_obj = next((q for q in questions if q.question_number == qn), None)
                        if q_obj:
                            r = next((r for r in student_results if r.question_id == q_obj.id), None)
                            ts += r.score if r else 0
                    scores.append(ts)
                    total_score += ts
            else:
                for question in questions:
                    r = next((r for r in student_results if r.question_id == question.id), None)
                    s = r.score if r else 0
                    scores.append(s)
                    total_score += s

            percentage = (total_score / total_max_score * 100) if total_max_score > 0 else 0
            students_data.append({
                'Ism': student.first_name, 'Familiya': student.last_name,
                'Guruh': student.group_number if show_groups else None,
                'Jami ball': total_score, 'Foiz': f"{round(percentage, 1)}%",
                'scores': scores,
            })

    exam_data = {
        'header': header, 'teacher': teacher_name, 'date': exam_date,
        'students': students_data, 'questions': questions,
        'question_types_summary': question_types_summary,
        'is_bsb_exam': exam.is_bsb_exam, 'is_chsb_exam': exam.is_chsb_exam,
        'is_project_exam': exam.is_project_exam, 'show_groups': show_groups,
        'variant': exam.variant, 'total_max_score': total_max_score,
    }

    try:
        quarter_name = (exam.period or (quarter.name if quarter else 'chorak')).replace(' ', '_')
        class_name = (class_obj.name if class_obj else 'sinf').replace(' ', '_').replace('-', '')
        exam_nm_str = (exam_name.name if exam_name else 'imtihon').replace(' ', '_')
        base = '_'.join(''.join(c for c in s if c.isalnum() or c == '_')
                        for s in [quarter_name, class_name, exam_nm_str])

        if format == 'excel':
            output = await run_in_threadpool(generate_excel_report, exam_data)
            return StreamingResponse(BytesIO(output.getvalue()),
                media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                headers={'Content-Disposition': f'attachment; filename={base}.xlsx'})
        elif format == 'pdf':
            output = await run_in_threadpool(generate_pdf_report, exam_data)
            return StreamingResponse(BytesIO(output.getvalue()),
                media_type='application/pdf',
                headers={'Content-Disposition': f'attachment; filename={base}.pdf'})
        elif format == 'word':
            output = await run_in_threadpool(generate_word_report, exam_data)
            return StreamingResponse(BytesIO(output.getvalue()),
                media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                headers={'Content-Disposition': f'attachment; filename={base}.docx'})
        else:
            flash(request, "Noto'g'ri format", 'danger')
            return RedirectResponse(url=f"/teacher/results/{exam_id}", status_code=303)
    except Exception as e:
        flash(request, f'Xatolik yuz berdi: {str(e)}', 'danger')
        return RedirectResponse(url=f"/teacher/results/{exam_id}", status_code=303)
