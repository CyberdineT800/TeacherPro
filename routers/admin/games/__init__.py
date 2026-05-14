"""Admin games router package — one sub-module per game type."""
from fastapi import APIRouter
from . import quiz_race

router = APIRouter()
router.include_router(quiz_race.router)

__all__ = ['router']
