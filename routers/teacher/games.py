"""Teacher game management routes — create, lobby, host Quiz Race sessions."""
import json
import logging
import random
import string
import traceback
from datetime import datetime
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Request, Depends, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sqlalchemy import func

from models import (
    get_db, AsyncSessionLocal, Employee, Subject, AIQuestionSet,
    GameSession, GameQuestion, GameParticipant,
)
from dependencies import require_login, flash, get_template_context
from services.game_engine import (
    create_room, get_room, remove_room,
    start_question, reveal_question, finish_game, get_scoreboard,
)
from services.ai_service import generate_game_questions

log = logging.getLogger("teacher.games")
# NOTE: No router-level dependency — WebSocket endpoints cannot use Request-based
# dependencies. Each HTTP route adds Depends(require_login) individually.
router = APIRouter(prefix="/teacher")
templates = Jinja2Templates(directory="templates")


def _random_code(n: int = 8) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))


async def _unique_code(db: AsyncSession) -> str:
    for _ in range(20):
        code = _random_code()
        existing = (await db.execute(
            select(GameSession).where(GameSession.code == code)
        )).scalar_one_or_none()
        if not existing:
            return code
    raise RuntimeError("Could not generate unique game code")


# ── Game type hub ─────────────────────────────────────────────────────────────

@router.get("/games", response_class=HTMLResponse)
async def teacher_games_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: Employee = Depends(require_login),
):
    """Hub page — show available game types (Quiz Race, …)."""
    teacher_id = request.session.get('user_id')
    teacher = (await db.execute(select(Employee).where(Employee.id == teacher_id))).scalar_one_or_none()

    if not teacher or not teacher.games_enabled:
        flash(request, "O'yin funksiyasi sizga yoqilmagan. Administrator bilan bog'laning.", 'warning')
        return RedirectResponse(url="/teacher/dashboard", status_code=303)

    total_sessions = (await db.execute(
        select(func.count(GameSession.id)).where(GameSession.teacher_id == teacher_id)
    )).scalar() or 0

    context = await get_template_context(request, db)
    context.update({'teacher': teacher, 'total_sessions': total_sessions})
    return templates.TemplateResponse('teacher/games_hub.html', context)


# ── Sessions list (master-detail) ─────────────────────────────────────────────

@router.get("/games/sessions", response_class=HTMLResponse)
async def teacher_games_sessions(
    request: Request,
    selected_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    _user: Employee = Depends(require_login),
):
    """List of this teacher's Quiz Race sessions with a detail panel."""
    teacher_id = request.session.get('user_id')
    teacher = (await db.execute(select(Employee).where(Employee.id == teacher_id))).scalar_one_or_none()

    if not teacher or not teacher.games_enabled:
        flash(request, "O'yin funksiyasi sizga yoqilmagan. Administrator bilan bog'laning.", 'warning')
        return RedirectResponse(url="/teacher/dashboard", status_code=303)

    sessions = (await db.execute(
        select(GameSession)
        .options(selectinload(GameSession.questions))
        .where(GameSession.teacher_id == teacher_id)
        .order_by(GameSession.created_at.desc())
        .limit(100)
    )).scalars().all()

    # Load detail for selected game (or auto-select most recent)
    selected_game = None
    selected_participants: list = []
    resolved_id = selected_id or (sessions[0].id if sessions else None)

    if resolved_id:
        selected_game = (await db.execute(
            select(GameSession)
            .options(selectinload(GameSession.questions), selectinload(GameSession.participants))
            .where(GameSession.id == resolved_id, GameSession.teacher_id == teacher_id)
        )).scalar_one_or_none()
        if selected_game and selected_game.participants:
            selected_participants = sorted(selected_game.participants, key=lambda p: p.rank or 9999)

    context = await get_template_context(request, db)
    context.update({
        'sessions': sessions,
        'teacher': teacher,
        'selected_game': selected_game,
        'selected_participants': selected_participants,
        'selected_id': resolved_id,
    })
    return templates.TemplateResponse('teacher/games_list.html', context)


# ── Create new game ───────────────────────────────────────────────────────────

@router.get("/games/create", response_class=HTMLResponse)
async def teacher_games_create_form(request: Request, db: AsyncSession = Depends(get_db), _user: Employee = Depends(require_login)):
    teacher_id = request.session.get('user_id')
    teacher = (await db.execute(select(Employee).where(Employee.id == teacher_id))).scalar_one_or_none()
    if not teacher or not teacher.games_enabled:
        return RedirectResponse(url="/teacher/games", status_code=303)

    subjects = (await db.execute(select(Subject).order_by(Subject.name))).scalars().all()
    # Teacher's saved AI question sets (test type only)
    saved_sets = (await db.execute(
        select(AIQuestionSet)
        .where(AIQuestionSet.teacher_id == teacher_id, AIQuestionSet.question_type == 'test')
        .order_by(AIQuestionSet.created_at.desc())
        .limit(50)
    )).scalars().all()

    context = await get_template_context(request, db)
    context.update({'subjects': subjects, 'saved_sets': saved_sets, 'teacher': teacher})
    return templates.TemplateResponse('teacher/games_create.html', context)


