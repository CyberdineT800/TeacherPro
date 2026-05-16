"""Redis cache layer for TeacherPro.

Single module that owns the Redis connection lifecycle, JSON serialization,
and all named-cache operations.  Callers stay thin: import helpers, call them.

Key namespaces
──────────────
  user:{id}            Employee row          TTL  5 min
  gs:{CODE}            GameSession by code   TTL 24 h
  gqs:{session_id}     sorted GameQuestions  TTL 24 h (immutable)
  t_sessions:{tid}     teacher session list  TTL  2 min
  ref:{name}           reference tables      TTL 24 h

All helpers fail silently when Redis is unavailable (returns None / does nothing)
so the app degrades gracefully without Redis.
"""
import json
import logging
import types
from typing import Optional, Any

import redis.asyncio as aioredis

log = logging.getLogger("cache")

# ── connection ─────────────────────────────────────────────────────────────────

_redis: Optional[aioredis.Redis] = None

REDIS_URL = "redis://127.0.0.1:6379/0"


async def init_redis(url: str = REDIS_URL) -> None:
    global _redis
    try:
        _redis = aioredis.from_url(url, encoding="utf-8", decode_responses=True)
        await _redis.ping()
        log.info("Redis connected: %s", url)
    except Exception as e:
        log.warning("Redis unavailable (%s) — caching disabled", e)
        _redis = None


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
        log.info("Redis connection closed")


def get_redis() -> Optional[aioredis.Redis]:
    return _redis


# ── TTL constants ──────────────────────────────────────────────────────────────

TTL_USER         = 300        # 5 min
TTL_GAME_SESSION = 86_400     # 24 h
TTL_GAME_QS      = 86_400     # 24 h
TTL_T_SESSIONS   = 120        # 2 min
TTL_REF          = 86_400     # 24 h


# ── low-level primitives ───────────────────────────────────────────────────────

async def cache_get(key: str) -> Optional[Any]:
    if not _redis:
        return None
    try:
        raw = await _redis.get(key)
        return json.loads(raw) if raw else None
    except Exception as e:
        log.debug("cache_get %s: %s", key, e)
        return None


async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    if not _redis:
        return
    try:
        await _redis.setex(key, ttl, json.dumps(value, default=str))
    except Exception as e:
        log.debug("cache_set %s: %s", key, e)


async def cache_delete(*keys: str) -> None:
    if not _redis or not keys:
        return
    try:
        await _redis.delete(*keys)
    except Exception as e:
        log.debug("cache_delete %s: %s", keys, e)


# ── Employee / User ────────────────────────────────────────────────────────────

def _emp_to_dict(emp) -> dict:
    """Serialize only the fields we need from the Employee ORM object."""
    return {
        'id':                        emp.id,
        'username':                  emp.username,
        'first_name':                emp.first_name,
        'last_name':                 emp.last_name,
        'email':                     getattr(emp, 'email', None),
        'is_admin':                  bool(emp.is_admin),
        'is_active':                 bool(emp.is_active),
        'school_id':                 emp.school_id,
        'staff_title_id':            emp.staff_title_id,
        'ai_enabled':                bool(emp.ai_enabled),
        'ai_daily_limit':            emp.ai_daily_limit,
        'ai_used_today':             emp.ai_used_today,
        'ai_questions_daily_limit':  emp.ai_questions_daily_limit,
        'ai_questions_used_today':   emp.ai_questions_used_today,
        'ai_last_reset':             str(emp.ai_last_reset) if emp.ai_last_reset else None,
        'games_enabled':             bool(emp.games_enabled),
    }


def _dict_to_emp(d: dict) -> types.SimpleNamespace:
    """Reconstruct a SimpleNamespace that quacks like an Employee object."""
    return types.SimpleNamespace(**d)


async def cache_set_user(emp) -> None:
    await cache_set(f"user:{emp.id}", _emp_to_dict(emp), TTL_USER)


async def cache_get_user(user_id: int) -> Optional[types.SimpleNamespace]:
    d = await cache_get(f"user:{user_id}")
    return _dict_to_emp(d) if d else None


async def cache_del_user(user_id: int) -> None:
    await cache_delete(f"user:{user_id}")


# ── GameSession by code ────────────────────────────────────────────────────────

def _gs_to_dict(gs) -> dict:
    return {
        'id':               gs.id,
        'code':             gs.code,
        'teacher_id':       gs.teacher_id,
        'title':            gs.title,
        'subject_name':     gs.subject_name,
        'grade':            gs.grade,
        'time_per_question': gs.time_per_question,
        'status':           gs.status,
    }


def _dict_to_gs(d: dict) -> types.SimpleNamespace:
    return types.SimpleNamespace(**d)


async def cache_set_game_session(gs) -> None:
    await cache_set(f"gs:{gs.code.upper()}", _gs_to_dict(gs), TTL_GAME_SESSION)


async def cache_get_game_session(code: str) -> Optional[types.SimpleNamespace]:
    d = await cache_get(f"gs:{code.upper()}")
    return _dict_to_gs(d) if d else None


