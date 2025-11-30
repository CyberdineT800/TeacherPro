from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, delete
from typing import Optional
from io import BytesIO

from models import (
    CHSBQuestionAssignment, get_db, Employee, School, SchoolClass, Student, Subject, Quarter, 
    ExamName, ExamType, QuestionType, Exam, Question, ExamResult
)
from dependencies import require_login, flash, get_template_context
from utils import generate_excel_report, generate_pdf_report, generate_word_report

router = APIRouter(prefix="/teacher", dependencies=[Depends(require_login)])
templates = Jinja2Templates(directory="templates")

# ============================================================================
# TEACHER DASHBOARD
# ============================================================================

@router.get("/dashboard", response_class=HTMLResponse)
async def teacher_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Teacher dashboard"""
    teacher_id = request.session.get('user_id')
    
    # Get teacher info
    teacher_result = await db.execute(select(Employee).where(Employee.id == teacher_id))
    employee = teacher_result.scalar_one_or_none()
    
    # Get teacher's exams
    exams_result = await db.execute(
        select(Exam)
        .where(Exam.teacher_id == teacher_id)
        .order_by(Exam.created_at.desc())
        .limit(10)
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
    
    context = await get_template_context(request)
    context.update({
        'employee': employee,
        'school': school,
        'exams': exams_data
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
    """Display create exam form"""
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
    
    exam_names_result = await db.execute(select(ExamName))
    exam_names = exam_names_result.scalars().all()
    
    exam_types_result = await db.execute(select(ExamType))
    exam_types = exam_types_result.scalars().all()
    
    question_types_result = await db.execute(select(QuestionType))
    question_types = question_types_result.scalars().all()
    
    default_chsb_exam_type_result = await db.execute(select(ExamType).where(ExamType.name == "Test"))
    default_chsb_exam_type = default_chsb_exam_type_result.scalar_one_or_none()
    
    context = await get_template_context(request)
    context.update({
        'classes': classes,
        'subjects': subjects,
        'quarters': quarters,
        'exam_names': exam_names,
        'exam_types': exam_types,
        'question_types': question_types,
        'default_chsb_exam_type_id': default_chsb_exam_type.id if default_chsb_exam_type else 1
    })
    
    if not classes or not subjects:
        flash(request, 'Sizga sinf yoki fan biriktirilmagan. Administrator bilan bog\'laning.', 'warning')
    
    return templates.TemplateResponse('teacher/create_exam.html', context)

@router.post("/create-exam")
async def create_exam(
    request: Request,
    class_id: int = Form(...),
    subject_id: int = Form(...),
    quarter_id: int = Form(...),
    exam_name_id: int = Form(...),
    exam_type_id: int = Form(...),
    num_questions: int = Form(...),
    gender_filter: int = Form(...),
    group_filter: int = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Create new exam"""
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
    
    if is_chsb_exam:
        exam_type_result = await db.execute(select(ExamType).where(ExamType.name == "Test"))
        forced_exam_type = exam_type_result.scalar_one_or_none()
        if forced_exam_type:
            exam_type_id = forced_exam_type.id
    
    exam = Exam(
        class_id=class_id,
        subject_id=subject_id,
        quarter_id=quarter_id,
        exam_name_id=exam_name_id,
        exam_type_id=exam_type_id,
        teacher_id=teacher_id,
        is_bsb_exam=is_bsb_exam,
        is_chsb_exam=is_chsb_exam,
        gender_filter=gender_filter, 
        group_filter=group_filter
    )
    db.add(exam)
    await db.flush()
    
    form_data = await request.form()
    
    if is_bsb_exam:
        num_questions = 5
        default_question_type_id = 1
        
        for i in range(1, num_questions + 1):
            question = Question(
                exam_id=exam.id,
                question_number=i,
                question_type_id=default_question_type_id,
                max_score=5.0
            )
            db.add(question)
    
    elif is_chsb_exam:
        num_questions = 10
        
        chsb_assignments = {}
        for i in range(1, num_questions + 1):
            question_type_id = form_data.get(f'chsb_question_type_{i}')
            if question_type_id:
                chsb_assignments[i] = int(question_type_id)
                
                assignment = CHSBQuestionAssignment(
                    exam_id=exam.id,
                    question_number=i,
                    question_type_id=int(question_type_id),
                    max_score=4.0  
                )
                db.add(assignment)
        
        import json
        exam.chsb_config = json.dumps(chsb_assignments)
        
        for i in range(1, num_questions + 1):
            question_type_id = chsb_assignments.get(i, 1)  
            question = Question(
                exam_id=exam.id,
                question_number=i,
                question_type_id=question_type_id,
                max_score=4.0
            )
            db.add(question)

    else:
        for i in range(1, num_questions + 1):
            question_type_id = form_data.get(f'question_type_{i}')
            max_score = form_data.get(f'max_score_{i}')
            
            if question_type_id and max_score:
                question = Question(
                    exam_id=exam.id,
                    question_number=i,
                    question_type_id=int(question_type_id),
                    max_score=float(max_score)
                )
                db.add(question)
    
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
    
    student_query = student_query.order_by(Student.last_name, Student.first_name)
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
    
    quarter_result = await db.execute(select(Quarter).where(Quarter.id == exam.quarter_id))
    quarter = quarter_result.scalar_one_or_none()
    
    exam_name_result = await db.execute(select(ExamName).where(ExamName.id == exam.exam_name_id))
    exam_name = exam_name_result.scalar_one_or_none()
    
    exam_type_result = await db.execute(select(ExamType).where(ExamType.id == exam.exam_type_id))
    exam_type = exam_type_result.scalar_one_or_none()
    
    exam_info = {
        'class_name': class_obj.name if class_obj else '',
        'leader_fullname': f"{class_obj.leader_first_name} {class_obj.leader_last_name}" if class_obj else '',
        'leader_phone': class_obj.leader_phone if class_obj else '',
        'subject_name': subject.name if subject else '',
        'quarter_name': quarter.name if quarter else '',
        'exam_name': exam_name.name if exam_name else '',
        'exam_type_name': exam_type.name if exam_type else ''
    }
    
    question_types_dict = {}
    for question in questions:
        qt_result = await db.execute(select(QuestionType).where(QuestionType.id == question.question_type_id))
        qt = qt_result.scalar_one_or_none()
        question_types_dict[question.id] = qt.name if qt else ''
    
    question_types_summary = []
    if exam.is_chsb_exam:
        chsb_assignments_result = await db.execute(
            select(CHSBQuestionAssignment)
            .where(CHSBQuestionAssignment.exam_id == exam_id)
            .options(selectinload(CHSBQuestionAssignment.question_type)))
        
        chsb_assignments = chsb_assignments_result.scalars().all()
        
        type_groups = {}
        for assignment in chsb_assignments:
            type_id = assignment.question_type_id
            if type_id not in type_groups:
                type_groups[type_id] = {
                    'type': assignment.question_type,
                    'questions': [],
                    'total_max_score': 0
                }
            type_groups[type_id]['questions'].append(assignment.question_number)
            type_groups[type_id]['total_max_score'] += assignment.max_score
        
        for type_id, group in type_groups.items():
            question_types_summary.append({
                'id': type_id,
                'name': group['type'].name,
                'count': len(group['questions']),
                'question_numbers': sorted(group['questions']),
                'total_max_score': group['total_max_score']
            })

    context = await get_template_context(request)
    context.update({
        'exam': exam,
        'exam_info': exam_info,
        'students': students,
        'questions': questions,
        'question_types': question_types_dict,
        'question_types_summary': question_types_summary, 
        'group_filter': exam.group_filter
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
    
    for student in students:
        if exam.is_chsb_exam:
            chsb_assignments_result = await db.execute(
                select(CHSBQuestionAssignment)
                .where(CHSBQuestionAssignment.exam_id == exam_id)
            )
            chsb_assignments = chsb_assignments_result.scalars().all()
            
            assignments_by_type = {}
            for assignment in chsb_assignments:
                if assignment.question_type_id not in assignments_by_type:
                    assignments_by_type[assignment.question_type_id] = []
                assignments_by_type[assignment.question_type_id].append(assignment)
            
            for question_type_id, assignments in assignments_by_type.items():
                score_key = f'chsb_score_{student.id}_{question_type_id}'
                score_value = form_data.get(score_key)
                
                if score_value:
                    total_score = float(score_value)
                    num_questions = len(assignments)
                    if num_questions > 0:
                        score_per_question = total_score / num_questions
                        
                        for assignment in assignments:
                            question = next((q for q in questions if q.question_number == assignment.question_number), None)
                            if question:
                                result = ExamResult(
                                    exam_id=exam_id,
                                    student_id=student.id,
                                    question_id=question.id,
                                    score=score_per_question
                                )
                                db.add(result)
        else:
            for question in questions:
                score_key = f'score_{student.id}_{question.id}'
                score_value = form_data.get(score_key)
                
                if score_value:
                    result = ExamResult(
                        exam_id=exam_id,
                        student_id=student.id,
                        question_id=question.id,
                        score=float(score_value)
                    )
                    db.add(result)
    
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
    
    student_query = student_query.order_by(Student.last_name, Student.first_name)
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
    
    quarter_result = await db.execute(select(Quarter).where(Quarter.id == exam.quarter_id))
    quarter = quarter_result.scalar_one_or_none()
    
    exam_type_result = await db.execute(select(ExamType).where(ExamType.id == exam.exam_type_id))
    exam_type = exam_type_result.scalar_one_or_none()

    exam_name_result = await db.execute(select(ExamName).where(ExamName.id == exam.exam_name_id))
    exam_name = exam_name_result.scalar_one_or_none()
    
    teacher_result = await db.execute(select(Employee).where(Employee.id == exam.teacher_id))
    teacher = teacher_result.scalar_one_or_none()
    
    exam_info = {
        'class_name': class_obj.name if class_obj else '',
        'leader_fullname': f"{class_obj.leader_first_name} {class_obj.leader_last_name}" if class_obj else '',
        'leader_phone': class_obj.leader_phone if class_obj else '',
        'subject_name': subject.name if subject else '',
        'quarter_name': quarter.name if quarter else '',
        'exam_type_name': exam_type.name if exam_type else '',
        'exam_name': exam_name.name if exam_name else '',
        'teacher_name': f"{teacher.first_name} {teacher.last_name}" if teacher else ''
    }
    
    total_max_score = sum(q.max_score for q in questions)
    
    question_types_summary = []
    if exam.is_chsb_exam:
        chsb_assignments_result = await db.execute(
            select(CHSBQuestionAssignment)
            .where(CHSBQuestionAssignment.exam_id == exam_id)
            .options(selectinload(CHSBQuestionAssignment.question_type)))

        chsb_assignments = chsb_assignments_result.scalars().all()
        
        type_groups = {}
        for assignment in chsb_assignments:
            type_id = assignment.question_type_id
            if type_id not in type_groups:
                type_groups[type_id] = {
                    'type': assignment.question_type,
                    'questions': [],
                    'total_max_score': 0
                }
            type_groups[type_id]['questions'].append(assignment.question_number)
            type_groups[type_id]['total_max_score'] += assignment.max_score
        
        for type_id, group in type_groups.items():
            question_types_summary.append({
                'id': type_id,
                'name': group['type'].name,
                'count': len(group['questions']),
                'question_numbers': group['questions'],
                'total_max_score': group['total_max_score']
            })
    
    results = []
    for student in students:
        student_results_query = await db.execute(
            select(ExamResult)
            .where(ExamResult.exam_id == exam_id, ExamResult.student_id == student.id)
        )
        student_results = student_results_query.scalars().all()
        
        if exam.is_chsb_exam:
            question_scores = []
            total_score = 0
            
            for qtype_summary in question_types_summary:
                type_score = 0
                for q_num in qtype_summary['question_numbers']:
                    question = next((q for q in questions if q.question_number == q_num), None)
                    if question:
                        result = next((r for r in student_results if r.question_id == question.id), None)
                        score = result.score if result else 0
                        type_score += score
                question_scores.append(type_score)
                total_score += type_score
        else:
            question_scores = []
            total_score = 0
            
            for question in questions:
                result = next((r for r in student_results if r.question_id == question.id), None)
                score = result.score if result else 0
                question_scores.append(score)
                total_score += score
        
        percentage = (total_score / total_max_score * 100) if total_max_score > 0 else 0
        
        results.append({
            'student_name': f"{student.first_name} {student.last_name}",
            'group_number': student.group_number,
            'question_scores': question_scores,
            'total_score': total_score,
            'percentage': round(percentage, 1)
        })
    
    context = await get_template_context(request)
    context.update({
        'exam': exam,
        'exam_info': exam_info,
        'questions': questions,
        'results': results,
        'total_max_score': total_max_score,
        'question_types_summary': question_types_summary
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
    
    student_query = student_query.order_by(Student.last_name, Student.first_name)
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
    
    quarter_result = await db.execute(select(Quarter).where(Quarter.id == exam.quarter_id))
    quarter = quarter_result.scalar_one_or_none()
    
    exam_type_result = await db.execute(select(ExamType).where(ExamType.id == exam.exam_type_id))
    exam_type = exam_type_result.scalar_one_or_none()

    exam_name_result = await db.execute(select(ExamName).where(ExamName.id == exam.exam_name_id))
    exam_name = exam_name_result.scalar_one_or_none()
    
    teacher_result = await db.execute(select(Employee).where(Employee.id == exam.teacher_id))
    teacher = teacher_result.scalar_one_or_none()
    
    header = f"{class_obj.name} - {subject.name} - {quarter.name}\n{exam_type.name} - {exam_name.name}"
    teacher_name = f"{teacher.first_name} {teacher.last_name}" if teacher else ''
    exam_date = exam.created_at.strftime('%d.%m.%Y') if exam.created_at else ''
    
    total_max_score = sum(q.max_score for q in questions)
    
    students_data = []
    for student in students:
        student_results_query = await db.execute(
            select(ExamResult)
            .where(ExamResult.exam_id == exam_id, ExamResult.student_id == student.id)
        )
        student_results = student_results_query.scalars().all()
        
        scores = []
        total_score = 0
        
        for question in questions:
            result = next((r for r in student_results if r.question_id == question.id), None)
            score = result.score if result else 0
            scores.append(score)
            total_score += score
        
        percentage = (total_score / total_max_score * 100) if total_max_score > 0 else 0
        
        student_row = {
            'Ism': student.first_name,
            'Familiya': student.last_name,
            'Guruh': student.group_number,
            'Jami ball': total_score,
            'Foiz': f"{round(percentage, 1)}%"
        }
        
        for i, score in enumerate(scores, 1):
            student_row[f'Savol {i}'] = score
        
        students_data.append(student_row)
    
    exam_data = {
        'header': header,
        'teacher': teacher_name,
        'date': exam_date,
        'students': students_data
    }
    
    try:
        if format == 'excel':
            output = await generate_excel_report(exam_data)
            return StreamingResponse(
                BytesIO(output.getvalue()),
                media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                headers={'Content-Disposition': f'attachment; filename=natijalar_{exam_id}.xlsx'}
            )
        elif format == 'pdf':
            output = await generate_pdf_report(exam_data)
            return StreamingResponse(
                BytesIO(output.getvalue()),
                media_type='application/pdf',
                headers={'Content-Disposition': f'attachment; filename=natijalar_{exam_id}.pdf'}
            )
        elif format == 'word':
            output = await generate_word_report(exam_data)
            return StreamingResponse(
                BytesIO(output.getvalue()),
                media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                headers={'Content-Disposition': f'attachment; filename=natijalar_{exam_id}.docx'}
            )
        else:
            flash(request, "Noto'g'ri format", 'danger')
            return RedirectResponse(url=f"/teacher/results/{exam_id}", status_code=303)
    except Exception as e:
        flash(request, f'Xatolik yuz berdi: {str(e)}', 'danger')
        return RedirectResponse(url=f"/teacher/results/{exam_id}", status_code=303)