from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
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
    
    context = await get_template_context(request)
    context.update({
        'items': staff_titles,
        'title': 'Xodim lavozim nomlari',
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