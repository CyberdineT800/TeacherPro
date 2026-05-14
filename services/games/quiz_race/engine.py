"""
In-memory real-time game state manager for Quiz Race.

Each active game lives in a RoomState stored in a module-level dict keyed by
the 6-char join code. No database is touched here except at game-end when
final results are persisted.
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from fastapi import WebSocket

log = logging.getLogger("game_engine")

_AUTO_ADVANCE_SECS = 4   # seconds to display results before auto-advancing


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PlayerState:
    participant_id: int          # DB row id created at join time
    nickname: str
    score: int = 0
    correct: int = 0
    wrong: int = 0
    answered_current: bool = False
    last_answer: Optional[int] = None   # 0-3 index, None = no answer
    answer_time: float = 0.0            # time.time() when answer arrived
    ws: Optional[WebSocket] = None


@dataclass
class RoomState:
    session_id: int
    code: str
    teacher_id: int
    time_per_question: int           # seconds
    questions: List[dict]            # list of GameQuestion-like dicts
    players: Dict[int, PlayerState] = field(default_factory=dict)
    teacher_ws: Optional[WebSocket] = None
    current_question_index: int = -1
    question_start_time: float = 0.0
    timer_task: Optional[asyncio.Task] = None
    status: str = 'lobby'            # lobby | question | reveal | finished
    save_cb: Optional[Any] = None    # persisted here so record_answer can use it

    @property
    def question_count(self) -> int:
        return len(self.questions)


# ---------------------------------------------------------------------------
# Global registry
# ---------------------------------------------------------------------------

_rooms: Dict[str, RoomState] = {}


def create_room(session_id: int, code: str, teacher_id: int,
                time_per_question: int, questions: List[dict]) -> RoomState:
    room = RoomState(
        session_id=session_id,
        code=code.upper(),
        teacher_id=teacher_id,
        time_per_question=time_per_question,
        questions=questions,
    )
    _rooms[code.upper()] = room
    return room


def get_room(code: str) -> Optional[RoomState]:
    return _rooms.get(code.upper())


def remove_room(code: str) -> None:
    _rooms.pop(code.upper(), None)


def list_active_rooms() -> List[str]:
    return list(_rooms.keys())


# ---------------------------------------------------------------------------
# Messaging helpers
# ---------------------------------------------------------------------------

async def _safe_send(ws: WebSocket, msg: dict) -> bool:
    """Send JSON to a WebSocket; return False if the connection is dead."""
    try:
        await ws.send_json(msg)
        return True
    except Exception:
        return False


async def broadcast_to_students(room: RoomState, message: dict) -> None:
    players = [(pid, p) for pid, p in list(room.players.items()) if p.ws]
    if not players:
        return
    results = await asyncio.gather(
        *(_safe_send(p.ws, message) for _, p in players),
        return_exceptions=True,
    )
    for (pid, _), ok in zip(players, results):
        if ok is not True and pid in room.players:
            room.players[pid].ws = None


async def send_to_teacher(room: RoomState, message: dict) -> None:
    if room.teacher_ws:
        ok = await _safe_send(room.teacher_ws, message)
        if not ok:
            room.teacher_ws = None


async def broadcast_to_all(room: RoomState, message: dict) -> None:
    await broadcast_to_students(room, message)
    await send_to_teacher(room, message)


# ---------------------------------------------------------------------------
# Scoreboard helpers
# ---------------------------------------------------------------------------

def get_scoreboard(room: RoomState) -> List[dict]:
    players = list(room.players.values())
    players.sort(key=lambda p: (-p.score, p.nickname))
    return [
        {
            'rank': i + 1,
            'nickname': p.nickname,
            'score': p.score,
            'correct': p.correct,
            'wrong': p.wrong,
        }
        for i, p in enumerate(players)
    ]


_BADGES = [
    ('🥇', lambda r, e: r == 1),
    ('🥈', lambda r, e: r == 2),
    ('🥉', lambda r, e: r == 3),
    ('🎯 Perfect', lambda r, e: e.get('correct', 0) > 0 and e.get('wrong', 0) == 0),
    ('⚡ Speedy', lambda r, e: r <= 3 and e.get('correct', 0) > 0),
]


def assign_badges(scoreboard: List[dict]) -> List[dict]:
    for entry in scoreboard:
        r = entry['rank']
        entry['badges'] = [
            label for label, fn in _BADGES if fn(r, entry)
        ]
    return scoreboard


# ---------------------------------------------------------------------------
# Game flow
# ---------------------------------------------------------------------------

async def start_question(room: RoomState, save_cb=None) -> None:
    """Cancel any running timer and display the next question."""
    _cancel_timer(room)
    if save_cb is not None:
        room.save_cb = save_cb  # store so record_answer can reach it later

    room.current_question_index += 1
    if room.current_question_index >= room.question_count:
        await finish_game(room, save_cb)
        return

    q = room.questions[room.current_question_index]
    room.status = 'question'
    room.question_start_time = time.time()

    # Reset per-question state for all players
    for player in room.players.values():
        player.answered_current = False
        player.last_answer = None
        player.answer_time = 0.0

    msg = {
        'type': 'question_start',
        'index': room.current_question_index,
        'total': room.question_count,
        'question': q['question_text'],
        'options': [q['option_a'], q['option_b'], q['option_c'], q['option_d']],
        'time_limit': room.time_per_question,
        'points': q.get('points', 10),
    }
    await broadcast_to_all(room, msg)

    # Kick off the auto-advance timer
    room.timer_task = asyncio.create_task(
        _question_timer(room, save_cb),
        name=f"timer_{room.code}_{room.current_question_index}",
    )


async def _question_timer(room: RoomState, save_cb) -> None:
    try:
        await asyncio.sleep(room.time_per_question)
        if room.status == 'question':
            # Clear reference BEFORE calling reveal_question so _cancel_timer()
            # inside it does NOT cancel this running task (self-cancellation bug).
            room.timer_task = None
            await reveal_question(room, save_cb)
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        log.error("Timer error in room %s: %s", room.code, exc)


async def _auto_advance(room: RoomState, save_cb) -> None:
    """After showing question results, automatically move to the next question."""
    try:
        await asyncio.sleep(_AUTO_ADVANCE_SECS)
        if room.status == 'reveal':
            # Clear reference BEFORE calling start_question so _cancel_timer()
            # inside it does NOT cancel this running task (self-cancellation bug).
            room.timer_task = None
            await start_question(room, save_cb)
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        log.error("Auto-advance error in room %s: %s", room.code, exc)


def _cancel_timer(room: RoomState) -> None:
    if room.timer_task and not room.timer_task.done():
        room.timer_task.cancel()
    room.timer_task = None


async def record_answer(room: RoomState, participant_id: int, option: int) -> None:
    """Store a player's answer; ignore if already answered or wrong phase."""
    if room.status != 'question':
        return
    player = room.players.get(participant_id)
    if not player or player.answered_current:
        return

    player.answered_current = True
    player.last_answer = option
    player.answer_time = time.time()

    # Let teacher know how many have answered
    answered = sum(1 for p in room.players.values() if p.answered_current)
    await send_to_teacher(room, {
        'type': 'answer_update',
        'answered': answered,
        'total': len(room.players),
    })

    # If everyone has answered, reveal early
    if answered == len(room.players):
        _cancel_timer(room)
        await reveal_question(room, room.save_cb)


