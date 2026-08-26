"""Session helpers and route guards.

Two roles share one session: ``super`` may manage accounts and use the studio,
``admin`` may use the studio only. Everything except the landing page, the
sign-in endpoint, the health check and static files requires one of them.
"""
from __future__ import annotations

from functools import wraps

from flask import jsonify, redirect, request, session, url_for

SESSION_USER = "user"
SESSION_ROLE = "role"      # "super" | "admin"
ROLE_SUPER = "super"
ROLE_ADMIN = "admin"


def sign_in(username: str, role: str) -> None:
    session.clear()
    session[SESSION_USER] = username
    session[SESSION_ROLE] = role
    session.permanent = True


def current_user() -> dict | None:
    user = session.get(SESSION_USER)
    if not user:
        return None
    return {"username": user, "role": session.get(SESSION_ROLE, ROLE_ADMIN)}


def is_super() -> bool:
    return session.get(SESSION_ROLE) == ROLE_SUPER


def _deny():
    """401 for API callers, back to the sign-in page for everyone else."""
    if request.path.startswith("/api/"):
        return jsonify({"error": "unauthorised"}), 401
    return redirect(url_for("views.landing"))


def require_auth(view):
    """Any signed-in account."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get(SESSION_USER):
            return _deny()
        return view(*args, **kwargs)
    return wrapper


def require_super(view):
    """The super administrator only."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not is_super():
            return _deny()
        return view(*args, **kwargs)
    return wrapper
