"""Teacher games router package — one sub-module per game type."""
from fastapi import APIRouter
from . import quiz_race, mini_games

router = APIRouter()
router.include_router(quiz_race.router)
router.include_router(mini_games.router)

__all__ = ['router']
