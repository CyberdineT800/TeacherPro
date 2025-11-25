from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from datetime import datetime
from typing import Optional

from models import (
    get_db, School, Employee, StaffTitle, SchoolClass, Student, 
    Subject, Quarter, ExamName, ExamType, QuestionType, Exam, Question, ExamResult,
    TeacherClass, TeacherSubject
)
from dependencies import require_admin, flash, get_template_context
from utils import process_student_excel

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory="templates")


# ============================================================================
# DASHBOARD
# ============================================================================

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Admin dashboard"""
    schools_count = (await db.execute(select(School))).scalars().all()
    employees_count = (await db.execute(select(Employee))).scalars().all()
    classes_count = (await db.execute(select(SchoolClass))).scalars().all()
    students_count = (await db.execute(select(Student))).scalars().all()
    
    context = await get_template_context(request)
    context.update({
        'schools_count': len(schools_count),
        'employees_count': len(employees_count),
        'classes_count': len(classes_count),
        'students_count': len(students_count)
    })
    return templates.TemplateResponse('admin_dashboard.html', context)

# ============================================================================
# LANGUAGE MANAGEMENT
# ============================================================================

@router.get("/languages", response_class=HTMLResponse)
async def manage_languages(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Manage translation keys"""
    from language import language_manager
    
    # Get all unique keys across all languages
    all_keys = set()
    for lang_translations in language_manager.translations.values():
        all_keys.update(lang_translations.keys())
    
    # Build translation data
    translations_data = []
    for key in sorted(all_keys):
        translations_data.append({
            'key': key,
            'uz': language_manager.get(key, 'uz', ''),
            'ru': language_manager.get(key, 'ru', ''),
            'en': language_manager.get(key, 'en', '')
        })
    
    context = await get_template_context(request, db)
    context.update({
        'translations': translations_data,
        'languages': language_manager.get_available_languages()
    })
    return templates.TemplateResponse('admin/languages.html', context)

@router.post("/languages/save")
async def save_translation(
    request: Request,
    key: str = Form(...),
    value_uz: str = Form(""),
    value_ru: str = Form(""),
    value_en: str = Form(""),
    original_key: str = Form(""),
    db: AsyncSession = Depends(get_db)
):
    """Save translation for all languages"""
    from language import language_manager
    
    try:
        # If key was changed, delete old key
        if original_key and original_key != key:
            for lang in ['uz', 'ru', 'en']:
                language_manager.delete_translation(lang, original_key)
        
        # Save new translations
        if value_uz:
            language_manager.save_translation('uz', key, value_uz)
        if value_ru:
            language_manager.save_translation('ru', key, value_ru)
        if value_en:
            language_manager.save_translation('en', key, value_en)
        
        flash(request, 'Tarjima saqlandi', 'success')
    except Exception as e:
        flash(request, f'Xatolik: {str(e)}', 'danger')
    
    return RedirectResponse(url="/admin/languages", status_code=303)

