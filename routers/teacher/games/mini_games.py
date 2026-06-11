"""Teacher routes for static mini-games from PrimarySchoolGames.

Each game is served in a full-viewport iframe wrapper so the teacher stays
authenticated inside the TeacherPro shell.  Games themselves are static
HTML/JS/CSS files served under /mini-games/ (mounted in main.py) or from
/static/games/ for games that required emoji cleanup.
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from config import ROOT_PATH
from dependencies import require_login, get_template_context
from models import Employee, get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
templates = Jinja2Templates(directory="templates")

MINI_GAMES: dict = {
    "2048": {
        "title_key": "mg_2048_title",
        "src": "/static/games/2048/index.html",
    },
    "balloon-pop-maths": {
        "title_key": "mg_balloon_title",
        "src": "/static/games/balloon_pop_maths/index.html",
    },
    "catch-beaver": {
        "title_key": "mg_beaver_title",
        "src": "/static/games/catch_beaver/index.html",
    },
    "guess-number": {
        "title_key": "mg_guess_title",
        "src": "/static/games/guess_number/index.html",
    },
    "kids-english": {
        "title_key": "mg_english_title",
        "src": "/static/games/kids_english/index.html",
    },
    "maze": {
        "title_key": "mg_maze_title",
        "src": "/static/games/maze/index.html",
    },
    "minesweeper": {
        "title_key": "mg_minesweeper_title",
        "src": "/static/games/minesweeper/index.html",
    },
    "remember-colors": {
        "title_key": "mg_colors_title",
        "src": "/static/games/remember_colors/index.html",
    },
    "twins": {
        "title_key": "mg_twins_title",
        "src": "/static/games/twins/index.html",
    },
    "word-match": {
        "title_key": "mg_wordmatch_title",
        "src": "/static/games/word_match/index.html",
    },
}


# ── Play route ────────────────────────────────────────────────────────────────

@router.get("/teacher/games/mini/{game_id}", response_class=HTMLResponse)
async def teacher_mini_game_play(
    request: Request,
    game_id: str,
    teacher: Employee = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    game = MINI_GAMES.get(game_id)
    if game is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Game not found")

    ctx = await get_template_context(request, db)

    src = ROOT_PATH + game["src"]

    ctx.update({
        "game_id": game_id,
        "game_title_key": game["title_key"],
        "game_src": src,
    })
    return templates.TemplateResponse("teacher/games/mini_game_play.html", ctx)
