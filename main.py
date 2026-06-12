from contextlib import asynccontextmanager
import logging
import os

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

log = logging.getLogger("main")

from sqlalchemy import select
from models import (
    init_db, AsyncSessionLocal,
    Employee, Quarter, ExamName, ExamType, QuestionType, StaffTitle
)
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from rate_limit import limiter

from services.cache import init_redis, close_redis

from routers import auth, language
from routers.shared import router as shared_router
from routers.home import router as home_router
from routers.admin import router as admin_router
from routers.teacher import router as teacher_router
from routers.game import router as game_router
from dependencies import get_flashed_messages
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates as _Jinja2Templates
_err_templates = _Jinja2Templates(directory="templates")



async def seed_defaults():
    async with AsyncSessionLocal() as db:
        # Admin user
        result = await db.execute(select(Employee).where(Employee.username == 'SysAdmin'))
        if not result.scalar_one_or_none():
            admin_user = Employee(
                username='SysAdmin', first_name='Admin', last_name='User', is_admin=True
            )
            admin_user.set_password('Admin224236')
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
            for name in ["Test", "Bilish", "Qo'llash", "Mulohaza"]:
                db.add(QuestionType(name=name))

        # Staff titles
        st_result = await db.execute(select(StaffTitle))
        if not st_result.scalars().first():
            for title in ["O'qituvchi", "Maktab direktori", "O'quv ishlari bo'yicha direktor o'rinbosari"]:
                db.add(StaffTitle(title=title))

        await db.commit()
        print("Seed data OK — SysAdmin / Admin224236")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_defaults()
    print("Database ready")
    await init_redis()
    print("Redis ready")
    yield
    await close_redis()
    print("Application shutdown")


# ROOT_PATH lets url_for() generate correct links when behind an /prefix/ nginx proxy
ROOT_PATH = os.environ.get('ROOT_PATH', '')

app = FastAPI(
    title="TeacherPro",
    description="School Grading Management System",
    version="2.0.0",
    root_path=ROOT_PATH,
    lifespan=lifespan
)

# Attach rate limiter state and exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/health")
async def health():
    return {"status": "ok"}

SECRET_KEY = os.environ.get('SECRET_KEY', '')
if not SECRET_KEY:
    log.warning(
        "SECRET_KEY environment variable is not set! "
        "Using an insecure default. Set SECRET_KEY in your .env file for production."
    )
    SECRET_KEY = 'dev-insecure-key-please-set-SECRET_KEY-env-var'

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    https_only=True,   # Secure flag — cookie never sent over plain HTTP
    same_site="lax",   # CSRF protection: blocks cross-site POST/PUT/DELETE
    max_age=86400,     # 24-hour session lifetime
)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


