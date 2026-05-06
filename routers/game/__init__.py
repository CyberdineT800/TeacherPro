"""Game router package — student-facing join and play endpoints."""
from fastapi import APIRouter
from . import play

router = APIRouter()
router.include_router(play.router)

__all__ = ['router']
