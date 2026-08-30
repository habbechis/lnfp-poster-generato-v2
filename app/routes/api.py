"""JSON API and poster rendering endpoints."""
from __future__ import annotations

import io
import os
import re
import traceback
import zipfile

from flask import Blueprint, Response, current_app, jsonify, request

from ..auth import require_auth
from ..services import fixtures_parser, livescore, poster, results_parser
from ..services.dates import arabic_date_label
from ..services.teams import (all_channels, all_competitions, all_teams,
                             channel_logos, combined_channel_logo, get_team,
                             max_channels_per_match, squad_meta, team_side,
                             teams_for)

bp = Blueprint("api", __name__)

BACKGROUNDS = {"bg-vide.png", "bg-ligue2.png"}
STANDING_LEAGUES = {"ligue1", "l2-pool1", "l2-pool2"}

DEFAULT_TITLE = "تعيينات مباريات\nالجولة الأولى ذهاب\nلبطولة الرابطة 1"


# --------------------------------------------------------------------------- #
# Reference data
# --------------------------------------------------------------------------- #
@bp.get("/teams")
@require_auth
def teams():
    return jsonify(all_teams())


@bp.get("/competitions")
@require_auth
def competitions():
    return jsonify(all_competitions())


@bp.get("/channels")
@require_auth
def channels():
    return jsonify({"channels": all_channels(),
                    "max_per_match": max_channels_per_match()})


@bp.get("/fonts")
@require_auth
def fonts():
    """Title faces the studio may offer (Arabic-capable, present on disk)."""
    return jsonify(poster.available_title_fonts())


@bp.get("/team/<code>")
@require_auth
def team(code):
    t = get_team(code)
    return (jsonify(t), 200) if t else (jsonify({"error": "not found"}), 404)


@bp.get("/diag")
@require_auth
def diag():
    """Browser-visitable diagnostic: reports Pillow/raqm and attempts a render,
    returning the full traceback as plain text if it fails. Temporary."""
    lines = []
    try:
        import PIL
        from PIL import features
        lines.append(f"Pillow {PIL.__version__}")
        for f in ("raqm", "harfbuzz", "fribidi", "freetype2"):
            lines.append(f"  {f}: {features.check(f)}")
    except Exception as exc:
        lines.append(f"features error: {exc}")
    lines.append("")
    try:
        data = poster.render_png_bytes(
            "تعيينات مباريات\nالجولة الأولى",
            "الأحد 23 أوت 2026",
            [{"home": {"name_ar": "الترجي الرياضي التونسي", "logo": "est.png"},
              "away": {"name_ar": "النجم الرياضي الساحلي", "logo": "ess.png"},
              "time": "16:30", "stadium_ar": "حمادي العقربي برادس"}],
            scale=0.4)
        lines.append(f"RENDER OK — {len(data)} bytes")
    except Exception:
        lines.append("RENDER FAILED:")
        lines.append(traceback.format_exc())
    return Response("\n".join(lines), mimetype="text/plain")


@bp.get("/db-status")
@require_auth
def db_status():
    """Live database heartbeat for the sidebar dot and the admin panel pill."""
    connected, detail = current_app.store.ping()
    return jsonify({"connected": connected,
                    "backend": current_app.store.backend,
                    "detail": detail})


# --------------------------------------------------------------------------- #
# Pasted results bulletin -> matches + standings
# --------------------------------------------------------------------------- #
@bp.post("/parse-results")
@require_auth
def parse_results():
    payload = request.get_json(force=True, silent=True) or {}
    squad = payload.get("squad") or "ligue1"
    return jsonify(results_parser.parse(payload.get("text", ""), squad))


@bp.post("/parse-fixtures")
@require_auth
def parse_fixtures():
    """Scheduled-round bulletin, pasted as text or uploaded as a PDF."""
    upload = request.files.get("file")
    if upload is not None:
        squad = request.form.get("squad") or "ligue1"
        text, err = fixtures_parser.text_from_pdf(upload.stream)
        if err:
            return jsonify({"error": err}), 400
    else:
        payload = request.get_json(force=True, silent=True) or {}
        squad = payload.get("squad") or "ligue1"
        text = payload.get("text", "")
    return jsonify(fixtures_parser.parse(text, squad))


