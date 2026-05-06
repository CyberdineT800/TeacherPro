# Router package initialization
from . import auth, language
from .admin import router as admin_router
from .teacher import router as teacher_router
from .game import router as game_router

__all__ = ['auth', 'language', 'admin_router', 'teacher_router', 'game_router']
