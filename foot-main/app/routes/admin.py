"""Super-administrator area: login, control panel and account management."""
from __future__ import annotations

import time
from functools import wraps

from flask import (Blueprint, current_app, jsonify, redirect, render_template,
                   request, session, url_for)

from ..auth import (ROLE_ADMIN, ROLE_SUPER, current_user, require_super,
                    sign_in)
from ..services.admins import ACTIVE, SUSPENDED, generate_password
from ..services.teams import all_competitions

bp = Blueprint("admin", __name__)

# Simple in-process throttle: enough to blunt online guessing without adding a
# dependency. Keyed by client address.
_FAILURES: dict[str, list[float]] = {}
_MAX_ATTEMPTS = 6
_WINDOW = 300.0      # seconds


def _landing_with_error(msg: str, code: int):
    """Re-render the chooser with the sign-in panel open and an error shown."""
    comps = {c["code"]: c for c in all_competitions()}
    leagues = [comps[c] for c in ("ligue1", "ligue2") if c in comps]
    return render_template("landing.html", leagues=leagues, error=msg,
                           user=current_user()), code


def _client() -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    return (fwd.split(",")[0].strip() or request.remote_addr or "?")


def _throttled(key: str) -> bool:
    now = time.time()
    hits = [t for t in _FAILURES.get(key, []) if now - t < _WINDOW]
    _FAILURES[key] = hits
    return len(hits) >= _MAX_ATTEMPTS


def _record_failure(key: str) -> None:
    _FAILURES.setdefault(key, []).append(time.time())


# --------------------------------------------------------------------------- #
# Session
# --------------------------------------------------------------------------- #
@bp.post("/admin/login")
def login():
    data = request.form if request.form else (request.get_json(silent=True) or {})
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    wants_json = request.is_json or request.headers.get("Accept", "").startswith(
        "application/json")
    key = _client()

    if _throttled(key):
        msg = "محاولات كثيرة. أعد المحاولة بعد قليل."
        return ((jsonify({"error": msg}), 429) if wants_json
                else _landing_with_error(msg, 429))

    # Both roles land on the competition chooser; the super administrator
    # reaches the control panel from the button there.
    target = None
    if current_app.admins.check_super(username, password):
        sign_in(username, ROLE_SUPER)
        target = url_for("views.landing")
    elif current_app.admins.check_admin(username, password):
        sign_in(username, ROLE_ADMIN)
        target = url_for("views.landing")

    if target:
        _FAILURES.pop(key, None)
        return (jsonify({"ok": True, "redirect": target})
                if wants_json else redirect(target))

    _record_failure(key)
    msg = "بيانات الدخول غير صحيحة."
    return ((jsonify({"error": msg}), 401) if wants_json
            else _landing_with_error(msg, 401))


@bp.post("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("views.landing"))


@bp.get("/api/me")
def me():
    """Who is signed in — used by the front-end to shape the chrome."""
    return jsonify(current_user() or {})


# --------------------------------------------------------------------------- #
# Control panel
# --------------------------------------------------------------------------- #
@bp.get("/admin")
@require_super
def panel():
    return render_template("admin.html",
                           super_user=(current_user() or {}).get("username", ""))


# --------------------------------------------------------------------------- #
# Account API (super admin only)
# --------------------------------------------------------------------------- #
@bp.get("/api/admins")
@require_super
def list_admins():
    svc = current_app.admins
    return jsonify({"admins": svc.list(), "counts": svc.counts()})


@bp.get("/api/admins/password")
@require_super
def suggest_password():
    return jsonify({"password": generate_password(16)})


@bp.post("/api/admins")
@require_super
def create_admin():
    payload = request.get_json(silent=True) or {}
    try:
        record, created = current_app.admins.create_or_reset(
            payload.get("username", ""), payload.get("password", ""))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"admin": record, "created": created}), (201 if created else 200)


@bp.post("/api/admins/<username>/status")
@require_super
def set_status(username):
    payload = request.get_json(silent=True) or {}
    status = SUSPENDED if payload.get("status") == SUSPENDED else ACTIVE
    try:
        return jsonify({"admin": current_app.admins.set_status(username, status)})
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@bp.delete("/api/admins/<username>")
@require_super
def delete_admin(username):
    ok = current_app.admins.delete(username)
    return (jsonify({"deleted": username}) if ok
            else (jsonify({"error": "الحساب غير موجود"}), 404))