# --------------------------------------------------------------------------- #
# Live scoring (API-Football) — optional; degrades to "not configured"
# --------------------------------------------------------------------------- #
@bp.get("/live/status")
@require_auth
def live_status():
    return jsonify(livescore.status(current_app.config_object))


@bp.get("/live/scoreboard")
@require_auth
def live_scoreboard():
    return jsonify(livescore.live(current_app.config_object))


@bp.get("/live/fixtures")
@require_auth
def live_fixtures():
    return jsonify(livescore.fixtures_on(
        current_app.config_object, request.args.get("date", "")))


@bp.get("/live/standings")
@require_auth
def live_standings():
    return jsonify(livescore.standings(current_app.config_object))


@bp.get("/status")
@require_auth
def status():
    data = current_app.store.status()
    try:
        import PIL
        from PIL import features
        data["pillow"] = {
            "version": PIL.__version__,
            "raqm": features.check("raqm"),
            "harfbuzz": features.check("harfbuzz"),
            "fribidi": features.check("fribidi"),
        }
    except Exception as exc:  # pragma: no cover - diagnostics only
        data["pillow"] = {"error": str(exc)}
    data["fonts"] = {
        "text": os.path.basename(poster.TEXT_FONT_PATH),
        "time": os.path.basename(poster.TIME_FONT_PATH),
    }
    data["font"] = os.path.basename(poster.TEXT_FONT_PATH)  # legacy key
    return jsonify(data)


# --------------------------------------------------------------------------- #
# Payload -> normalised render model
# --------------------------------------------------------------------------- #
def _build_render_model(payload: dict) -> dict:
    title = (payload.get("title") or DEFAULT_TITLE).strip()
    date_iso = (payload.get("date_iso") or "").strip()
    date_label = payload.get("date_label") or arabic_date_label(date_iso)
    brand_logo = (payload.get("brand_logo") or "").strip() or None
    background = (payload.get("background") or "").strip()
    background = background if background in BACKGROUNDS else None

    try:
        title_size = float(payload.get("title_size"))
    except (TypeError, ValueError):
        title_size = 1.0
    title_size = min(1.6, max(0.6, title_size))
    title_font = payload.get("title_font")
    if title_font not in poster.TITLE_FONTS:
        title_font = None
    mode = "results" if payload.get("mode") == "results" else "fixtures"
    # Auto mode supplies ready title artwork; manual mode leaves it empty and
    # the typed text is rendered instead.
    title_image = payload.get("title_image")
    if title_image not in poster.TITLE_IMAGES:
        title_image = None

    matches = []
    for m in payload.get("matches", []):
        home_code = m.get("home")
        away_code = m.get("away")
        if not home_code or not away_code:
            continue
        home = team_side(home_code)
        away = team_side(away_code)
        home["logo_dir"] = home.pop("logo_dir", "logos")
        away["logo_dir"] = away.pop("logo_dir", "logos")
        rec = {"home": home, "away": away}
        if mode == "results":
            sh = _digits(m.get("score_home")) or "0"
            sa = _digits(m.get("score_away")) or "0"
            rec["score"] = f"{sh} - {sa}"
        else:
            # Stadium: explicit override, else the home team's home ground.
            stadium = (m.get("stadium_ar") or "").strip()
            if not stadium:
                ht = get_team(home_code) or {}
                stadium = ht.get("stadium_ar", "")
            rec["time"] = (m.get("time") or "16:30").strip()
            rec["stadium_ar"] = stadium
            # Codes come in from the UI; the renderer wants file names. A ready
            # combined banner is preferred when the picked set matches one;
            # the individual logos stay as a fallback if it is missing.
            rec["channels"] = channel_logos(m.get("channels"))
            rec["channels_combined"] = combined_channel_logo(m.get("channels"))
        matches.append(rec)
    return {"title": title, "date_label": date_label, "matches": matches,
            "brand_logo": brand_logo, "background": background,
            "title_size": title_size, "title_font": title_font, "mode": mode,
            "title_image": title_image}