async def reveal_question(room: RoomState, save_cb) -> None:
    """Score the current question and push results to all clients."""
    _cancel_timer(room)
    if room.status != 'question':
        return

    room.status = 'reveal'
    q = room.questions[room.current_question_index]
    correct_option: int = q['correct_option']
    base_points: int = q.get('points', 10)

    for player in room.players.values():
        if player.last_answer is None:
            # no answer
            continue

        if player.last_answer == correct_option:
            elapsed = max(0.0, player.answer_time - room.question_start_time)
            time_ratio = max(0.0, 1.0 - elapsed / max(room.time_per_question, 1))
            score_gained = int(base_points * (0.5 + 0.5 * time_ratio))
            player.score += score_gained
            player.correct += 1

            if player.ws:
                await _safe_send(player.ws, {
                    'type': 'question_result',
                    'was_correct': True,
                    'correct_option': correct_option,
                    'score_gained': score_gained,
                    'total_score': player.score,
                })
        else:
            player.wrong += 1
            if player.ws:
                await _safe_send(player.ws, {
                    'type': 'question_result',
                    'was_correct': False,
                    'correct_option': correct_option,
                    'score_gained': 0,
                    'total_score': player.score,
                })

    # Players who didn't answer at all
    for player in room.players.values():
        if player.last_answer is None and player.ws:
            await _safe_send(player.ws, {
                'type': 'question_result',
                'was_correct': None,
                'correct_option': correct_option,
                'score_gained': 0,
                'total_score': player.score,
            })

    is_last = room.current_question_index + 1 >= room.question_count
    scoreboard = get_scoreboard(room)
    await send_to_teacher(room, {
        'type': 'question_end',
        'correct_option': correct_option,
        'scoreboard': scoreboard[:10],
        'answered_count': sum(1 for p in room.players.values() if p.last_answer is not None),
        'total_count': len(room.players),
        'is_last': is_last,
    })

    # Auto-advance to next question after displaying results, unless this was the last one
    if not is_last:
        room.timer_task = asyncio.create_task(
            _auto_advance(room, save_cb),
            name=f"auto_adv_{room.code}_{room.current_question_index}",
        )
    else:
        await finish_game(room, save_cb)


async def finish_game(room: RoomState, save_cb=None) -> None:
    """End the game, push final scoreboard, persist results."""
    if room.status == 'finished':
        return  # guard against double-call (auto-advance + teacher 'end' race)
    _cancel_timer(room)
    room.status = 'finished'

    scoreboard = get_scoreboard(room)
    total_q = room.question_count
    for entry in scoreboard:
        entry['total_questions'] = total_q
    scoreboard = assign_badges(scoreboard)

    # Notify teacher
    await send_to_teacher(room, {
        'type': 'game_finished',
        'scoreboard': scoreboard,
    })

    # Notify each student their personal result
    rank_map = {entry['nickname']: entry for entry in scoreboard}
    for player in room.players.values():
        entry = rank_map.get(player.nickname, {})
        if player.ws:
            await _safe_send(player.ws, {
                'type': 'game_finished',
                'rank': entry.get('rank', 0),
                'total_players': len(room.players),
                'score': player.score,
                'correct': player.correct,
                'wrong': player.wrong,
                'badges': entry.get('badges', []),
            })

    # Persist results via callback
    if save_cb:
        try:
            await save_cb(room, scoreboard)
        except Exception as exc:
            log.error("Failed to persist game results for room %s: %s", room.code, exc)