@router.post("/languages/delete/{key}")
async def delete_translation(
    request: Request,
    key: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete translation key from all languages"""
    from language import language_manager
    
    try:
        for lang in ['uz', 'ru', 'en']:
            language_manager.delete_translation(lang, key)
        flash(request, 'Tarjima o\'chirildi', 'success')
    except Exception as e:
        flash(request, f'Xatolik: {str(e)}', 'danger')
    
    return RedirectResponse(url="/admin/languages", status_code=303)


# ============================================================================
# SCHOOL MANAGEMENT
# ============================================================================

@router.get("/schools", response_class=HTMLResponse)
async def schools_list(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """List all schools"""
    result = await db.execute(select(School).order_by(School.created_at.desc()))
    schools = result.scalars().all()
    
    context = await get_template_context(request)
    context['schools'] = schools
    return templates.TemplateResponse('admin/schools.html', context)

@router.get("/schools/add", response_class=HTMLResponse)
async def add_school_page(request: Request):
    """Display add school form"""
    context = await get_template_context(request)
    context['school'] = None
    return templates.TemplateResponse('admin/school_form.html', context) 

@router.post("/schools/add")
async def add_school(
    request: Request,
    name: str = Form(...),
    address: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    db: AsyncSession = Depends(get_db)
):
    """Create new school"""
    school = School(name=name, address=address, phone=phone, email=email)
    db.add(school)
    await db.commit()
    flash(request, 'Maktab muvaffaqiyatli qo\'shildi', 'success')
    return RedirectResponse(url="/admin/schools", status_code=303)

@router.get("/schools/edit/{id}", response_class=HTMLResponse)
async def edit_school_page(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db)
):
    """Display edit school form"""
    result = await db.execute(select(School).where(School.id == id))
    school = result.scalar_one_or_none()
    if not school:
        flash(request, 'Maktab topilmadi', 'danger')
        return RedirectResponse(url="/admin/schools", status_code=303)
    
    context = await get_template_context(request)
    context['school'] = school
    return templates.TemplateResponse('admin/school_form.html', context) 

@router.post("/schools/edit/{id}")
async def edit_school(
    request: Request,
    id: int,
    name: str = Form(...),
    address: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    db: AsyncSession = Depends(get_db)
):
    """Update school"""
    result = await db.execute(select(School).where(School.id == id))
    school = result.scalar_one_or_none()
    if not school:
        flash(request, 'Maktab topilmadi', 'danger')
        return RedirectResponse(url="/admin/schools", status_code=303)
    
    school.name = name
    school.address = address
    school.phone = phone
    school.email = email
    await db.commit()
    flash(request, 'Maktab ma\'lumotlari yangilandi', 'success')
    return RedirectResponse(url="/admin/schools", status_code=303)

@router.post("/schools/delete/{id}")
async def delete_school(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete school and all related data"""
    result = await db.execute(select(School).where(School.id == id))
    school = result.scalar_one_or_none()
    if not school:
        flash(request, 'Maktab topilmadi', 'danger')
        return RedirectResponse(url="/admin/schools", status_code=303)
    
    try:
        # Get all classes in this school
        classes_result = await db.execute(select(SchoolClass).where(SchoolClass.school_id == id))
        classes_in_school = classes_result.scalars().all()
        
        for class_obj in classes_in_school:
            # Delete exams and related data
            exams_result = await db.execute(select(Exam).where(Exam.class_id == class_obj.id))
            exams_in_class = exams_result.scalars().all()
            
            for exam in exams_in_class:
                await db.execute(delete(Question).where(Question.exam_id == exam.id))
                await db.execute(delete(ExamResult).where(ExamResult.exam_id == exam.id))
                await db.delete(exam)
            
            # Delete students
            await db.execute(delete(Student).where(Student.class_id == class_obj.id))
            await db.delete(class_obj)
        
        # Update employees to remove school reference
        employees_result = await db.execute(select(Employee).where(Employee.school_id == id))
        employees = employees_result.scalars().all()
        for emp in employees:
            emp.school_id = None
        
        await db.delete(school)
        await db.commit()
        
        flash(request, 'Maktab va unga bog\'liq barcha ma\'lumotlar o\'chirildi', 'success')
    except Exception as e:
        await db.rollback()
        flash(request, f'Maktabni o\'chirishda xatolik: {str(e)}', 'danger')
    
    return RedirectResponse(url="/admin/schools", status_code=303)

# ============================================================================
# EMPLOYEE MANAGEMENT
# ============================================================================

@router.get("/employees", response_class=HTMLResponse)
async def employees_list(
    request: Request,
    school_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List all employees"""
    if school_id and school_id.strip():
        try:
            school_id_int = int(school_id)
        except ValueError:
            school_id_int = None

    if school_id:
        result = await db.execute(
            select(Employee)
            .options(selectinload(Employee.school), selectinload(Employee.staff_title))
            .where(Employee.school_id == school_id_int)
        )
    else:
        result = await db.execute(
            select(Employee)
            .options(selectinload(Employee.school), selectinload(Employee.staff_title))
            .order_by(Employee.created_at.desc())
        )
    employees = result.scalars().all()
    
    schools_result = await db.execute(select(School))
    schools = schools_result.scalars().all()
    
    context = await get_template_context(request)
    context.update({'employees': employees, 'schools': schools})
    return templates.TemplateResponse('admin/employees.html', context)  

@router.get("/employees/add", response_class=HTMLResponse)
async def add_employee_page(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Display add employee form"""
    schools_result = await db.execute(select(School))
    schools = schools_result.scalars().all()
    
    titles_result = await db.execute(select(StaffTitle))
    titles = titles_result.scalars().all()
    
    classes_result = await db.execute(select(SchoolClass))
    classes = classes_result.scalars().all()
    
    subjects_result = await db.execute(select(Subject))
    subjects = subjects_result.scalars().all()
    
    context = await get_template_context(request)
    context.update({
        'employee': None, 
        'schools': schools, 
        'titles': titles,
        'classes': classes,
        'subjects': subjects
    })
    return templates.TemplateResponse('admin/employee_form.html', context)

@router.post("/employees/add")
async def add_employee(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(""),
    is_admin: bool = Form(False),
    is_active: bool = Form(False),
    school_id: Optional[int] = Form(None),
    staff_title_id: Optional[int] = Form(None),
    assigned_classes: list = Form([]),
    assigned_subjects: list = Form([]),
    db: AsyncSession = Depends(get_db)
):
    """Create new employee"""
    employee = Employee(
        username=username,
        first_name=first_name,
        last_name=last_name,
        email=email,
        is_admin=is_admin,
        is_active=is_active,
        school_id=school_id,
        staff_title_id=staff_title_id
    )
    employee.set_password(password)
    db.add(employee)
    await db.flush()  
    
    for class_id in assigned_classes:
        teacher_class = TeacherClass(teacher_id=employee.id, class_id=int(class_id))
        db.add(teacher_class)
    
    for subject_id in assigned_subjects:
        teacher_subject = TeacherSubject(teacher_id=employee.id, subject_id=int(subject_id))
        db.add(teacher_subject)
    
    await db.commit()
    flash(request, 'Xodim qo\'shildi', 'success')
    return RedirectResponse(url="/admin/employees", status_code=303)

@router.get("/employees/edit/{id}", response_class=HTMLResponse)
async def edit_employee_page(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db)
):
    """Display edit employee form"""
    result = await db.execute(
        select(Employee)
        .options(selectinload(Employee.assigned_classes), selectinload(Employee.assigned_subjects))
        .where(Employee.id == id)
    )
    employee = result.scalar_one_or_none()
    if not employee:
        flash(request, 'Xodim topilmadi', 'danger')
        return RedirectResponse(url="/admin/employees", status_code=303)
    
    schools_result = await db.execute(select(School))
    schools = schools_result.scalars().all()
    
    titles_result = await db.execute(select(StaffTitle))
    titles = titles_result.scalars().all()
    
    classes_result = await db.execute(select(SchoolClass))
    classes = classes_result.scalars().all()
    
    subjects_result = await db.execute(select(Subject))
    subjects = subjects_result.scalars().all()
    
    context = await get_template_context(request)
    context.update({
        'employee': employee, 
        'schools': schools, 
        'titles': titles,
        'classes': classes,
        'subjects': subjects
    })
    return templates.TemplateResponse('admin/employee_form.html', context)

@router.post("/employees/edit/{id}")
async def edit_employee(
    request: Request,
    id: int,
    username: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(""),
    is_admin: bool = Form(False),
    is_active: bool = Form(False),
    school_id: Optional[int] = Form(None),
    staff_title_id: Optional[int] = Form(None),
    assigned_classes: list = Form([]),
    assigned_subjects: list = Form([]),
    password: str = Form(""),
    db: AsyncSession = Depends(get_db)
):
    """Update employee"""
    result = await db.execute(select(Employee).where(Employee.id == id))
    employee = result.scalar_one_or_none()
    if not employee:
        flash(request, 'Xodim topilmadi', 'danger')
        return RedirectResponse(url="/admin/employees", status_code=303)
    
    employee.username = username
    employee.first_name = first_name
    employee.last_name = last_name
    employee.email = email
    employee.is_admin = is_admin
    employee.is_active = is_active
    employee.school_id = school_id
    employee.staff_title_id = staff_title_id
    employee.updated_at = datetime.utcnow()
    
    if password:
        employee.set_password(password)
    
    await db.execute(delete(TeacherClass).where(TeacherClass.teacher_id == id))
    for class_id in assigned_classes:
        teacher_class = TeacherClass(teacher_id=id, class_id=int(class_id))
        db.add(teacher_class)
    
    await db.execute(delete(TeacherSubject).where(TeacherSubject.teacher_id == id))
    for subject_id in assigned_subjects:
        teacher_subject = TeacherSubject(teacher_id=id, subject_id=int(subject_id))
        db.add(teacher_subject)
    
    await db.commit()
    flash(request, 'Xodim ma\'lumotlari yangilandi', 'success')
    return RedirectResponse(url="/admin/employees", status_code=303)

@router.post("/employees/delete/{id}")
async def delete_employee(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete employee"""
    if id == request.session.get('user_id'):
        flash(request, 'O\'zingizni o\'chira olmaysiz', 'danger')
        return RedirectResponse(url="/admin/employees", status_code=303)
    
    result = await db.execute(select(Employee).where(Employee.id == id))
    employee = result.scalar_one_or_none()
    if not employee:
        flash(request, 'Xodim topilmadi', 'danger')
        return RedirectResponse(url="/admin/employees", status_code=303)
    
    try:
        # Delete exams created by this employee
        exams_result = await db.execute(select(Exam).where(Exam.teacher_id == id))
        exams_by_employee = exams_result.scalars().all()
        
        for exam in exams_by_employee:
            await db.execute(delete(Question).where(Question.exam_id == exam.id))
            await db.execute(delete(ExamResult).where(ExamResult.exam_id == exam.id))
            await db.delete(exam)
        
        await db.delete(employee)
        await db.commit()
        
        flash(request, 'Xodim va uning yaratgan imtihonlari o\'chirildi', 'success')
    except Exception as e:
        await db.rollback()
        flash(request, f'Xodimni o\'chirishda xatolik: {str(e)}', 'danger')
    
    return RedirectResponse(url="/admin/employees", status_code=303)

@router.post("/employees/toggle-status/{id}")
async def toggle_employee_status(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db)
):
    """Toggle employee active status"""
    if id == request.session.get('user_id'):
        flash(request, 'O\'zingizni faolligini o\'zgartira olmaysiz', 'danger')
        return RedirectResponse(url="/admin/employees", status_code=303)
    
    result = await db.execute(select(Employee).where(Employee.id == id))
    employee = result.scalar_one_or_none()
    if not employee:
        flash(request, 'Xodim topilmadi', 'danger')
        return RedirectResponse(url="/admin/employees", status_code=303)
    
    employee.is_active = not employee.is_active
    employee.updated_at = datetime.utcnow()
    await db.commit()
    
    status = "faollashtirildi" if employee.is_active else "bloklandi"
    flash(request, f'Xodim {status}', 'success')
    return RedirectResponse(url="/admin/employees", status_code=303)

# ============================================================================
# CLASS MANAGEMENT
# ============================================================================

@router.get("/classes", response_class=HTMLResponse)
async def classes_list(
    request: Request,
    school_id: Optional[str] = None,  
    db: AsyncSession = Depends(get_db)
):
    """List all classes"""
    school_id_int = None
    if school_id and school_id.strip():
        try:
            school_id_int = int(school_id)
        except ValueError:
            school_id_int = None
    
    if school_id_int:
        result = await db.execute(select(SchoolClass).where(SchoolClass.school_id == school_id_int))
    else:
        result = await db.execute(select(SchoolClass).order_by(SchoolClass.created_at.desc()))
    classes = result.scalars().all()
    
    schools_result = await db.execute(select(School))
    schools = schools_result.scalars().all()
    
    students_result = await db.execute(select(Student))
    students = students_result.scalars().all()
    
    context = await get_template_context(request)
    context.update({'classes': classes, 'schools': schools, 'students': students})
    return templates.TemplateResponse('admin/classes.html', context)

@router.get("/classes/add", response_class=HTMLResponse)
async def add_class_page(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Display add class form"""
    schools_result = await db.execute(select(School))
    schools = schools_result.scalars().all()
    
    context = await get_template_context(request)
    context.update({'class_obj': None, 'schools': schools})
    return templates.TemplateResponse('admin/class_form.html', context)  

@router.post("/classes/add")
async def add_class(
    request: Request,
    name: str = Form(...),
    school_id: int = Form(...),
    students_file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db)
):
    """Create new class"""
    class_obj = SchoolClass(name=name, school_id=school_id)
    db.add(class_obj)
    await db.flush()
    
    if students_file and students_file.filename:
        try:
            students = await process_student_excel(students_file)
            for student_data in students:
                student = Student(
                    first_name=student_data['first_name'],
                    last_name=student_data['last_name'],
                    gender=student_data['gender'],
                    group_number=student_data['group_number'],
                    class_id=class_obj.id
                )
                db.add(student)
        except Exception as e:
            flash(request, f'Excel faylni o\'qishda xatolik: {str(e)}', 'danger')
    
    await db.commit()
    flash(request, 'Sinf va o\'quvchilar qo\'shildi', 'success')
    return RedirectResponse(url="/admin/classes", status_code=303)

@router.get("/classes/edit/{id}", response_class=HTMLResponse)
async def edit_class_page(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db)
):
    """Display edit class form"""
    result = await db.execute(select(SchoolClass).where(SchoolClass.id == id))
    class_obj = result.scalar_one_or_none()
    if not class_obj:
        flash(request, 'Sinf topilmadi', 'danger')
        return RedirectResponse(url="/admin/classes", status_code=303)
    
    schools_result = await db.execute(select(School))
    schools = schools_result.scalars().all()
    
    context = await get_template_context(request)
    context.update({'class_obj': class_obj, 'schools': schools})
    return templates.TemplateResponse('admin/class_form.html', context)  