def _digits(value) -> str:
    """Keep at most two digits from a user-typed score cell."""
    return re.sub(r"\D", "", str(value or ""))[:2]


def _slug(text: str) -> str:
    text = re.sub(r"\s+", "-", (text or "").strip())
    return re.sub(r"[^0-9A-Za-z\-]", "", text) or "poster"
# ---------------------------------------------------------------------------
# ضيف هذا الكود فـ app/routes/api.py
# مكان الحطة: بعد دالة _slug() وقبل قسم "# Poster rendering" — أو أي مكان
# بعد الـ imports وقبل أول استعمال. يستعمل نفس الأدوات الموجودة فوقو بالملف
# (team_side, poster, _render_error, _slug, request, jsonify, Response...).
# ---------------------------------------------------------------------------

def _build_kickoff_model(payload: dict) -> dict:
    """Same shape fixtures_parser.parse() returns, plus a matchweek number.

    Payload:
      {"matchweek": 3, "brand_logo": "...", "background": "...",
       "days": [{"date_label": "...",
                 "matches": [{"home": "EST", "away": "ESS", "time": "16:30"},
                             ...]}, ...]}
    Team codes are resolved the same way the fixtures poster does.
    """
    try:
        matchweek = int(payload.get("matchweek") or 1)
    except (TypeError, ValueError):
        matchweek = 1
    brand_logo = (payload.get("brand_logo") or "").strip() or None
    background = (payload.get("background") or "").strip()
    background = background if background in BACKGROUNDS else None

    days = []
    for d in payload.get("days", []):
        matches = []
        for m in d.get("matches", []):
            home_code, away_code = m.get("home"), m.get("away")
            if not home_code or not away_code:
                continue
            home = team_side(home_code)
            away = team_side(away_code)
            home["logo_dir"] = home.pop("logo_dir", "logos")
            away["logo_dir"] = away.pop("logo_dir", "logos")
            matches.append({"home": home, "away": away,
                            "time": (m.get("time") or "16:30").strip()})
        if matches:
            days.append({"date_label": (d.get("date_label") or "").strip(),
                        "matches": matches})

    return {"matchweek": matchweek, "brand_logo": brand_logo,
            "background": background, "days": days}


@bp.post("/kickoff/preview")
@require_auth
def kickoff_preview():
    """Render a downscaled PNG for the live on-screen preview."""
    model = _build_kickoff_model(request.get_json(force=True, silent=True) or {})
    if not model["days"]:
        return jsonify({"error": "add at least one match"}), 400
    try:
        png = poster.render_kickoff_png_bytes(
            model["matchweek"], model["days"],
            brand_logo=model["brand_logo"], background=model["background"],
            scale=0.55)
    except Exception as exc:
        return _render_error(exc)
    return Response(png, mimetype="image/png",
                    headers={"Cache-Control": "no-store"})


@bp.post("/kickoff/generate")
@require_auth
def kickoff_generate():
    """Render the full-resolution PNG and offer it as a download."""
    payload = request.get_json(force=True, silent=True) or {}
    model = _build_kickoff_model(payload)
    if not model["days"]:
        return jsonify({"error": "add at least one match"}), 400
    try:
        png = poster.render_kickoff_png_bytes(
            model["matchweek"], model["days"],
            brand_logo=model["brand_logo"], background=model["background"],
            scale=1.0)
    except Exception as exc:
        return _render_error(exc)
    fname = f"lnfp-kickoff-{model['matchweek']}.png"
    return Response(png, mimetype="image/png", headers={
        "Content-Disposition": f'attachment; filename="{fname}"',
        "Cache-Control": "no-store",
    })


# --------------------------------------------------------------------------- #
# Poster rendering
# --------------------------------------------------------------------------- #
def _render_error(exc):
    """500 payload; includes the traceback only when DIAG=1 is set."""
    current_app.logger.exception("poster rendering failed")
    body = {"error": "rendering failed"}
    if os.environ.get("DIAG") == "1":
        body["detail"] = str(exc)
        body["trace"] = traceback.format_exc()
    return jsonify(body), 500


