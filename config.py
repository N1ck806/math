"""Конфигурация Flask-приложения."""

import os
import secrets
from dotenv import load_dotenv

load_dotenv()


class Config:
    # --- Безопасность ---
    # Ключ читается из переменной окружения. Если её нет, генерируем
    # случайный ключ на время жизни процесса — это безопаснее, чем
    # хардкод, но не сохраняет сессии между перезапусками.
    _env_key = os.environ.get("FLASK_SECRET_KEY")
    if not _env_key or len(_env_key) < 32:
        # В продакшене обязательно задайте FLASK_SECRET_KEY в .env.
        _env_key = secrets.token_urlsafe(48)
    SECRET_KEY = _env_key

    # --- Cookies ---
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"
    SESSION_COOKIE_NAME = "mnk_session"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8  # 8 часов

    # --- Кодировка / JSON ---
    JSON_AS_ASCII = False
    JSONIFY_PRETTYPRINT_REGULAR = False

    # --- Ограничения запроса ---
    MAX_CONTENT_LENGTH = 256 * 1024  # 256 КБ на запрос

    # --- Отладка ---
    DEBUG = os.environ.get("FLASK_ENV") == "development"
    TESTING = False