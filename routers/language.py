from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from config import RedirectResponse
from dependencies import require_login, get_template_context

router = APIRouter()

@router.post("/set-language/{lang_code}")
async def set_language(
    request: Request,
    lang_code: str
):
    """Set user language preference"""
    available_languages = ['uz', 'ru', 'en']
    
    if lang_code in available_languages:
        request.session['language'] = lang_code
    
    # Return JSON response for AJAX requests
    return JSONResponse({"status": "success", "language": lang_code})

@router.get("/set-language/{lang_code}")
async def set_language_get(
    request: Request,
    lang_code: str
):
    """Set user language preference (GET fallback)"""
    available_languages = ['uz', 'ru', 'en']
    
    if lang_code in available_languages:
        request.session['language'] = lang_code
    
    referer = request.headers.get('referer', '/')
    return RedirectResponse(url=referer, status_code=303)