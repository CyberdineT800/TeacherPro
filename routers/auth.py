from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from models import get_db, Employee
from dependencies import flash, get_template_context

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Redirect to appropriate dashboard or login"""
    if 'user_id' in request.session:
        if request.session.get('is_admin'):
            return RedirectResponse(url="/admin/dashboard", status_code=303)
        return RedirectResponse(url="/teacher/dashboard", status_code=303)
    return RedirectResponse(url="/login", status_code=303)

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Display login page"""
    context = await get_template_context(request)
    return templates.TemplateResponse("login.html", context)

@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Process login form"""
    result = await db.execute(select(Employee).where(Employee.username == username))
    employee = result.scalar_one_or_none()
    
    if employee and employee.check_password(password):
        if not employee.is_active:
            flash(request, "Hisobingiz bloklangan. Administrator bilan bog'laning.", 'danger')
            return RedirectResponse(url="/login", status_code=303)
        
        # Set session data
        request.session['user_id'] = employee.id
        request.session['is_admin'] = employee.is_admin
        request.session['username'] = employee.username
        request.session['full_name'] = f"{employee.first_name} {employee.last_name}"
        
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
    request.session.clear()
    flash(request, 'Tizimdan muvaffaqiyatli chiqdingiz', 'success')
    return RedirectResponse(url="/login", status_code=303)
