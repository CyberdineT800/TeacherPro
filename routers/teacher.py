from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import Optional
from io import BytesIO

from models import (
    get_db, Employee, School, SchoolClass, Student, Subject, Quarter, 
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
    
    # Get teacher info
    teacher_result = await db.execute(select(Employee).where(Employee.id == teacher_id))
    teacher = teacher_result.scalar_one_or_none()
    
    # Get classes in teacher's school
    classes = []
    if teacher and teacher.school_id:
        classes_result = await db.execute(
            select(SchoolClass).where(SchoolClass.school_id == teacher.school_id)
        )
        classes = classes_result.scalars().all()
    
    # Get reference data
    subjects_result = await db.execute(select(Subject))
    subjects = subjects_result.scalars().all()
    
    quarters_result = await db.execute(select(Quarter).order_by(Quarter.order_num))
    quarters = quarters_result.scalars().all()
    
    exam_names_result = await db.execute(select(ExamName))
    exam_names = exam_names_result.scalars().all()
    
    exam_types_result = await db.execute(select(ExamType))
    exam_types = exam_types_result.scalars().all()
    
    question_types_result = await db.execute(select(QuestionType))
    question_types = question_types_result.scalars().all()
    
    context = await get_template_context(request)
    context.update({
        'classes': classes,
        'subjects': subjects,
        'quarters': quarters,
        'exam_names': exam_names,
        'exam_types': exam_types,
        'question_types': question_types
    })
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
    db: AsyncSession = Depends(get_db)
):
    """Create new exam"""
    teacher_id = request.session.get('user_id')
    
    # Create exam
    exam = Exam(
        class_id=class_id,
        subject_id=subject_id,
        quarter_id=quarter_id,
        exam_name_id=exam_name_id,
        exam_type_id=exam_type_id,
        teacher_id=teacher_id
    )
    db.add(exam)
    await db.flush()
    
    # Get form data
    form_data = await request.form()
    
    # Add questions
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
    group_filter: str = 'all',
    db: AsyncSession = Depends(get_db)
):
    """Display enter scores form"""
    # Get exam
    exam_result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = exam_result.scalar_one_or_none()
    if not exam:
        flash(request, 'Imtihon topilmadi', 'danger')
        return RedirectResponse(url="/teacher/dashboard", status_code=303)
    
    # Get students with filtering
    if group_filter == '1':
        students_result = await db.execute(
            select(Student)
            .where(Student.class_id == exam.class_id, Student.group_number == 1)
            .order_by(Student.last_name, Student.first_name)
        )
    elif group_filter == '2':
        students_result = await db.execute(
            select(Student)
            .where(Student.class_id == exam.class_id, Student.group_number == 2)
            .order_by(Student.last_name, Student.first_name)
        )
    else:
        students_result = await db.execute(
            select(Student)
            .where(Student.class_id == exam.class_id)
            .order_by(Student.last_name, Student.first_name)
        )
    students = students_result.scalars().all()
    
    # Get questions
    questions_result = await db.execute(
        select(Question)
        .where(Question.exam_id == exam_id)
        .order_by(Question.question_number)
    )
    questions = questions_result.scalars().all()
    
    # Get exam info
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
        'subject_name': subject.name if subject else '',
        'quarter_name': quarter.name if quarter else '',
        'exam_name': exam_name.name if exam_name else '',
        'exam_type_name': exam_type.name if exam_type else ''
    }
    
    # Get question types
    question_types_dict = {}
    for question in questions:
        qt_result = await db.execute(select(QuestionType).where(QuestionType.id == question.question_type_id))
        qt = qt_result.scalar_one_or_none()
        question_types_dict[question.id] = qt.name if qt else ''
    
    context = await get_template_context(request)
    context.update({
        'exam': exam,
        'exam_info': exam_info,
        'students': students,
        'questions': questions,
        'question_types': question_types_dict,
        'group_filter': group_filter
    })
    return templates.TemplateResponse('teacher/enter_scores.html', context)