@bp.post("/preview")
@require_auth
def preview():
    """Render a downscaled PNG for the live on-screen preview."""
    model = _build_render_model(request.get_json(force=True, silent=True) or {})
    if not model["matches"]:
        return jsonify({"error": "add at least one match"}), 400
    try:
        png = poster.render_png_bytes(
            model["title"], model["date_label"], model["matches"],
            brand_logo=model["brand_logo"], background=model["background"],
            title_size=model["title_size"], title_font=model["title_font"],
            title_image=model["title_image"], mode=model["mode"],
            scale=0.55)
    except Exception as exc:
        return _render_error(exc)
    return Response(png, mimetype="image/png",
                    headers={"Cache-Control": "no-store"})


@bp.post("/generate")
@require_auth
def generate():
    """Render the full-resolution PNG and offer it as a download."""
    payload = request.get_json(force=True, silent=True) or {}
    model = _build_render_model(payload)
    if not model["matches"]:
        return jsonify({"error": "add at least one match"}), 400
    try:
        png = poster.render_png_bytes(
            model["title"], model["date_label"], model["matches"],
            brand_logo=model["brand_logo"], background=model["background"],
            title_size=model["title_size"], title_font=model["title_font"],
            title_image=model["title_image"], mode=model["mode"],
            scale=1.0)
    except Exception as exc:
        return _render_error(exc)
    fname = f"lnfp-{_slug(payload.get('date_iso') or 'affiche')}.png"
    return Response(png, mimetype="image/png", headers={
        "Content-Disposition": f'attachment; filename="{fname}"',
        "Cache-Control": "no-store",
    })


# --------------------------------------------------------------------------- #
# Standings (one editable table per league / pool)
# --------------------------------------------------------------------------- #
def _clean_points(value) -> int:
    try:
        return max(0, min(999, int(value)))
    except (TypeError, ValueError):
        return 0


def _clean_played(value) -> int:
    try:
        return max(0, min(99, int(value)))
    except (TypeError, ValueError):
        return 0


def _page_slice(rows: list, page: int):
    """Split a table into two halves; return (rows_on_page, rank_of_first)."""
    per = (len(rows) + 1) // 2          # ceil half on page 1
    if page == 2:
        return rows[per:], per + 1
    return rows[:per], 1


def _standings_rows(league: str, rows) -> list[dict]:
    """Keep only real teams of ``league``, in the given order, deduplicated."""
    valid = {t["code"] for t in teams_for(league)}
    out, seen = [], set()
    for r in rows or []:
        code = r.get("code")
        if code in valid and code not in seen:
            seen.add(code)
            out.append({"code": code, "points": _clean_points(r.get("points")),
                        "played": _clean_played(r.get("played"))})
    return out


def _standings_render_model(payload: dict) -> dict:
    league = payload.get("league")
    if league not in STANDING_LEAGUES:
        league = "ligue1"
    meta = squad_meta(league)
    title = (payload.get("title") or "الترتيب العام").strip()
    subtitle = (payload.get("subtitle") or "").strip()
    rows = []
    for r in _standings_rows(league, payload.get("rows")):
        t = get_team(r["code"]) or {}
        rows.append({"name_ar": t.get("name_ar", ""), "logo": t.get("logo", ""),
                     "logo_dir": t.get("_logos", "logos"),
                     "points": r["points"], "played": r["played"]})
    return {"meta": meta, "title": title, "subtitle": subtitle, "rows": rows}


@bp.get("/standings/<league>")
@require_auth
def get_standings(league):
    if league not in STANDING_LEAGUES:
        return jsonify({"error": "unknown league"}), 404
    saved = current_app.store.get_standing(league)
    return jsonify(saved or {"league": league, "rows": []})


