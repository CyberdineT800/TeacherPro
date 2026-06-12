"""Public mini-games routes — no login required.

GET /games         → hub page showing all 10 mini-game cards
GET /games/{id}    → standalone iframe player for a single game
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from config import ROOT_PATH
from dependencies import get_template_context
from models import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from routers.teacher.games.mini_games import MINI_GAMES

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/games", response_class=HTMLResponse)
async def public_games_hub(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ctx = await get_template_context(request, db)
    return templates.TemplateResponse("game/mini_games_hub.html", ctx)


@router.get("/games/{game_id}", response_class=HTMLResponse)
async def public_mini_game_play(
    request: Request,
    game_id: str,
    db: AsyncSession = Depends(get_db),
):
    game = MINI_GAMES.get(game_id)
    if game is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Game not found")

    ctx = await get_template_context(request, db)
    ctx.update({
        "game_id": game_id,
        "game_title_key": game["title_key"],
        "game_src": ROOT_PATH + game["src"],
    })
    return templates.TemplateResponse("game/mini_game_play.html", ctx)