@router.post("/games/create")
async def teacher_games_create(
    request: Request,
    title: str = Form(...),
    subject_name: str = Form(...),
    grade: int = Form(...),
    time_per_question: int = Form(20),
    question_source: str = Form('ai'),           # 'ai' | 'saved' | 'manual'
    saved_set_id: Optional[str] = Form(None),   # raw string; empty string -> None
    ai_topic: Optional[str] = Form(None),
    ai_language: str = Form('uz'),
    ai_count: int = Form(10),
    db: AsyncSession = Depends(get_db),
    _user: Employee = Depends(require_login),
):
    teacher_id = request.session.get('user_id')
    teacher = (await db.execute(select(Employee).where(Employee.id == teacher_id))).scalar_one_or_none()
    if not teacher or not teacher.games_enabled:
        raise HTTPException(403)

    # Normalise saved_set_id: HTML sends "" for empty <select>
    saved_set_id_int: Optional[int] = None
    if saved_set_id and saved_set_id.strip().isdigit():
        saved_set_id_int = int(saved_set_id.strip())

    time_per_question = max(10, min(60, time_per_question))
    code = await _unique_code(db)

    gs = GameSession(
        code=code, teacher_id=teacher_id, title=title.strip(),
        subject_name=subject_name.strip(), grade=grade,
        time_per_question=time_per_question, status='pending',
    )
    db.add(gs)
    await db.flush()  # get gs.id

    questions_to_add = []

    if question_source == 'saved' and saved_set_id_int:
        qs_obj = (await db.execute(
            select(AIQuestionSet).where(AIQuestionSet.id == saved_set_id_int,
                                        AIQuestionSet.teacher_id == teacher_id)
        )).scalar_one_or_none()
        if qs_obj:
            data = json.loads(qs_obj.content)
            for i, q in enumerate(data.get('questions', [])[:30]):
                questions_to_add.append(GameQuestion(
                    session_id=gs.id, order=i,
                    question_text=q.get('question', ''),
                    option_a=q.get('options', ['', '', '', ''])[0],
                    option_b=q.get('options', ['', '', '', ''])[1],
                    option_c=q.get('options', ['', '', '', ''])[2],
                    option_d=q.get('options', ['', '', '', ''])[3],
                    correct_option=q.get('correct', 0),
                    points=100,
                ))

    elif question_source == 'ai' and ai_topic:
        try:
            ai_count = max(5, min(20, ai_count))
            data = await generate_game_questions(
                subject_name.strip(), grade, ai_topic.strip(), ai_language, ai_count
            )
            for i, q in enumerate(data.get('questions', [])):
                questions_to_add.append(GameQuestion(
                    session_id=gs.id, order=i,
                    question_text=q.get('question', ''),
                    option_a=q.get('option_a', ''),
                    option_b=q.get('option_b', ''),
                    option_c=q.get('option_c', ''),
                    option_d=q.get('option_d', ''),
                    correct_option=q.get('correct', 0),
                    points=100,
                ))
        except Exception as e:
            log.error("AI game question generation failed: %s\n%s", e, traceback.format_exc())
            flash(request, f"AI savollar yaratishda xatolik: {str(e)[:200]}", 'danger')
            await db.rollback()
            return RedirectResponse(url="/teacher/games/create", status_code=303)

    # manual: questions added via lobby edit (not implemented here yet;
    # fall through with 0 questions, teacher edits before starting)

    if questions_to_add:
        for gq in questions_to_add:
            db.add(gq)
    elif question_source != 'manual':
        flash(request, "Savollar qo'shibgina o'yin yaratilmadi.", 'warning')

    gs.status = 'lobby'
    await db.commit()
    flash(request, f"O'yin yaratildi! Kod: {code}", 'success')
    return RedirectResponse(url=f"/teacher/games/{gs.id}/lobby", status_code=303)


# ── Lobby (teacher control room) ──────────────────────────────────────────────

@router.get("/games/{sid}/lobby", response_class=HTMLResponse)
async def teacher_games_lobby(sid: int, request: Request, db: AsyncSession = Depends(get_db), _user: Employee = Depends(require_login)):
    teacher_id = request.session.get('user_id')
    gs = (await db.execute(
        select(GameSession)
        .options(selectinload(GameSession.questions))
        .where(GameSession.id == sid, GameSession.teacher_id == teacher_id)
    )).scalar_one_or_none()
    if not gs:
        flash(request, "O'yin topilmadi", 'danger')
        return RedirectResponse(url="/teacher/games", status_code=303)

    if gs.status == 'finished':
        return RedirectResponse(url=f"/teacher/games/{sid}/results", status_code=303)

    # QR code
    try:
        import qrcode
        from io import BytesIO
        import base64
        join_url = str(request.base_url).rstrip('/') + f"/play/{gs.code}"
        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(join_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format='PNG')
        qr_b64 = base64.b64encode(buf.getvalue()).decode()
    except Exception:
        qr_b64 = ''
        join_url = f"/play/{gs.code}"

    context = await get_template_context(request, db)
    context.update({'gs': gs, 'qr_b64': qr_b64, 'join_url': join_url})
    return templates.TemplateResponse('teacher/games_lobby.html', context)