async def cache_del_game_session(code: str) -> None:
    await cache_delete(f"gs:{code.upper()}")


async def cache_update_gs_status(code: str, status: str) -> None:
    """Patch only the status field without changing TTL."""
    if not _redis:
        return
    try:
        key = f"gs:{code.upper()}"
        raw = await _redis.get(key)
        if raw:
            data = json.loads(raw)
            data['status'] = status
            ttl = await _redis.ttl(key)
            if ttl > 0:
                await _redis.setex(key, ttl, json.dumps(data))
    except Exception as e:
        log.debug("cache_update_gs_status %s: %s", code, e)


# ── Game Questions (sorted, immutable after creation) ─────────────────────────

def _questions_to_list(qs_orm) -> list:
    """Convert sorted ORM question objects → list[dict]."""
    return [
        {
            'question_text': q.question_text,
            'option_a':      q.option_a,
            'option_b':      q.option_b,
            'option_c':      q.option_c,
            'option_d':      q.option_d,
            'correct_option': q.correct_option,
            'points':        q.points,
        }
        for q in sorted(qs_orm, key=lambda x: x.order)
    ]


async def cache_set_game_questions(session_id: int, qs_orm) -> list:
    """Serialize + cache questions; returns the serialized list for reuse."""
    questions = _questions_to_list(qs_orm)
    await cache_set(f"gqs:{session_id}", questions, TTL_GAME_QS)
    return questions


async def cache_get_game_questions(session_id: int) -> Optional[list]:
    return await cache_get(f"gqs:{session_id}")


async def cache_del_game_questions(session_id: int) -> None:
    await cache_delete(f"gqs:{session_id}")


# ── Teacher sessions list ──────────────────────────────────────────────────────

async def cache_set_teacher_sessions(teacher_id: int, data: list) -> None:
    await cache_set(f"t_sessions:{teacher_id}", data, TTL_T_SESSIONS)


async def cache_get_teacher_sessions(teacher_id: int) -> Optional[list]:
    return await cache_get(f"t_sessions:{teacher_id}")


async def cache_del_teacher_sessions(teacher_id: int) -> None:
    await cache_delete(f"t_sessions:{teacher_id}")


# ── Reference tables (Quarter, ExamType, QuestionType, ExamName) ──────────────

async def cache_set_ref(name: str, rows: list) -> None:
    await cache_set(f"ref:{name}", rows, TTL_REF)


async def cache_get_ref(name: str) -> Optional[list]:
    return await cache_get(f"ref:{name}")


async def cache_del_all_ref() -> None:
    """Call when admin edits reference tables."""
    await cache_delete("ref:quarters", "ref:question_types",
                       "ref:exam_types", "ref:exam_names", "ref:staff_titles")


# ── Home page (public landing) ────────────────────────────────────────────────

TTL_HOME_STATS        = 600   # 10 min — school/teacher/student counts rarely change
TTL_HOME_ANNOUNCEMENTS = 300  # 5 min — TTL safety net; invalidated explicitly on admin edit


async def cache_get_home_stats() -> Optional[dict]:
    return await cache_get("home:stats")


async def cache_set_home_stats(stats: dict) -> None:
    await cache_set("home:stats", stats, TTL_HOME_STATS)


async def cache_del_home_stats() -> None:
    await cache_delete("home:stats")


async def cache_get_home_announcements() -> Optional[list]:
    return await cache_get("home:announcements")


async def cache_set_home_announcements(announcements: list) -> None:
    await cache_set("home:announcements", announcements, TTL_HOME_ANNOUNCEMENTS)


async def cache_del_home_announcements() -> None:
    await cache_delete("home:announcements")


# ── Admin dashboard stats ─────────────────────────────────────────────────────
# Short TTL: counts change when employees/schools/classes/students are added.
# Explicit invalidation is complex (many routes), so we accept 60 s of stale.

TTL_ADMIN_STATS = 60   # 1 min


async def cache_get_admin_stats() -> Optional[dict]:
    return await cache_get("admin:stats")


async def cache_set_admin_stats(stats: dict) -> None:
    await cache_set("admin:stats", stats, TTL_ADMIN_STATS)


async def cache_del_admin_stats() -> None:
    """Call after any admin action that changes entity counts."""
    await cache_delete("admin:stats")

# ── Shared presentation (public, no-auth links) ───────────────────────────────
# Cached for 10 min; explicitly invalidated when teacher unshares.
# Stores full presentation JSON so /s/{token} never hits the DB on cache hit.

TTL_SHARED_PRESENTATION = 600   # 10 min


async def cache_get_shared_presentation(token: str) -> Optional[dict]:
    return await cache_get(f"shared_pres:{token}")


async def cache_set_shared_presentation(token: str, data: dict) -> None:
    await cache_set(f"shared_pres:{token}", data, TTL_SHARED_PRESENTATION)


async def cache_del_shared_presentation(token: str) -> None:
    await cache_delete(f"shared_pres:{token}")
