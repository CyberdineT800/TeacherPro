from fastapi import APIRouter, Request, Depends, Form
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse
from config import RedirectResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from models import get_db, Employee
from dependencies import flash, get_template_context
from services.cache import cache_del_user

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Display login page"""
    context = await get_template_context(request)
    return templates.TemplateResponse("login.html", context)

@router.post("/login")
@limiter.limit("15/minute")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Process login form"""
    result = await db.execute(select(Employee).where(Employee.username == username))
    employee = result.scalar_one_or_none()

    password_valid = employee and await run_in_threadpool(employee.check_password, password)
    if password_valid:
        if not employee.is_active:
            flash(request, "Hisobingiz bloklangan. Administrator bilan bog'laning.", 'danger')
            return RedirectResponse(url="/login", status_code=303)
        
        # Set session data
        request.session['user_id'] = employee.id
        request.session['is_admin'] = employee.is_admin
        request.session['is_super_admin'] = bool(employee.is_super_admin)
        request.session['school_id'] = employee.school_id
        request.session['username'] = employee.username
        request.session['full_name'] = f"{employee.first_name} {employee.last_name}"
        request.session['ai_enabled'] = bool(employee.ai_enabled)
        request.session['games_enabled'] = bool(employee.games_enabled)
        
        # Update last login time
        employee.updated_at = datetime.utcnow()
        await db.commit()
        
        if employee.is_admin:
            return RedirectResponse(url="/admin/dashboard", status_code=303)
        return RedirectResponse(url="/teacher/dashboard", status_code=303)
    
    flash(request, "Noto'g'ri login yoki parol", 'danger')
    return RedirectResponse(url="/login", status_code=303)

@router.get("/logout")
async def logout(request: Request):
    """Logout user"""
    user_id = request.session.get('user_id')
    if user_id:
        await cache_del_user(user_id)
    request.session.clear()
    flash(request, 'Tizimdan muvaffaqiyatli chiqdingiz', 'success')
    return RedirectResponse(url="/", status_code=303)
