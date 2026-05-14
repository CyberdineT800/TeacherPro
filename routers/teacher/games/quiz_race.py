"""Teacher routes for Quiz Race game.

All Quiz Race-specific routes live under /teacher/games/quiz-race/
so it is clear which game type they belong to.

The hub /teacher/games is game-agnostic (shows all game types) and lives
in this same router for convenience.
"""
import json
import logging
import random
import string
import traceback
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Depends, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from config import RedirectResponse, ROOT_PATH
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import (
    get_db, AsyncSessionLocal, Employee, Subject, AIQuestionSet,
    GameSession, GameQuestion, GameParticipant,
)
from dependencies import require_login, flash, get_template_context
from services.games.quiz_race.engine import (
    create_room, get_room,
    start_question, reveal_question, finish_game, get_scoreboard,
)
from services.ai_service import generate_game_questions

log = logging.getLogger("teacher.games.quiz_race")
router = APIRouter(prefix="/teacher")
templates = Jinja2Templates(directory="templates")


def _random_code(n: int = 8) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))


async def _unique_code(db: AsyncSession) -> str:
    for _ in range(20):
        code = _random_code()
        if not (await db.execute(
            select(GameSession).where(GameSession.code == code)
        )).scalar_one_or_none():
            return code
    raise RuntimeError("Could not generate unique game code")


# ── Game type hub (game-agnostic) ─────────────────────────────────────────────

@router.get("/games", response_class=HTMLResponse)
async def teacher_games_hub(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: Employee = Depends(require_login),
):
    """Hub page — shows all available game types."""
    teacher_id = request.session.get('user_id')
    teacher = (await db.execute(
        select(Employee).where(Employee.id == teacher_id)
    )).scalar_one_or_none()

    if not teacher or not teacher.games_enabled:
        flash(request, "O'yin funksiyasi sizga yoqilmagan. Administrator bilan bog'laning.", 'warning')
        return RedirectResponse(url="/teacher/dashboard", status_code=303)

    total_sessions = (await db.execute(
        select(func.count(GameSession.id)).where(GameSession.teacher_id == teacher_id)
    )).scalar() or 0

    context = await get_template_context(request, db)
    context.update({'teacher': teacher, 'total_sessions': total_sessions})
    return templates.TemplateResponse('teacher/games/hub.html', context)


# ── Quiz Race: sessions list ──────────────────────────────────────────────────

@router.get("/games/quiz-race/sessions", response_class=HTMLResponse)
async def teacher_quiz_race_sessions(
    request: Request,
    selected_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    _user: Employee = Depends(require_login),
):
    """List of this teacher's Quiz Race sessions with a detail panel."""
    teacher_id = request.session.get('user_id')
    teacher = (await db.execute(
        select(Employee).where(Employee.id == teacher_id)
    )).scalar_one_or_none()

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
        'sessions': sessions, 'teacher': teacher,
        'selected_game': selected_game,
        'selected_participants': selected_participants,
        'selected_id': resolved_id,
    })
    return templates.TemplateResponse('teacher/games/quiz_race/list.html', context)


# ── Quiz Race: create ─────────────────────────────────────────────────────────

@router.get("/games/quiz-race/create", response_class=HTMLResponse)
async def teacher_quiz_race_create_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: Employee = Depends(require_login),
):
    teacher_id = request.session.get('user_id')
    teacher = (await db.execute(
        select(Employee).where(Employee.id == teacher_id)
    )).scalar_one_or_none()
    if not teacher or not teacher.games_enabled:
        return RedirectResponse(url="/teacher/games", status_code=303)

    subjects = (await db.execute(select(Subject).order_by(Subject.name))).scalars().all()
    saved_sets = (await db.execute(
        select(AIQuestionSet)
        .where(AIQuestionSet.teacher_id == teacher_id, AIQuestionSet.question_type == 'test')
        .order_by(AIQuestionSet.created_at.desc())
        .limit(50)
    )).scalars().all()

    context = await get_template_context(request, db)
    context.update({'subjects': subjects, 'saved_sets': saved_sets, 'teacher': teacher})
    return templates.TemplateResponse('teacher/games/quiz_race/create.html', context)