@app.middleware("http")
async def add_template_context(request: Request, call_next):
    """Inject a custom url_for into every request so templates resolve named routes."""
    def url_for(name: str, **path_params):
        """Custom url_for — respects ROOT_PATH so links work behind an nginx prefix."""
        if name == 'static':
            filename = path_params.get('filename', '')
            return f"{ROOT_PATH}/static/{filename}"

        route_map = {
            # ── Auth ────────────────────────────────────────────────────────
            'login': '/login', 'logout': '/logout', 'index': '/',

            # ── Admin: core ─────────────────────────────────────────────────
            'admin_dashboard': '/admin/dashboard',
            'schools_list': '/admin/schools',        'add_school': '/admin/schools/add',
            'edit_school': '/admin/schools/edit/{id}',
            'delete_school': '/admin/schools/delete/{id}',
            'employees_list': '/admin/employees',    'add_employee': '/admin/employees/add',
            'edit_employee': '/admin/employees/edit/{id}',
            'delete_employee': '/admin/employees/delete/{id}',
            'toggle_employee_status': '/admin/employees/toggle-status/{id}',
            'classes_list': '/admin/classes',        'add_class': '/admin/classes/add',
            'edit_class': '/admin/classes/edit/{id}',
            'delete_class': '/admin/classes/delete/{id}',
            'students_list': '/admin/students',      'add_student': '/admin/students/add',
            'edit_student': '/admin/students/edit/{id}',
            'delete_student': '/admin/students/delete/{id}',

            # ── Admin: settings ─────────────────────────────────────────────
            'subjects_list': '/admin/subjects',
            'add_subject': '/admin/subjects/add',    'delete_subject': '/admin/subjects/delete/{id}',
            'quarters_list': '/admin/quarters',
            'add_quarter': '/admin/quarters/add',    'delete_quarter': '/admin/quarters/delete/{id}',
            'exam_names_list': '/admin/exam-names',
            'add_exam_name': '/admin/exam-names/add',
            'delete_exam_name': '/admin/exam-names/delete/{id}',
            'exam_types_list': '/admin/exam-types',
            'add_exam_type': '/admin/exam-types/add',
            'delete_exam_type': '/admin/exam-types/delete/{id}',
            'question_types_list': '/admin/question-types',
            'add_question_type': '/admin/question-types/add',
            'delete_question_type': '/admin/question-types/delete/{id}',
            'staff_titles_list': '/admin/staff-titles',
            'add_staff_title': '/admin/staff-titles/add',
            'delete_staff_title': '/admin/staff-titles/delete/{id}',
            'manage_languages': '/admin/languages',
            'save_translation': '/admin/languages/save',
            'delete_translation': '/admin/languages/delete/{key}',

            # ── Admin: AI ───────────────────────────────────────────────────
            'admin_ai_list': '/admin/ai',
            'admin_ai_settings': '/admin/ai/settings',
            'admin_ai_questions': '/admin/ai-questions',

            # ── Admin: Quiz Race ─────────────────────────────────────────────
            'admin_quiz_race_settings': '/admin/games/quiz-race/settings',
            'admin_quiz_race_list': '/admin/games/quiz-race',
            'admin_quiz_race_session_results': '/admin/games/quiz-race/{sid}/results',

            # ── Teacher: core ───────────────────────────────────────────────
            'teacher_dashboard': '/teacher/dashboard',
            'create_exam': '/teacher/create-exam',
            'enter_scores': '/teacher/enter-scores/{exam_id}',
            'view_results': '/teacher/results/{exam_id}',
            'download_results': '/teacher/download/{exam_id}/{format}',

            # ── Teacher: AI ─────────────────────────────────────────────────
            'teacher_ai_list': '/teacher/ai',
            'teacher_ai_create': '/teacher/ai/create',
            'teacher_ai_questions_list': '/teacher/ai-questions',
            'teacher_ai_questions_create': '/teacher/ai-questions/create',

            # ── Teacher: games hub (game-agnostic) ──────────────────────────
            'teacher_games_hub': '/teacher/games',
            'teacher_mini_game_play': '/teacher/games/mini/{game_id}',

            # ── Teacher: tools hub ───────────────────────────────────────────
            'teacher_tools_hub':      '/teacher/tools',
            'tools_script_converter': '/teacher/tools/script-converter',
            'tools_word_counter':     '/teacher/tools/word-counter',
            'tools_pdf_merge':        '/teacher/tools/pdf-merge',
            'tools_image_to_pdf':     '/teacher/tools/image-to-pdf',
            'tools_qr':               '/teacher/tools/qr',

            # ── Teacher: Quiz Race ───────────────────────────────────────────
            'teacher_quiz_race_sessions': '/teacher/games/quiz-race/sessions',
            'teacher_quiz_race_create': '/teacher/games/quiz-race/create',
            'teacher_quiz_race_lobby': '/teacher/games/quiz-race/{sid}/lobby',
            'teacher_quiz_race_results': '/teacher/games/quiz-race/{sid}/results',

            # ── Public: Quiz Race (students) ─────────────────────────────────
            'quiz_race_join_landing': '/play/quiz-race',
            'quiz_race_join_game': '/play/quiz-race/{code}',

            # ── Public: Mini-Games ───────────────────────────────────────────
            'public_games_hub': '/games',
            'public_mini_game_play': '/games/{game_id}',

            # ── Public: Home & Announcements ─────────────────────────────────
            'home': '/',
            'admin_announcements': '/admin/announcements',
        }

        base_path = route_map.get(name, f'/{name}')
        for key, value in list(path_params.items()):
            placeholder = f'{{{key}}}'
            if placeholder in base_path:
                base_path = base_path.replace(placeholder, str(value))
                path_params.pop(key)

        if path_params:
            query_string = '&'.join(f"{k}={v}" for k, v in path_params.items())
            result = f"{ROOT_PATH}{base_path}?{query_string}"
        else:
            result = f"{ROOT_PATH}{base_path}"

        return result

    request.state.url_for_custom = url_for
    response = await call_next(request)
    return response


# ── 404 handler ──────────────────────────────────────────────────────────────
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    context = {"request": request, "root_path": ROOT_PATH}
    return _err_templates.TemplateResponse("404.html", context, status_code=404)

# Include routers
app.include_router(shared_router, tags=["Shared"])
app.include_router(home_router, tags=["Home"])
app.include_router(auth.router, tags=["Authentication"])
app.include_router(admin_router, tags=["Admin"])
app.include_router(teacher_router, tags=["Teacher"])
app.include_router(game_router, tags=["Game"])
app.include_router(language.router, tags=["Language"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