@bp.post("/standings")
@require_auth
def save_standings():
    payload = request.get_json(force=True, silent=True) or {}
    league = payload.get("league")
    if league not in STANDING_LEAGUES:
        return jsonify({"error": "unknown league"}), 400
    record = current_app.store.save_standing(league, {
        "title": (payload.get("title") or "").strip(),
        "subtitle": (payload.get("subtitle") or "").strip(),
        "rows": _standings_rows(league, payload.get("rows")),
    })
    return jsonify(record), 201


def _render_standings(payload, scale, page=1):
    model = _standings_render_model(payload)
    meta = model["meta"]
    # Split the table into two pages so each is large and readable.
    rows, start = _page_slice(model["rows"], page)
    if not rows:                                   # page beyond the data
        rows, start = model["rows"], 1
    return poster.render_standings_png_bytes(
        model["title"], model["subtitle"], rows,
        brand_logo=meta["brand"], background=meta["background"],
        title_image="title-ranking.png", start_rank=start, scale=scale)


def _page_arg(payload) -> int:
    return 2 if str(payload.get("page")) == "2" else 1


@bp.post("/standings/preview")
@require_auth
def standings_preview():
    payload = request.get_json(force=True, silent=True) or {}
    if not payload.get("rows"):
        return jsonify({"error": "no rows"}), 400
    try:
        png = _render_standings(payload, scale=0.55, page=_page_arg(payload))
    except Exception as exc:
        return _render_error(exc)
    return Response(png, mimetype="image/png",
                    headers={"Cache-Control": "no-store"})


@bp.post("/standings/generate")
@require_auth
def standings_generate():
    payload = request.get_json(force=True, silent=True) or {}
    if not payload.get("rows"):
        return jsonify({"error": "no rows"}), 400
    page = _page_arg(payload)
    try:
        png = _render_standings(payload, scale=1.0, page=page)
    except Exception as exc:
        return _render_error(exc)
    league = payload.get("league") if payload.get("league") in STANDING_LEAGUES \
        else "ligue1"
    return Response(png, mimetype="image/png", headers={
        "Content-Disposition":
            f'attachment; filename="classement-{league}-{page}.png"',
        "Cache-Control": "no-store",
    })


@bp.post("/standings/generate_all")
@require_auth
def standings_generate_all():
    """Both pages of the table bundled into one ZIP — a single download."""
    payload = request.get_json(force=True, silent=True) or {}
    if not payload.get("rows"):
        return jsonify({"error": "no rows"}), 400
    league = payload.get("league") if payload.get("league") in STANDING_LEAGUES \
        else "ligue1"
    n = len(_standings_rows(league, payload.get("rows")))
    pages = 2 if n > (n + 1) // 2 else 1     # two pages once the table splits
    try:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for page in range(1, pages + 1):
                png = _render_standings(payload, scale=1.0, page=page)
                zf.writestr(f"classement-{league}-{page}.png", png)
    except Exception as exc:
        return _render_error(exc)
    return Response(buf.getvalue(), mimetype="application/zip", headers={
        "Content-Disposition": f'attachment; filename="classement-{league}.zip"',
        "Cache-Control": "no-store",
    })


# --------------------------------------------------------------------------- #
# Saved match-days (Firebase / local)
# --------------------------------------------------------------------------- #
@bp.get("/matchdays")
@require_auth
def list_matchdays():
    return jsonify(current_app.store.list_matchdays())


@bp.get("/matchdays/<mid>")
@require_auth
def get_matchday(mid):
    md = current_app.store.get_matchday(mid)
    return (jsonify(md), 200) if md else (jsonify({"error": "not found"}), 404)


@bp.post("/matchdays")
@require_auth
def save_matchday():
    payload = request.get_json(force=True, silent=True) or {}
    payload["date_label"] = payload.get("date_label") or arabic_date_label(
        payload.get("date_iso", ""))
    record = current_app.store.save_matchday(payload)
    return jsonify(record), 201


@bp.delete("/matchdays/<mid>")
@require_auth
def delete_matchday(mid):
    ok = current_app.store.delete_matchday(mid)
    return (jsonify({"deleted": mid}), 200) if ok else (
        jsonify({"error": "not found"}), 404)