@router.post("/games/quiz-race/create")
async def teacher_quiz_race_create(
    request: Request,
    title: str = Form(...),
    subject_name: str = Form(...),
    grade: int = Form(...),
    time_per_question: int = Form(20),
    question_source: str = Form('ai'),
    saved_set_id: Optional[str] = Form(None),
    ai_topic: Optional[str] = Form(None),
    ai_language: str = Form('uz'),
    ai_count: int = Form(10),
    db: AsyncSession = Depends(get_db),
    _user: Employee = Depends(require_login),
):
    teacher_id = request.session.get('user_id')
    teacher = (await db.execute(
        select(Employee).where(Employee.id == teacher_id)
    )).scalar_one_or_none()
    if not teacher or not teacher.games_enabled:
        raise HTTPException(403)

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
    await db.flush()

    questions_to_add = []

    if question_source == 'saved' and saved_set_id_int:
        qs_obj = (await db.execute(
            select(AIQuestionSet).where(
                AIQuestionSet.id == saved_set_id_int,
                AIQuestionSet.teacher_id == teacher_id,
            )
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
                    correct_option=q.get('correct', 0), points=10,
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
                    option_a=q.get('option_a', ''), option_b=q.get('option_b', ''),
                    option_c=q.get('option_c', ''), option_d=q.get('option_d', ''),
                    correct_option=q.get('correct', 0), points=10,
                ))
        except Exception as e:
            log.error("AI game question generation failed: %s\n%s", e, traceback.format_exc())
            flash(request, f"AI savollar yaratishda xatolik: {str(e)[:200]}", 'danger')
            await db.rollback()
            return RedirectResponse(url="/teacher/games/quiz-race/create", status_code=303)

    for gq in questions_to_add:
        db.add(gq)
    if not questions_to_add and question_source != 'manual':
        flash(request, "Savollar qo'shilmadi.", 'warning')

    gs.status = 'lobby'
    await db.commit()
    flash(request, f"O'yin yaratildi! Kod: {code}", 'success')
    return RedirectResponse(url=f"/teacher/games/quiz-race/{gs.id}/lobby", status_code=303)


# ── Quiz Race: lobby ──────────────────────────────────────────────────────────

@router.get("/games/quiz-race/{sid}/lobby", response_class=HTMLResponse)
async def teacher_quiz_race_lobby(
    sid: int, request: Request,
    db: AsyncSession = Depends(get_db),
    _user: Employee = Depends(require_login),
):
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
        return RedirectResponse(url=f"/teacher/games/quiz-race/{sid}/results", status_code=303)

    try:
        import qrcode
        from io import BytesIO
        import base64
        join_url = str(request.base_url).rstrip('/') + ROOT_PATH + f"/play/quiz-race/{gs.code}"
        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(join_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format='PNG')
        qr_b64 = base64.b64encode(buf.getvalue()).decode()
    except Exception:
        qr_b64 = ''
        join_url = f"{ROOT_PATH}/play/quiz-race/{gs.code}"

    context = await get_template_context(request, db)
    context.update({'gs': gs, 'qr_b64': qr_b64, 'join_url': join_url})
    return templates.TemplateResponse('teacher/games/quiz_race/lobby.html', context)


# ── Quiz Race: results ────────────────────────────────────────────────────────

@router.get("/games/quiz-race/{sid}/results", response_class=HTMLResponse)
async def teacher_quiz_race_results(
    sid: int, request: Request,
    db: AsyncSession = Depends(get_db),
    _user: Employee = Depends(require_login),
):
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
    return templates.TemplateResponse('teacher/games/quiz_race/results.html', context)


# ── Quiz Race: teacher WebSocket ──────────────────────────────────────────────

@router.websocket("/games/quiz-race/{sid}/ws")
async def teacher_quiz_race_ws(sid: int, websocket: WebSocket):
    """Teacher's real-time control socket."""
    await websocket.accept()

    session = websocket.session if hasattr(websocket, 'session') else {}
    teacher_id = session.get('user_id')
    if not teacher_id:
        await websocket.send_json({'type': 'error', 'msg': 'Not authenticated'})
        await websocket.close(code=4001)
        return

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
                    'correct_option': q.correct_option, 'points': q.points,
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

    try:
        async for data in websocket.iter_json():
            action = data.get('action')
            if action == 'start':
                if room.status == 'lobby':
                    room.status = 'playing'
                    async with AsyncSessionLocal() as db:
                        gs_obj = (await db.execute(
                            select(GameSession).where(GameSession.id == sid)
                        )).scalar_one_or_none()
                        if gs_obj:
                            gs_obj.status = 'playing'
                            gs_obj.started_at = datetime.utcnow()
                            await db.commit()
                    await start_question(room, _save_cb)
            elif action == 'next':
                if room.status == 'reveal':
                    from services.games.quiz_race.engine import _cancel_timer
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
