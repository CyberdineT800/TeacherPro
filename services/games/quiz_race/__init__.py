"""Quiz Race game service package."""
from .engine import (
    PlayerState,
    RoomState,
    create_room,
    get_room,
    remove_room,
    list_active_rooms,
    broadcast_to_students,
    send_to_teacher,
    broadcast_to_all,
    get_scoreboard,
    assign_badges,
    start_question,
    reveal_question,
    finish_game,
    record_answer,
    _safe_send,
    _cancel_timer,
)

__all__ = [
    'PlayerState', 'RoomState',
    'create_room', 'get_room', 'remove_room', 'list_active_rooms',
    'broadcast_to_students', 'send_to_teacher', 'broadcast_to_all',
    'get_scoreboard', 'assign_badges',
    'start_question', 'reveal_question', 'finish_game', 'record_answer',
    '_safe_send', '_cancel_timer',
]
