"""Game router package — student-facing join and play endpoints.

Sub-modules are organised per game type:
    quiz_race  — Quiz Race join/play routes (was: play.py)
"""
from fastapi import APIRouter
from . import quiz_race

router = APIRouter()
router.include_router(quiz_race.router)

__all__ = ['router']