@router.post("/classes/edit/{id}")
async def edit_class(
    request: Request,
    id: int,
    name: str = Form(...),
    school_id: int = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Update class"""
    result = await db.execute(select(SchoolClass).where(SchoolClass.id == id))
    class_obj = result.scalar_one_or_none()
    if not class_obj:
        flash(request, 'Sinf topilmadi', 'danger')
        return RedirectResponse(url="/admin/classes", status_code=303)
    
    class_obj.name = name
    class_obj.school_id = school_id
    await db.commit()
    flash(request, 'Sinf ma\'lumotlari yangilandi', 'success')
    return RedirectResponse(url="/admin/classes", status_code=303)

@router.post("/classes/delete/{id}")
async def delete_class(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete class and all related data"""
    result = await db.execute(select(SchoolClass).where(SchoolClass.id == id))
    class_obj = result.scalar_one_or_none()
    if not class_obj:
        flash(request, 'Sinf topilmadi', 'danger')
        return RedirectResponse(url="/admin/classes", status_code=303)
    
    try:
        # Delete exams and related data
        exams_result = await db.execute(select(Exam).where(Exam.class_id == id))
        exams_in_class = exams_result.scalars().all()
        
        for exam in exams_in_class:
            await db.execute(delete(Question).where(Question.exam_id == exam.id))
            await db.execute(delete(ExamResult).where(ExamResult.exam_id == exam.id))
            await db.delete(exam)
        
        # Delete students
        await db.execute(delete(Student).where(Student.class_id == id))
        
        await db.delete(class_obj)
        await db.commit()
        
        flash(request, 'Sinf va unga bog\'liq barcha ma\'lumotlar o\'chirildi', 'success')
    except Exception as e:
        await db.rollback()
        flash(request, f'Sinfni o\'chirishda xatolik: {str(e)}', 'danger')
    
    return RedirectResponse(url="/admin/classes", status_code=303)

# ============================================================================
# STUDENT MANAGEMENT
# ============================================================================

@router.get("/students", response_class=HTMLResponse)
async def students_list(
    request: Request,
    class_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List all students"""
    # Convert class_id to int if provided and not empty
    class_id_int = None
    if class_id and class_id.strip():
        try:
            class_id_int = int(class_id)
        except ValueError:
            pass
    
    if class_id_int:
        result = await db.execute(select(Student).where(Student.class_id == class_id_int))
        students = result.scalars().all()
        # Eagerly load the school relationship to avoid lazy loading in template
        class_result = await db.execute(
            select(SchoolClass)
            .options(selectinload(SchoolClass.school))
            .where(SchoolClass.id == class_id_int)
        )
        selected_class = class_result.scalar_one_or_none()
    else:
        result = await db.execute(select(Student).order_by(Student.created_at.desc()))
        students = result.scalars().all()
        selected_class = None
    
    # Eagerly load schools for all classes
    classes_result = await db.execute(
        select(SchoolClass).options(selectinload(SchoolClass.school))
    )
    classes = classes_result.scalars().all()
    
    context = await get_template_context(request)
    context.update({'students': students, 'classes': classes, 'selected_class': selected_class})
    return templates.TemplateResponse('admin/students.html', context)  

@router.get("/students/add", response_class=HTMLResponse)
async def add_student_page(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Display add student form"""
    classes_result = await db.execute(select(SchoolClass))
    classes = classes_result.scalars().all()
    
    context = await get_template_context(request)
    context.update({'student': None, 'classes': classes})
    return templates.TemplateResponse('admin/student_form.html', context)  

@router.post("/students/add")
async def add_student(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: int = Form(...),
    group_number: int = Form(...),
    class_id: int = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Create new student"""
    student = Student(
        first_name=first_name,
        last_name=last_name,
        gender=gender,
        group_number=group_number,
        class_id=class_id
    )
    db.add(student)
    await db.commit()
    flash(request, 'O\'quvchi qo\'shildi', 'success')
    return RedirectResponse(url=f"/admin/students?class_id={class_id}", status_code=303)

@router.get("/students/edit/{id}", response_class=HTMLResponse)
async def edit_student_page(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db)
):
    """Display edit student form"""
    result = await db.execute(select(Student).where(Student.id == id))
    student = result.scalar_one_or_none()
    if not student:
        flash(request, 'O\'quvchi topilmadi', 'danger')
        return RedirectResponse(url="/admin/students", status_code=303)
    
    classes_result = await db.execute(select(SchoolClass))
    classes = classes_result.scalars().all()
    
    context = await get_template_context(request)
    context.update({'student': student, 'classes': classes})
    return templates.TemplateResponse('admin/student_form.html', context)  

@router.post("/students/edit/{id}")
async def edit_student(
    request: Request,
    id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: int = Form(...),
    group_number: int = Form(...),
    class_id: int = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Update student"""
    result = await db.execute(select(Student).where(Student.id == id))
    student = result.scalar_one_or_none()
    if not student:
        flash(request, 'O\'quvchi topilmadi', 'danger')
        return RedirectResponse(url="/admin/students", status_code=303)
    
    student.first_name = first_name
    student.last_name = last_name
    student.gender = gender
    student.group_number = group_number
    student.class_id = class_id
    await db.commit()
    flash(request, 'O\'quvchi ma\'lumotlari yangilandi', 'success')
    return RedirectResponse(url=f"/admin/students?class_id={class_id}", status_code=303)

@router.post("/students/delete/{id}")
async def delete_student(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete student"""
    result = await db.execute(select(Student).where(Student.id == id))
    student = result.scalar_one_or_none()
    if not student:
        flash(request, 'O\'quvchi topilmadi', 'danger')
        return RedirectResponse(url="/admin/students", status_code=303)
    
    class_id = student.class_id
    
    try:
        await db.execute(delete(ExamResult).where(ExamResult.student_id == id))
        await db.delete(student)
        await db.commit()
        
        flash(request, 'O\'quvchi va uning natijalari o\'chirildi', 'success')
    except Exception as e:
        await db.rollback()
        flash(request, f'O\'quvchini o\'chirishda xatolik: {str(e)}', 'danger')
    
    return RedirectResponse(url=f"/admin/students?class_id={class_id}", status_code=303)

# ============================================================================
# REFERENCE TABLE MANAGEMENT (Subjects, Quarters, etc.)
# ============================================================================

@router.get("/subjects", response_class=HTMLResponse)
async def subjects_list(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """List all subjects"""
    result = await db.execute(select(Subject))
    subjects = result.scalars().all()

    from language import language_manager
    lang = request.session.get('language', 'uz')
    
    context = await get_template_context(request)
    context.update({
        'items': subjects,
        'title': language_manager.get('subjects', lang),
        'add_url': 'add_subject',
        'delete_url': 'delete_subject'
    })
    return templates.TemplateResponse('admin/simple_list.html', context)

@router.post("/subjects/add")
async def add_subject(
    request: Request,
    name: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Add new subject"""
    if name:
        subject = Subject(name=name)
        db.add(subject)
        await db.commit()
        flash(request, 'Fan qo\'shildi', 'success')
    return RedirectResponse(url="/admin/subjects", status_code=303)

@router.post("/subjects/delete/{id}")
async def delete_subject(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete subject"""
    result = await db.execute(select(Subject).where(Subject.id == id))
    subject = result.scalar_one_or_none()
    if not subject:
        flash(request, 'Fan topilmadi', 'danger')
        return RedirectResponse(url="/admin/subjects", status_code=303)
    
    # Check if subject is used in exams
    exam_result = await db.execute(select(Exam).where(Exam.subject_id == id).limit(1))
    exams_using_subject = exam_result.scalar_one_or_none()
    
    if exams_using_subject:
        flash(request, 'Bu fan hozirda imtihonlarda ishlatilmoqda. Avval shu fan bilan bog\'liq imtihonlarni o\'chiring.', 'danger')
        return RedirectResponse(url="/admin/subjects", status_code=303)
    
    try:
        await db.delete(subject)
        await db.commit()
        flash(request, 'Fan o\'chirildi', 'success')
    except Exception as e:
        await db.rollback()
        flash(request, f'Fanni o\'chirishda xatolik: {str(e)}', 'danger')
    
    return RedirectResponse(url="/admin/subjects", status_code=303)

@router.get("/quarters", response_class=HTMLResponse)
async def quarters_list(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """List all quarters"""
    result = await db.execute(select(Quarter).order_by(Quarter.order_num))
    quarters = result.scalars().all()
    
    context = await get_template_context(request)
    context['quarters'] = quarters
    return templates.TemplateResponse('admin/quarters.html', context) 

@router.post("/quarters/add")
async def add_quarter(
    request: Request,
    name: str = Form(...),
    order_num: int = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Add new quarter"""
    if name and order_num:
        quarter = Quarter(name=name, order_num=order_num)
        db.add(quarter)
        await db.commit()
        flash(request, 'Chorak qo\'shildi', 'success')
    return RedirectResponse(url="/admin/quarters", status_code=303)

@router.post("/quarters/delete/{id}")
async def delete_quarter(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete quarter"""
    result = await db.execute(select(Quarter).where(Quarter.id == id))
    quarter = result.scalar_one_or_none()
    if quarter:
        await db.delete(quarter)
        await db.commit()
        flash(request, 'Chorak o\'chirildi', 'success')
    return RedirectResponse(url="/admin/quarters", status_code=303)

@router.get("/exam-names", response_class=HTMLResponse)
async def exam_names_list(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """List all exam names"""
    result = await db.execute(select(ExamName))
    exam_names = result.scalars().all()

    from language import language_manager
    lang = request.session.get('language', 'uz')
    
    context = await get_template_context(request)
    context.update({
        'items': exam_names,
        'title': language_manager.get('exam_names', lang),
        'add_url': 'add_exam_name',
        'delete_url': 'delete_exam_name'
    })
    return templates.TemplateResponse('admin/simple_list.html', context)  

@router.post("/exam-names/add")
async def add_exam_name(
    request: Request,
    name: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Add new exam name"""
    if name:
        exam_name = ExamName(name=name)
        db.add(exam_name)
        await db.commit()
        flash(request, 'Imtihon nomi qo\'shildi', 'success')
    return RedirectResponse(url="/admin/exam-names", status_code=303)

@router.post("/exam-names/delete/{id}")
async def delete_exam_name(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete exam name"""
    result = await db.execute(select(ExamName).where(ExamName.id == id))
    exam_name = result.scalar_one_or_none()
    if exam_name:
        await db.delete(exam_name)
        await db.commit()
        flash(request, 'Imtihon nomi o\'chirildi', 'success')
    return RedirectResponse(url="/admin/exam-names", status_code=303)

@router.get("/exam-types", response_class=HTMLResponse)
async def exam_types_list(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """List all exam types"""
    result = await db.execute(select(ExamType))
    exam_types = result.scalars().all()

    from language import language_manager
    lang = request.session.get('language', 'uz')
    
    context = await get_template_context(request)
    context.update({
        'items': exam_types,
        'title': language_manager.get('exam_types', lang),
        'add_url': 'add_exam_type',
        'delete_url': 'delete_exam_type'
    })
    return templates.TemplateResponse('admin/simple_list.html', context) 

@router.post("/exam-types/add")
async def add_exam_type(
    request: Request,
    name: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Add new exam type"""
    if name:
        exam_type = ExamType(name=name)
        db.add(exam_type)
        await db.commit()
        flash(request, 'Imtihon turi qo\'shildi', 'success')
    return RedirectResponse(url="/admin/exam-types", status_code=303)

@router.post("/exam-types/delete/{id}")
async def delete_exam_type(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete exam type"""
    result = await db.execute(select(ExamType).where(ExamType.id == id))
    exam_type = result.scalar_one_or_none()
    if exam_type:
        await db.delete(exam_type)
        await db.commit()
        flash(request, 'Imtihon turi o\'chirildi', 'success')
    return RedirectResponse(url="/admin/exam-types", status_code=303)

@router.get("/question-types", response_class=HTMLResponse)
async def question_types_list(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """List all question types"""
    result = await db.execute(select(QuestionType))
    question_types = result.scalars().all()

    from language import language_manager
    lang = request.session.get('language', 'uz')
    
    context = await get_template_context(request)
    context.update({
        'items': question_types,
        'title': language_manager.get('question_types', lang),
        'add_url': 'add_question_type',
        'delete_url': 'delete_question_type'
    })
    return templates.TemplateResponse('admin/simple_list.html', context)

@router.post("/question-types/add")
async def add_question_type(
    request: Request,
    name: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Add new question type"""
    if name:
        question_type = QuestionType(name=name)
        db.add(question_type)
        await db.commit()
        flash(request, 'Savol turi qo\'shildi', 'success')
    return RedirectResponse(url="/admin/question-types", status_code=303)

@router.post("/question-types/delete/{id}")
async def delete_question_type(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete question type"""
    result = await db.execute(select(QuestionType).where(QuestionType.id == id))
    question_type = result.scalar_one_or_none()
    if question_type:
        await db.delete(question_type)
        await db.commit()
        flash(request, 'Savol turi o\'chirildi', 'success')
    return RedirectResponse(url="/admin/question-types", status_code=303)

@router.get("/staff-titles", response_class=HTMLResponse)
async def staff_titles_list(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """List all staff titles"""
    result = await db.execute(select(StaffTitle))
    staff_titles = result.scalars().all()

    from language import language_manager
    lang = request.session.get('language', 'uz')
    
    context = await get_template_context(request)
    context.update({
        'items': staff_titles,
        'title': language_manager.get('staff_titles', lang),
        'add_url': 'add_staff_title',
        'delete_url': 'delete_staff_title'
    })
    return templates.TemplateResponse('admin/simple_list.html', context) 

@router.post("/staff-titles/add")
async def add_staff_title(
    request: Request,
    name: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Add new staff title"""
    if name:
        staff_title = StaffTitle(title=name)
        db.add(staff_title)
        await db.commit()
        flash(request, 'Lavozim qo\'shildi', 'success')
    return RedirectResponse(url="/admin/staff-titles", status_code=303)

@router.post("/staff-titles/delete/{id}")
async def delete_staff_title(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete staff title"""
    result = await db.execute(select(StaffTitle).where(StaffTitle.id == id))
    staff_title = result.scalar_one_or_none()
    if staff_title:
        await db.delete(staff_title)
        await db.commit()
        flash(request, 'Lavozim o\'chirildi', 'success')
    return RedirectResponse(url="/admin/staff-titles", status_code=303)