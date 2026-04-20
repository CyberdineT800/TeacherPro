from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from models import get_db, Employee
from sqlalchemy import select
from language import language_manager

def get_flashed_messages(request: Request, with_categories: bool = False):
    """Get flash messages from session (compatible with Flask)"""
    messages = request.session.pop('_flashes', [])
    if with_categories:
        return [(msg.get('category', 'info'), msg.get('message', '')) for msg in messages]
    else:
        return [msg.get('message', '') if isinstance(msg, dict) else msg for msg in messages]

def flash(request: Request, message: str, category: str = 'info'):
    """Add a flash message to the session"""
    if '_flashes' not in request.session:
        request.session['_flashes'] = []
    request.session['_flashes'].append({'message': message, 'category': category})

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[Employee]:
    """Get the current logged-in user from session"""
    user_id = request.session.get('user_id')
    if not user_id:
        return None
    
    result = await db.execute(select(Employee).where(Employee.id == user_id))
    user = result.scalar_one_or_none()
    return user

async def require_login(
    request: Request,
    current_user: Optional[Employee] = Depends(get_current_user)
) -> Employee:
    """Require user to be logged in"""
    if not current_user:
        flash(request, 'Iltimos, tizimga kiring', 'warning')
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"}
        )
    return current_user

async def require_admin(
    request: Request,
    current_user: Employee = Depends(require_login)
) -> Employee:
    """Require user to be admin"""
    if not current_user.is_admin:
        flash(request, 'Admin huquqi talab qilinadi', 'danger')
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"}
        )
    return current_user

async def get_current_language(request: Request) -> str:
    """Get current language from session"""
    return request.session.get('language', 'uz')

async def get_template_context(request: Request, db: AsyncSession = None) -> Dict[str, Any]:
    """Get template context with language support and all necessary utilities"""
    # Setup url_for function
    url_for = getattr(request.state, 'url_for_custom', None)
    if not url_for:
        def url_for(name: str, **params):
            return f"/{name}"
    
    # Setup request args wrapper for query params
    class RequestArgsWrapper:
        def __init__(self, query_params):
            self._params = query_params
        
        def get(self, key, default=None):
            return self._params.get(key, default)
        
        def __getitem__(self, key):
            return self._params[key]
        
        def __contains__(self, key):
            return key in self._params
    
    if not hasattr(request, 'args'):
        request.args = RequestArgsWrapper(request.query_params)
    
    # Get language settings
    lang_code = request.session.get('language', 'uz')
    
    # Build context
    context = {
        'request': request,
        'session': request.session,
        'get_flashed_messages': lambda with_categories=False: get_flashed_messages(request, with_categories),
        'url_for': url_for,
        'current_language': lang_code,
        'languages': language_manager.get_available_languages(),
        '_': lambda key: language_manager.get(key, lang_code)
    }
    
    # Add user if available
    user_id = request.session.get('user_id')
    if user_id and db:
        result = await db.execute(select(Employee).where(Employee.id == user_id))
        employee = result.scalar_one_or_none()
        if employee:
            context['user'] = employee
            request.session['ai_enabled'] = bool(employee.ai_enabled)

    return context