@router.post("/enter-scores/{exam_id}")
async def enter_scores(
    request: Request,
    exam_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Save exam scores"""
    # Get exam
    exam_result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = exam_result.scalar_one_or_none()
    if not exam:
        flash(request, 'Imtihon topilmadi', 'danger')
        return RedirectResponse(url="/teacher/dashboard", status_code=303)
    
    # Get students
    students_result = await db.execute(select(Student).where(Student.class_id == exam.class_id))
    students = students_result.scalars().all()
    
    # Get questions
    questions_result = await db.execute(select(Question).where(Question.exam_id == exam_id))
    questions = questions_result.scalars().all()
    
    # Delete existing results
    await db.execute(delete(ExamResult).where(ExamResult.exam_id == exam_id))
    
    # Get form data
    form_data = await request.form()
    
    # Save new results
    for student in students:
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
    # Get exam
    exam_result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = exam_result.scalar_one_or_none()
    if not exam:
        flash(request, 'Imtihon topilmadi', 'danger')
        return RedirectResponse(url="/teacher/dashboard", status_code=303)
    
    # Get students
    students_result = await db.execute(
        select(Student)
        .where(Student.class_id == exam.class_id)
        .order_by(Student.last_name, Student.first_name)
    )
    students = students_result.scalars().all()
    
    # Get questions
    questions_result = await db.execute(
        select(Question)
        .where(Question.exam_id == exam_id)
        .order_by(Question.question_number)
    )
    questions = questions_result.scalars().all()
    
    # Get exam info
    class_result = await db.execute(select(SchoolClass).where(SchoolClass.id == exam.class_id))
    class_obj = class_result.scalar_one_or_none()
    
    subject_result = await db.execute(select(Subject).where(Subject.id == exam.subject_id))
    subject = subject_result.scalar_one_or_none()
    
    quarter_result = await db.execute(select(Quarter).where(Quarter.id == exam.quarter_id))
    quarter = quarter_result.scalar_one_or_none()
    
    exam_type_result = await db.execute(select(ExamType).where(ExamType.id == exam.exam_type_id))
    exam_type = exam_type_result.scalar_one_or_none()
    
    teacher_result = await db.execute(select(Employee).where(Employee.id == exam.teacher_id))
    teacher = teacher_result.scalar_one_or_none()
    
    exam_info = {
        'class_name': class_obj.name if class_obj else '',
        'subject_name': subject.name if subject else '',
        'quarter_name': quarter.name if quarter else '',
        'exam_type_name': exam_type.name if exam_type else '',
        'teacher_name': f"{teacher.first_name} {teacher.last_name}" if teacher else ''
    }
    
    # Calculate max score
    total_max_score = sum(q.max_score for q in questions)
    
    # Calculate results
    results = []
    for student in students:
        # Get student results
        student_results_query = await db.execute(
            select(ExamResult)
            .where(ExamResult.exam_id == exam_id, ExamResult.student_id == student.id)
        )
        student_results = student_results_query.scalars().all()
        
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
        'total_max_score': total_max_score
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
    # Get exam
    exam_result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = exam_result.scalar_one_or_none()
    if not exam:
        flash(request, 'Imtihon topilmadi', 'danger')
        return RedirectResponse(url="/teacher/dashboard", status_code=303)
    
    # Get students
    students_result = await db.execute(
        select(Student)
        .where(Student.class_id == exam.class_id)
        .order_by(Student.last_name, Student.first_name)
    )
    students = students_result.scalars().all()
    
    # Get questions
    questions_result = await db.execute(
        select(Question)
        .where(Question.exam_id == exam_id)
        .order_by(Question.question_number)
    )
    questions = questions_result.scalars().all()
    
    # Get exam info
    class_result = await db.execute(select(SchoolClass).where(SchoolClass.id == exam.class_id))
    class_obj = class_result.scalar_one_or_none()
    
    subject_result = await db.execute(select(Subject).where(Subject.id == exam.subject_id))
    subject = subject_result.scalar_one_or_none()
    
    quarter_result = await db.execute(select(Quarter).where(Quarter.id == exam.quarter_id))
    quarter = quarter_result.scalar_one_or_none()
    
    exam_type_result = await db.execute(select(ExamType).where(ExamType.id == exam.exam_type_id))
    exam_type = exam_type_result.scalar_one_or_none()
    
    teacher_result = await db.execute(select(Employee).where(Employee.id == exam.teacher_id))
    teacher = teacher_result.scalar_one_or_none()
    
    header = f"{class_obj.name} - {subject.name} - {quarter.name}\n{exam_type.name}"
    teacher_name = f"{teacher.first_name} {teacher.last_name}" if teacher else ''
    exam_date = exam.created_at.strftime('%d.%m.%Y') if exam.created_at else ''
    
    # Calculate max score
    total_max_score = sum(q.max_score for q in questions)
    
    # Prepare student data
    students_data = []
    for student in students:
        # Get student results
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
        
        # Add question scores
        for i, score in enumerate(scores, 1):
            student_row[f'Savol {i}'] = score
        
        students_data.append(student_row)
    
    exam_data = {
        'header': header,
        'teacher': teacher_name,
        'date': exam_date,
        'students': students_data
    }
    
    # Generate file based on format
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