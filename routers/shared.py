"""Public shared-presentation endpoint — no authentication required.

Route: GET /s/{token}

Anyone with the URL can view the presentation in full interactive mode.
The teacher can revoke access at any time via POST /teacher/ai/{pid}/unshare,
which clears the share_token from the DB and invalidates the Redis cache.

Performance:
  - Redis hit  → zero DB queries, ~1 ms
  - Redis miss → one DB lookup by index (share_token is indexed + unique)
  - TTL: 10 min; cache is explicitly busted on unshare
"""
import json
import logging

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db, AIPresentation
from dependencies import get_template_context
from services.ai_shared import TEMPLATES, LANGUAGE_DISPLAY
from services.cache import cache_get_shared_presentation, cache_set_shared_presentation
from language import language_manager

log = logging.getLogger("shared")
router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/s/{token}", response_class=HTMLResponse)
async def shared_presentation(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Render a shared AI presentation — public, no login needed."""

    # 1. Cache hit — skip DB entirely
    cached = await cache_get_shared_presentation(token)
    if cached:
        data = cached['data']
        pres_meta = cached['meta']
        pres_lang = pres_meta.get('language', 'uz')
        tpl_key = pres_meta.get('template', 'cosmos')
        if tpl_key not in TEMPLATES:
            tpl_key = 'cosmos'

        context = await get_template_context(request)
        context.update({
            'presentation': _MetaProxy(pres_meta),
            'data': data,
            'language_display': LANGUAGE_DISPLAY,
            'allow_download': False,
            'template_info': TEMPLATES[tpl_key],
            'template_key': tpl_key,
            '_p': lambda key: language_manager.get(key, pres_lang),
            'is_shared': True,
            'share_url': None,
        })
        return templates.TemplateResponse('teacher/ai_view.html', context)

    # 2. Cache miss — hit the DB (indexed lookup)
    presentation = (await db.execute(
        select(AIPresentation).where(AIPresentation.share_token == token)
    )).scalar_one_or_none()

    if not presentation:
        raise HTTPException(404, detail="Bu havola mavjud emas yoki bekor qilingan.")

    data = json.loads(presentation.content)
    tpl_key = presentation.template if presentation.template in TEMPLATES else 'cosmos'
    pres_lang = presentation.language if presentation.language in ('uz', 'ru', 'en') else 'uz'

    # Populate cache for next requests
    pres_meta = {
        'id':           presentation.id,
        'topic':        presentation.topic,
        'subject_name': presentation.subject_name,
        'grade':        presentation.grade,
        'language':     presentation.language,
        'template':     presentation.template,
        'slides_count': presentation.slides_count,
        'teacher_id':   presentation.teacher_id,
        'share_token':  token,
    }
    await cache_set_shared_presentation(token, {'data': data, 'meta': pres_meta})

    context = await get_template_context(request)
    context.update({
        'presentation': presentation,
        'data': data,
        'language_display': LANGUAGE_DISPLAY,
        'allow_download': False,
        'template_info': TEMPLATES[tpl_key],
        'template_key': tpl_key,
        '_p': lambda key: language_manager.get(key, pres_lang),
        'is_shared': True,
        'share_url': None,
    })
    return templates.TemplateResponse('teacher/ai_view.html', context)


class _MetaProxy:
    """Lightweight stand-in for AIPresentation ORM when serving from cache.

    Only exposes the fields accessed by the ai_view.html template.
    """
    __slots__ = (
        'id', 'topic', 'subject_name', 'grade', 'language',
        'template', 'slides_count', 'teacher_id', 'share_token',
    )

    def __init__(self, d: dict):
        for k in self.__slots__:
            setattr(self, k, d.get(k))
