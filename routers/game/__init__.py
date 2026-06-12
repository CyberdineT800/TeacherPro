"""Game router package — student-facing join and play endpoints.

Sub-modules are organised per game type:
    quiz_race   — Quiz Race join/play routes (was: play.py)
    mini_games  — Public static mini-game hub and player (no login required)
"""
from fastapi import APIRouter
from . import quiz_race, mini_games

router = APIRouter()
router.include_router(quiz_race.router)
router.include_router(mini_games.router)

__all__ = ['router']
