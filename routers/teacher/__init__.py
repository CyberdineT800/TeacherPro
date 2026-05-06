"""Teacher router package — combines all teacher sub-routers under /teacher prefix."""
from fastapi import APIRouter
from . import core, ai_presentation, ai_questions, games

router = APIRouter()
router.include_router(core.router)
router.include_router(ai_presentation.router)
router.include_router(ai_questions.router)
router.include_router(games.router)

__all__ = ['router']
