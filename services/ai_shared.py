"""Shared constants and helpers for AI presentation / question routes.

Imported by:
  routers/admin/ai.py
  routers/teacher/ai_presentation.py
  routers/teacher/ai_questions.py
  routers/admin/announcements.py  (translate only)

Centralising here eliminates the duplicate _t(), _reset_if_new_day(),
TEMPLATES, LANGUAGE_DISPLAY and TYPE_DISPLAY definitions that previously
existed in each file.
"""
from datetime import date
from fastapi import Request
from language import language_manager


# ── UI translation helper ─────────────────────────────────────────────────────

def translate(request: Request, key: str) -> str:
    """Return the translation for *key* using the session language.

    Shorthand used inside route handlers (not templates — templates use the
    ``_`` lambda injected by get_template_context).
    """
    lang = request.session.get('language', 'uz')
    return language_manager.get(key, lang)


# ── Daily AI usage reset ──────────────────────────────────────────────────────

def reset_if_new_day(teacher) -> None:
    """Reset both AI counters when the calendar day has rolled over.

    Resets ai_used_today (presentations) AND ai_questions_used_today so that
    both limits are always in sync with the same reset date.
    """
    today = date.today()
    if teacher.ai_last_reset != today:
        teacher.ai_used_today = 0
        teacher.ai_questions_used_today = 0
        teacher.ai_last_reset = today


# ── Presentation templates ────────────────────────────────────────────────────

TEMPLATES: dict = {
    'cosmos': {
        'label': 'Cosmos',
        'stage_bg': 'linear-gradient(135deg, #182448, #0a0e1c)',
        'accent': '#64c8ff',
        'pptx': {
            'title':    (0x1a, 0x4d, 0x9e),
            'subtitle': (0x55, 0x66, 0x77),
            'muted':    (0x88, 0x88, 0x88),
            'correct':  (0x1d, 0x9b, 0x4f),
            'wrong':    (0xc0, 0x39, 0x2b),
            'body':     (0x33, 0x33, 0x33),
        },
    },
    'ocean': {
        'label': 'Ocean',
        'stage_bg': 'linear-gradient(135deg, #0d2b3e, #071a2c)',
        'accent': '#00d4aa',
        'pptx': {
            'title':    (0x0d, 0x5c, 0x6e),
            'subtitle': (0x3d, 0x7a, 0x8a),
            'muted':    (0x70, 0x90, 0x95),
            'correct':  (0x00, 0xb8, 0x8a),
            'wrong':    (0xc0, 0x39, 0x2b),
            'body':     (0x1a, 0x3a, 0x40),
        },
    },
    'aurora': {
        'label': 'Aurora',
        'stage_bg': 'linear-gradient(135deg, #1e1244, #0d0a2e)',
        'accent': '#b478ff',
        'pptx': {
            'title':    (0x5a, 0x1e, 0x9e),
            'subtitle': (0x7a, 0x5a, 0xaa),
            'muted':    (0x88, 0x70, 0xa0),
            'correct':  (0x1d, 0x9b, 0x4f),
            'wrong':    (0xc0, 0x39, 0x2b),
            'body':     (0x2a, 0x1a, 0x44),
        },
    },
}

# ── Display label maps ────────────────────────────────────────────────────────

LANGUAGE_DISPLAY: dict = {
    'uz': "O'zbekcha",
    'ru': 'Русский',
    'en': 'English',
}

TYPE_DISPLAY: dict = {
    'test': 'Test (MCQ)',
    'open': 'Ochiq savollar',
}