# ── Game results ──────────────────────────────────────────────────────────────

@router.get("/games/{sid}/results", response_class=HTMLResponse)
async def teacher_game_results(sid: int, request: Request, db: AsyncSession = Depends(get_db), _user: Employee = Depends(require_login)):
    teacher_id = request.session.get('user_id')
    gs = (await db.execute(
        select(GameSession)
        .options(selectinload(GameSession.questions), selectinload(GameSession.participants))
        .where(GameSession.id == sid, GameSession.teacher_id == teacher_id)
    )).scalar_one_or_none()
    if not gs:
        flash(request, "O'yin topilmadi", 'danger')
        return RedirectResponse(url="/teacher/games", status_code=303)

    participants = sorted(gs.participants, key=lambda p: (p.rank or 9999))
    context = await get_template_context(request, db)
    context.update({'gs': gs, 'participants': participants})
    return templates.TemplateResponse('teacher/games_results.html', context)


# ── Teacher WebSocket (host control) ─────────────────────────────────────────

@router.websocket("/games/{sid}/ws")
async def teacher_game_ws(sid: int, websocket: WebSocket):
    """Teacher's real-time control socket. Handles: start, next, reveal, end.

    NOTE: No Depends(get_db) here — WebSocket connections can last minutes/hours
    and a single held session will be recycled by the pool. Each DB operation
    opens its own short-lived session via AsyncSessionLocal instead.
    """
    await websocket.accept()

    # Auth — read from scope["session"] directly (SessionMiddleware populates it)
    session = websocket.session if hasattr(websocket, 'session') else {}
    teacher_id = session.get('user_id')
    if not teacher_id:
        await websocket.send_json({'type': 'error', 'msg': 'Not authenticated'})
        await websocket.close(code=4001)
        return

    # ── Initial load with a short-lived session ────────────────────────────────
    async with AsyncSessionLocal() as db:
        gs = (await db.execute(
            select(GameSession)
            .options(selectinload(GameSession.questions))
            .where(GameSession.id == sid)
        )).scalar_one_or_none()

        if not gs:
            await websocket.send_json({'type': 'error', 'msg': 'Game not found'})
            await websocket.close()
            return

        code = gs.code.upper()
        room = get_room(code)

        if not room:
            questions = [
                {
                    'question_text': q.question_text,
                    'option_a': q.option_a, 'option_b': q.option_b,
                    'option_c': q.option_c, 'option_d': q.option_d,
                    'correct_option': q.correct_option,
                    'points': q.points,
                }
                for q in sorted(gs.questions, key=lambda x: x.order)
            ]
            room = create_room(gs.id, code, gs.teacher_id, gs.time_per_question, questions)

    room.teacher_ws = websocket

    await websocket.send_json({
        'type': 'room_state',
        'status': room.status,
        'players': [{'nickname': p.nickname, 'score': p.score} for p in room.players.values()],
        'question_count': room.question_count,
        'current_index': room.current_question_index,
    })

    # ── Persistence callback — fresh session each call ─────────────────────────
    async def _save_cb(room, scoreboard):
        async with AsyncSessionLocal() as db:
            gs_obj = (await db.execute(
                select(GameSession).where(GameSession.id == room.session_id)
            )).scalar_one_or_none()
            if gs_obj:
                gs_obj.status = 'finished'
                gs_obj.finished_at = datetime.utcnow()

            for entry in scoreboard:
                player = next(
                    (p for p in room.players.values() if p.nickname == entry['nickname']), None
                )
                if player:
                    part = (await db.execute(
                        select(GameParticipant).where(GameParticipant.id == player.participant_id)
                    )).scalar_one_or_none()
                    if part:
                        part.total_score = player.score
                        part.correct_answers = player.correct
                        part.wrong_answers = player.wrong
                        part.rank = entry['rank']
            await db.commit()

    # ── Message loop ───────────────────────────────────────────────────────────
    try:
        async for data in websocket.iter_json():
            action = data.get('action')

            if action == 'start':
                if room.status == 'lobby':
                    room.status = 'playing'
                    # Update started_at with a fresh session
                    async with AsyncSessionLocal() as db:
                        gs_obj = (await db.execute(
                            select(GameSession).where(GameSession.id == sid)
                        )).scalar_one_or_none()
                        if gs_obj:
                            gs_obj.started_at = datetime.utcnow()
                            await db.commit()
                    await start_question(room, _save_cb)

            elif action == 'next':
                if room.status == 'reveal':
                    from services.game_engine import _cancel_timer
                    _cancel_timer(room)
                    await start_question(room, _save_cb)

            elif action == 'reveal':
                if room.status == 'question':
                    await reveal_question(room, _save_cb)

            elif action == 'end':
                await finish_game(room, _save_cb)
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.error("Teacher WS error room %s: %s", code, e)
    finally:
        if room and room.teacher_ws is websocket:
            room.teacher_ws = None
