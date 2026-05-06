# TeacherPro — Performance Evaluation

*Evaluated: May 2026*

---

## 1. Database & Connection Pool

**Pool configuration** is solid. `pool_size=10, max_overflow=20, pool_pre_ping=True, pool_recycle=1800` is a well-chosen baseline for a school-scale app. `pool_pre_ping` prevents stale connection errors on long idle periods. `expire_on_commit=False` on the session factory is correct for async SQLAlchemy — it prevents accidental lazy-load attempts after a session closes.

**Missing index on `GameSession.status`.** Every query that filters active games (`WHERE status != 'finished'`) does a full table scan. Add it:

```python
Index('ix_game_sessions_status', GameSession.status)
```

All other indexes are well-placed: composite `(teacher_id, created_at)` on GameSession, `(session_id, order)` on GameQuestion, `(exam_id, student_id)` on ExamResult, etc.

**No proper migration system.** The `ADD COLUMN IF NOT EXISTS` approach in `init_db()` works in development but is fragile in production — it won't rename columns, change types, or drop old ones. The project should adopt **Alembic** for proper schema versioning. This is the single biggest operational risk.

---

## 2. N+1 Query Risk

This is the most common silent performance killer in SQLAlchemy apps.

Accessing `exam.questions`, `exam.results`, `gs.questions`, `employee.assigned_classes`, `employee.assigned_subjects` after the session closes will either raise a `MissingGreenlet` error (async) or fire individual SELECT queries per row (N+1). The relationships are defined with lazy loading (the SQLAlchemy default).

Any route that loads a list of exams and then accesses `.questions` on each one is doing N+1 queries. The fix is to use `selectinload` or `joinedload` at query time:

```python
from sqlalchemy.orm import selectinload

stmt = (
    select(Exam)
    .where(Exam.teacher_id == teacher_id)
    .options(selectinload(Exam.questions), selectinload(Exam.results))
    .order_by(Exam.created_at.desc())
)
```

The game routes that access `gs.questions` inline need the same treatment. Without this, a teacher with 50 exams triggers 51+ queries per dashboard load.

---

## 3. WebSocket & Game Engine

**The in-memory `_rooms` dict works correctly for a single-process server.** The asyncio event loop is single-threaded, so there are no race conditions. The `_safe_send` wrapper properly handles dead connections.

**Critical multi-worker issue.** If the app is ever started with multiple Uvicorn/Gunicorn workers (`--workers 4`), each worker has its own separate `_rooms` dict. A teacher on worker 1 creates a room; a student connecting to worker 2 finds nothing. The game breaks completely. Right now the `__main__` block starts a single worker, so this is safe — but it must be documented and enforced. If horizontal scaling is ever needed, game room state must move to Redis (via `redis-py` async).

**Sequential broadcast.** `broadcast_to_students` sends messages to each player one at a time with `await`. For a class of 30 students this adds ~30× the latency of a single send. Replace with:

```python
await asyncio.gather(
    *[_safe_send(p.ws, message) for p in room.players.values() if p.ws],
    return_exceptions=True
)
```

This sends to all students in parallel and cuts broadcast time from O(N) sequential to O(1) amortized.

**Timer task leak guard.** `_cancel_timer` is called in `start_question` and `reveal_question`, which is correct. The `finish_game` guard (`if room.status == 'finished': return`) prevents double-execution. This is well-implemented.

---

## 4. Blocking Operations in the Async Event Loop

FastAPI's event loop must never be blocked. Two areas of concern:

**Excel/XLSX generation** (in download routes) uses `openpyxl` or similar, which is CPU-bound and synchronous. Running this directly in an async handler freezes the event loop for all other users during that time. Wrap it:

```python
import asyncio
from fastapi.concurrency import run_in_threadpool

result = await run_in_threadpool(generate_excel_file, exam, students)
```

**Password hashing** (`werkzeug.security.generate_password_hash`) is intentionally slow (bcrypt/pbkdf2). Same problem — it blocks the event loop. This only happens on employee create/edit so the impact is low-frequency, but it should still use `run_in_threadpool`.

---

## 5. AI Feature — Storage Size

`AIPresentation.content` and `AIQuestionSet.content` are `Text` columns storing full JSON. A presentation with 10 slides and base64-encoded images can be 500KB–2MB per row. This has two consequences:

- Loading the admin "all presentations" list fetches the full `content` column for every row, even though the list view only needs `topic`, `grade`, `created_at`. Add a `deferred` loading option or use `with_only_columns` to exclude `content` in list queries.
- PostgreSQL stores large text values in a TOAST table automatically, but reads are still slower than small column values.

Short-term fix — exclude `content` from list queries:

```python
stmt = select(
    AIPresentation.id,
    AIPresentation.teacher_id,
    AIPresentation.topic,
    AIPresentation.grade,
    AIPresentation.slides_count,
    AIPresentation.created_at,
).where(...)
```

---

## 6. Authentication & Security

**Secret key defaults.** `SECRET_KEY` defaults to `'your-secret-key-here-change-in-production'`. If the environment variable is not set in production, session cookies can be forged by anyone who reads the source code. This must be enforced at startup:

```python
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is required")
```

**No login rate limiting.** The `/login` endpoint accepts unlimited attempts. A basic slowdown (e.g., `slowapi` with 10 attempts/minute per IP) would prevent brute-force attacks on teacher accounts.

**`require_login` hits the database on every request.** Every authenticated page load fires a `SELECT * FROM employees WHERE id = ?`. For a school-size app this is acceptable, but adding a simple in-process LRU cache (keyed on `(user_id, updated_at)`) would eliminate these reads entirely.

---

## 7. Static File Serving

FastAPI's `StaticFiles` mount works for development. In production, static files (CSS, JS, images) should be served directly by **Nginx** before the request ever reaches Python. This completely removes Python event loop involvement from static asset delivery. The Nginx config should include:

```nginx
location /static/ {
    alias /app/static/;
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

---

## 8. Translations (Language System)

Loading all locale JSONs into memory at startup is the correct approach — zero per-request overhead. The only limitation is that adding/editing translations requires a server restart to take effect. For a school context this is fine.

---

## 9. Overall Assessment

| Area | Status | Priority |
|------|--------|----------|
| Connection pool | Good | — |
| Indexes | Good, one missing (status) | Low |
| N+1 query risk | Present, depends on route code | High |
| WebSocket state (single worker) | Safe as-is | Medium if scaling |
| Parallel broadcast | Sequential, fixable | Medium |
| Blocking event loop (Excel/hashing) | Present | High |
| AI content column size | Large rows in list queries | Medium |
| Secret key enforcement | Missing guard | High (security) |
| Login rate limiting | Missing | Medium (security) |
| Migration system | `IF NOT EXISTS` only | High (operational) |
| Static file serving (production) | Needs Nginx | Medium |

**Summary:** The architecture is correct and the async patterns are generally sound. The three highest-priority items to address before a serious production deployment are: (1) adopt Alembic for migrations, (2) add `selectinload` to prevent N+1 queries, and (3) enforce the `SECRET_KEY` environment variable. The game engine is well-designed for single-process deployment and will need Redis if the app is ever scaled horizontally.
