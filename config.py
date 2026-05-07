import os
from datetime import timedelta
from starlette.responses import RedirectResponse as _BaseRedirect

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production')
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite+aiosqlite:///school_grading.db')
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    ITEMS_PER_PAGE = 50


# ── Root-path support for reverse-proxy deployments ──────────────────────────
# Set ROOT_PATH=/teacherpro (or whatever prefix Nginx uses) in your environment.
ROOT_PATH: str = os.environ.get("ROOT_PATH", "").rstrip("/")


class RedirectResponse(_BaseRedirect):
    """Drop-in replacement for starlette/fastapi RedirectResponse.
    Automatically prepends ROOT_PATH to any path that starts with '/'.
    This ensures redirects work correctly when the app is deployed under
    a URL prefix (e.g. /teacherpro) via a reverse proxy.
    """

    def __init__(self, url: str, status_code: int = 303, **kwargs):
        if ROOT_PATH and url.startswith("/"):
            url = ROOT_PATH + url
        super().__init__(url=url, status_code=status_code, **kwargs)