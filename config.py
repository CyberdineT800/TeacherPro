import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production')
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite+aiosqlite:///school_grading.db')
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    ITEMS_PER_PAGE = 50