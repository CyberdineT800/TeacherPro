"""Student-facing Quiz Race endpoints — join page and real-time WebSocket.

All routes live under /play/quiz-race/ so they are clearly identified
as belonging to the Quiz Race game type.
"""
import logging

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import HTMLResponse
from config import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db, AsyncSessionLocal, GameSession, GameParticipant
from services.games.quiz_race.engine import (
    get_room, PlayerState,
    broadcast_to_students, send_to_teacher,
    record_answer, _safe_send,
)
from config import ROOT_PATH

log = logging.getLogger("game.quiz_race")
router = APIRouter()
templates = Jinja2Templates(directory="templates")

_PREFIX = "/play/quiz-race"


# ── Join landing page ─────────────────────────────────────────────────────────

@router.get("/play/quiz-race", response_class=HTMLResponse)
async def join_landing(request: Request):
    """Public landing — enter a game code."""
    return templates.TemplateResponse(
        'game/quiz_race/join.html',
        {'request': request, 'root_path': ROOT_PATH}
    )


@router.get("/play/quiz-race/{code}", response_class=HTMLResponse)
async def join_game(code: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Show the nickname entry form for a specific game code."""
    code = code.upper()
    gs = (await db.execute(
        select(GameSession).where(GameSession.code == code)
    )).scalar_one_or_none()

    if not gs:
        return templates.TemplateResponse('game/quiz_race/join.html', {
            'request': request,
            'error': "Bu kod bo'yicha o'yin topilmadi.",
            'root_path': ROOT_PATH,
        })
    if gs.status == 'finished':
        return templates.TemplateResponse('game/quiz_race/join.html', {
            'request': request,
            'error': "Bu o'yin allaqachon tugagan.",
            'root_path': ROOT_PATH,
        })
    if gs.status == 'playing':
        return templates.TemplateResponse('game/quiz_race/join.html', {
            'request': request,
            'error': "O'yin allaqachon boshlangan. Keyingi o'yinni kuting.",
            'root_path': ROOT_PATH,
        })

    return templates.TemplateResponse('game/quiz_race/nickname.html', {
        'request': request, 'code': code, 'game_title': gs.title, 'root_path': ROOT_PATH,
    })


@router.post("/play/quiz-race/{code}/join", response_class=HTMLResponse)
async def join_game_post(code: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Create a GameParticipant row and redirect to the waiting room."""
    code = code.upper()
    form = await request.form()
    nickname = (form.get('nickname') or '').strip()[:50]

    if not nickname:
        gs = (await db.execute(
            select(GameSession).where(GameSession.code == code)
        )).scalar_one_or_none()
        return templates.TemplateResponse('game/quiz_race/nickname.html', {
            'request': request, 'code': code,
            'game_title': gs.title if gs else '',
            'error': "Ism kiriting.", 'root_path': ROOT_PATH,
        })

    gs = (await db.execute(
        select(GameSession).where(GameSession.code == code)
    )).scalar_one_or_none()

    if not gs or gs.status not in ('lobby', 'pending'):
        return templates.TemplateResponse('game/quiz_race/join.html', {
            'request': request, 'error': "O'yinga qo'shilish mumkin emas.", 'root_path': ROOT_PATH,
        })

    part = GameParticipant(session_id=gs.id, nickname=nickname)
    db.add(part)
    await db.commit()
    await db.refresh(part)

    return RedirectResponse(
        url=f"/play/quiz-race/{code}/wait?pid={part.id}&nick={nickname}",
        status_code=303
    )


@router.get("/play/quiz-race/{code}/wait", response_class=HTMLResponse)
async def student_wait(code: str, request: Request):
    """Waiting room — connects to WS and waits for teacher to start."""
    pid = request.query_params.get('pid', '')
    nick = request.query_params.get('nick', '')
    return templates.TemplateResponse('game/quiz_race/play.html', {
        'request': request, 'code': code.upper(), 'pid': pid, 'nick': nick, 'root_path': ROOT_PATH,
    })


# ── Student WebSocket ─────────────────────────────────────────────────────────

@router.websocket("/play/quiz-race/{code}/ws")
async def student_game_ws(code: str, websocket: WebSocket, pid: int = 0):
    """Each student connects here; messages: answer."""
    await websocket.accept()
    code = code.upper()

    room = get_room(code)
    if not room:
        await websocket.send_json({'type': 'error', 'msg': 'Room not found'})
        await websocket.close()
        return

    async with AsyncSessionLocal() as db:
        part = (await db.execute(
            select(GameParticipant).where(GameParticipant.id == pid)
        )).scalar_one_or_none()

    if not part or part.session_id != room.session_id:
        await websocket.send_json({'type': 'error', 'msg': 'Participant not found'})
        await websocket.close()
        return

    if pid not in room.players:
        room.players[pid] = PlayerState(participant_id=pid, nickname=part.nickname)
    room.players[pid].ws = websocket

    await send_to_teacher(room, {
        'type': 'player_joined',
        'count': len(room.players),
        'nickname': part.nickname,
    })
    await websocket.send_json({
        'type': 'joined',
        'nickname': part.nickname,
        'status': room.status,
    })

    try:
        async for data in websocket.iter_json():
            if data.get('type') == 'answer':
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
