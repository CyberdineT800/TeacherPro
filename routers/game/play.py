"""Student-facing game endpoints — join page and real-time WebSocket."""
import logging
from datetime import datetime

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db, AsyncSessionLocal, GameSession, GameParticipant
from services.game_engine import (
    get_room, PlayerState,
    broadcast_to_students, send_to_teacher,
    record_answer, _safe_send,
)

log = logging.getLogger("game.play")
router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ── Join landing page ─────────────────────────────────────────────────────────

@router.get("/play", response_class=HTMLResponse)
async def join_landing(request: Request):
    """Public landing — enter a game code."""
    return templates.TemplateResponse('game/join.html', {'request': request})


@router.get("/play/{code}", response_class=HTMLResponse)
async def join_game(code: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Show the nickname entry form for a specific game code."""
    code = code.upper()
    gs = (await db.execute(
        select(GameSession).where(GameSession.code == code)
    )).scalar_one_or_none()

    if not gs:
        return templates.TemplateResponse('game/join.html', {
            'request': request, 'error': "Bu kod bo'yicha o'yin topilmadi."
        })

    if gs.status == 'finished':
        return templates.TemplateResponse('game/join.html', {
            'request': request, 'error': "Bu o'yin allaqachon tugagan."
        })

    if gs.status == 'playing':
        return templates.TemplateResponse('game/join.html', {
            'request': request, 'error': "O'yin allaqachon boshlangan. Keyingi o'yinni kuting."
        })

    return templates.TemplateResponse('game/nickname.html', {
        'request': request, 'code': code, 'game_title': gs.title
    })


@router.post("/play/{code}/join", response_class=HTMLResponse)
async def join_game_post(code: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Create a GameParticipant row and redirect to the waiting room."""
    code = code.upper()
    form = await request.form()
    nickname = (form.get('nickname') or '').strip()[:50]

    if not nickname:
        gs = (await db.execute(
            select(GameSession).where(GameSession.code == code)
        )).scalar_one_or_none()
        return templates.TemplateResponse('game/nickname.html', {
            'request': request, 'code': code,
            'game_title': gs.title if gs else '',
            'error': "Ism kiriting."
        })

    gs = (await db.execute(
        select(GameSession).where(GameSession.code == code)
    )).scalar_one_or_none()

    if not gs or gs.status not in ('lobby', 'pending'):
        return templates.TemplateResponse('game/join.html', {
            'request': request, 'error': "O'yinga qo'shilish mumkin emas."
        })

    # Create DB participant row now so we have a stable id
    part = GameParticipant(session_id=gs.id, nickname=nickname)
    db.add(part)
    await db.commit()
    await db.refresh(part)

    # Hand off to the JS client via the play page (participant_id in URL)
    return RedirectResponse(
        url=f"/play/{code}/wait?pid={part.id}&nick={nickname}",
        status_code=303
    )


@router.get("/play/{code}/wait", response_class=HTMLResponse)
async def student_wait(code: str, request: Request):
    """Waiting room page — connects to WS and waits for teacher to start."""
    pid = request.query_params.get('pid', '')
    nick = request.query_params.get('nick', '')
    return templates.TemplateResponse('game/play.html', {
        'request': request, 'code': code.upper(), 'pid': pid, 'nick': nick
    })


# ── Student WebSocket ─────────────────────────────────────────────────────────

@router.websocket("/play/{code}/ws")
async def student_game_ws(code: str, websocket: WebSocket, pid: int = 0):
    """Each student connects here; messages: answer.

    No Depends(get_db) — WebSocket sessions are long-lived; use short-lived
    AsyncSessionLocal sessions for each DB operation instead.
    """
    await websocket.accept()
    code = code.upper()

    room = get_room(code)
    if not room:
        await websocket.send_json({'type': 'error', 'msg': 'Room not found'})
        await websocket.close()
        return

    # Load participant from DB with a short-lived session
    async with AsyncSessionLocal() as db:
        part = (await db.execute(
            select(GameParticipant).where(GameParticipant.id == pid)
        )).scalar_one_or_none()

    if not part or part.session_id != room.session_id:
        await websocket.send_json({'type': 'error', 'msg': 'Participant not found'})
        await websocket.close()
        return

    # Register player in room
    if pid not in room.players:
        room.players[pid] = PlayerState(participant_id=pid, nickname=part.nickname)
    room.players[pid].ws = websocket

    # Notify teacher of new player count
    await send_to_teacher(room, {
        'type': 'player_joined',
        'count': len(room.players),
        'nickname': part.nickname,
    })

    # Confirm to student
    await websocket.send_json({
        'type': 'joined',
        'nickname': part.nickname,
        'status': room.status,
    })

    try:
        async for data in websocket.iter_json():
            msg_type = data.get('type')

            if msg_type == 'answer':
                option = data.get('option')
                if isinstance(option, int) and 0 <= option <= 3:
                    await record_answer(room, pid, option)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.error("Student WS error room %s pid %s: %s", code, pid, e)
    finally:
        if pid in room.players:
            room.players[pid].ws = None
        await send_to_teacher(room, {
            'type': 'player_left',
            'count': len([p for p in room.players.values() if p.ws]),
            'nickname': part.nickname,
        })
