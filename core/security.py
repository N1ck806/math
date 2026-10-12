"""CSRF-токены и утилиты проверки ввода."""

from __future__ import annotations

import hmac
import math
import secrets
from typing import Any

from flask import session, abort, request

CSRF_FIELD = "_csrf_token"
CSRF_SESSION_KEY = "_csrf_token"
CSRF_HEADER = "X-CSRF-Token"


def get_csrf_token() -> str:
    """Возвращает токен CSRF, создавая его при необходимости."""
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def check_csrf() -> None:
    """Проверяет CSRF-токен в POST-запросе. Прерывает запрос 400 при ошибке."""
    if request.method != "POST":
        return

    sent = request.form.get(CSRF_FIELD) or request.headers.get(CSRF_HEADER, "")
    stored = session.get(CSRF_SESSION_KEY, "")

    if not sent or not stored or not hmac.compare_digest(str(sent), str(stored)):
        abort(400, description="Недействительный CSRF-токен.")


def safe_int(value: Any, default: int, lo: int, hi: int) -> int:
    """Приводит значение к int в заданных границах."""
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def safe_float(value: Any, default: float = 0.0) -> float:
    """Приводит значение к float, возвращает default при ошибке или NaN/inf."""
    if value is None:
        return default
    s = str(value).strip().replace(",", ".")
    if not s:
        return default
    try:
        v = float(s)
    except ValueError:
        return default
    if not math.isfinite(v):
        return default
    return v