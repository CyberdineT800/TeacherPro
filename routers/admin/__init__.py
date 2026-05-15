"""Admin router package — combines all admin sub-routers under /admin prefix."""
from fastapi import APIRouter
from . import schools, employees, classes, students, settings, ai, games, announcements

router = APIRouter()
router.include_router(schools.router)
router.include_router(employees.router)
router.include_router(classes.router)
router.include_router(students.router)
router.include_router(settings.router)
router.include_router(ai.router)
router.include_router(games.router)
router.include_router(announcements.router)

__all__ = ['router']
