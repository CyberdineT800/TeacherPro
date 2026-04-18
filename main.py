from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
import os

from sqlalchemy import select
from models import (
    init_db, AsyncSessionLocal,
    Employee, Quarter, ExamName, ExamType, QuestionType, StaffTitle
)
from routers import auth, admin, teacher, language
from dependencies import get_flashed_messages


async def seed_defaults():
    async with AsyncSessionLocal() as db:
        # Admin user
        result = await db.execute(select(Employee).where(Employee.username == 'admin'))
        if not result.scalar_one_or_none():
            admin_user = Employee(
                username='admin', first_name='Admin', last_name='User', is_admin=True
            )
            admin_user.set_password('admin123')
            db.add(admin_user)

        # Quarters
        q_result = await db.execute(select(Quarter))
        if not q_result.scalars().first():
            for name, order in [('1-chorak', 1), ('2-chorak', 2), ('3-chorak', 3), ('4-chorak', 4)]:
                db.add(Quarter(name=name, order_num=order))

        # Exam names
        en_result = await db.execute(select(ExamName))
        if not en_result.scalars().first():
            for name in ['BSB-1', 'BSB-2', 'CHSB-1', 'CHSB-2', 'Loyiha ishi']:
                db.add(ExamName(name=name))

        # Exam types
        et_result = await db.execute(select(ExamType))
        if not et_result.scalars().first():
            for name in ['Amaliy', 'Nazariy', 'Oraliq', 'Yakuniy']:
                db.add(ExamType(name=name))

        # Question types
        qt_result = await db.execute(select(QuestionType))
        if not qt_result.scalars().first():
            for name in ["Test", "To'ldirish", "Qisqa javob", "Moslashtirish", "Masala", "Tahlil"]:
                db.add(QuestionType(name=name))

        # Staff titles
        st_result = await db.execute(select(StaffTitle))
        if not st_result.scalars().first():
            for title in ["O'qituvchi", "Maktab direktori", "O'quv ishlari bo'yicha direktor o'rinbosari"]:
                db.add(StaffTitle(title=title))

        await db.commit()
        print("Seed data OK — admin / admin123")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_defaults()
    print("Database ready")
    yield
    print("Application shutdown")

# Create FastAPI application
app = FastAPI(
    title="TeacherPro",
    description="School Grading Management System",
    version="2.0.0",
    lifespan=lifespan
)

# Add session middleware for authentication
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production')
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Add custom template context processor
@app.middleware("http")
async def add_template_context(request: Request, call_next):
    """Add common context to all templates"""
    # Create custom url_for for this request
    def url_for(name: str, **path_params):
        """Custom url_for to handle static files and Flask route names"""
        if name == 'static':
            filename = path_params.get('filename', '')
            return f"/static/{filename}"
        
        route_map = {
            'login': '/login', 'logout': '/logout', 'index': '/',
            'admin_dashboard': '/admin/dashboard',
            'schools_list': '/admin/schools', 'add_school': '/admin/schools/add',
            'employees_list': '/admin/employees', 'add_employee': '/admin/employees/add',
            'classes_list': '/admin/classes', 'add_class': '/admin/classes/add',
            'students_list': '/admin/students', 'add_student': '/admin/students/add',
            'subjects_list': '/admin/subjects', 'quarters_list': '/admin/quarters',
            'exam_names_list': '/admin/exam-names', 'exam_types_list': '/admin/exam-types',
            'question_types_list': '/admin/question-types', 'staff_titles_list': '/admin/staff-titles',
            'edit_school': '/admin/schools/edit/{id}', 'delete_school': '/admin/schools/delete/{id}',
            'edit_employee': '/admin/employees/edit/{id}', 'delete_employee': '/admin/employees/delete/{id}',
            'toggle_employee_status': '/admin/employees/toggle-status/{id}',
            'edit_class': '/admin/classes/edit/{id}', 'delete_class': '/admin/classes/delete/{id}',
            'edit_student': '/admin/students/edit/{id}', 'delete_student': '/admin/students/delete/{id}',
            # Reference table operations
            'add_subject': '/admin/subjects/add', 'delete_subject': '/admin/subjects/delete/{id}',
            'add_quarter': '/admin/quarters/add', 'delete_quarter': '/admin/quarters/delete/{id}',
            'add_exam_name': '/admin/exam-names/add', 'delete_exam_name': '/admin/exam-names/delete/{id}',
            'add_exam_type': '/admin/exam-types/add', 'delete_exam_type': '/admin/exam-types/delete/{id}',
            'add_question_type': '/admin/question-types/add', 'delete_question_type': '/admin/question-types/delete/{id}',
            'add_staff_title': '/admin/staff-titles/add', 'delete_staff_title': '/admin/staff-titles/delete/{id}',
            'teacher_dashboard': '/teacher/dashboard', 'create_exam': '/teacher/create-exam',
            'enter_scores': '/teacher/enter-scores/{exam_id}', 'view_results': '/teacher/results/{exam_id}',
            'download_results': '/teacher/download/{exam_id}/{format}',
            'manage_languages': '/admin/languages',
            'save_translation': '/admin/languages/save',
            'delete_translation': '/admin/languages/delete/{key}',
        }
        
        base_path = route_map.get(name, f'/{name}')
        for key, value in list(path_params.items()):
            placeholder = f'{{{key}}}'
            if placeholder in base_path:
                base_path = base_path.replace(placeholder, str(value))
                path_params.pop(key)
        
        if path_params:
            query_string = '&'.join(f"{k}={v}" for k, v in path_params.items())
            result = f"{base_path}?{query_string}"
        else:
            result = base_path
        
        return result
    
    # Store url_for in request state so templates can access it
    request.state.url_for_custom = url_for
    response = await call_next(request)
    return response

# Include routers
app.include_router(auth.router, tags=["Authentication"])
app.include_router(admin.router, tags=["Admin"])
app.include_router(teacher.router, tags=["Teacher"])
app.include_router(language.router, tags=["Language"])

# Root redirect (handled by auth router)
# Additional routes can be added here if needed

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
