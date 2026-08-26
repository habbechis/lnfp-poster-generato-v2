"""Firebase-backed store for saved data.

Kept deliberately small and defensive: if firebase-admin is not installed or
no credentials are configured, the accessors return ``None`` and the caller
falls back to the local JSON store. That means the app runs on Render
immediately and starts persisting to Firebase the moment credentials appear.

Two products are supported. If ``FIREBASE_DB_URL`` is set the app uses the
Realtime Database (RTDB); otherwise it uses Firestore. Both go through the
same Admin SDK app (one credential), so rules can stay locked — the service
account bypasses them.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache

_app = None
_fs_client = None
_rtdb_root = None
_init_error: str | None = None


# --------------------------------------------------------------------------- #
# Realtime Database over REST (legacy database secret)
# --------------------------------------------------------------------------- #
class RestReference:
    """A tiny stand-in for ``firebase_admin.db.Reference`` backed by the RTDB
    REST API and a legacy database secret. It exposes exactly the surface the
    store uses — ``child``/``get``/``set``/``delete`` — so it drops in for the
    Admin SDK reference without pulling in firebase-admin or a service account.
    The database secret is passed as ``?auth=`` and bypasses the rules, so the
    database rules can stay locked.
    """

    def __init__(self, base_url: str, secret: str, path: str = ""):
        self._base = base_url.rstrip("/")
        self._secret = secret
        self._path = path.strip("/")

    def child(self, key) -> "RestReference":
        key = str(key).strip("/")
        path = f"{self._path}/{key}" if self._path else key
        return RestReference(self._base, self._secret, path)

    def _url(self, **params) -> str:
        path = urllib.parse.quote(self._path, safe="/")
        leaf = f"{self._base}/{path}.json" if path else f"{self._base}/.json"
        query = {"auth": self._secret} if self._secret else {}
        query.update(params)
        return f"{leaf}?{urllib.parse.urlencode(query)}"

    def _request(self, method: str, value=None, **params):
        body = None
        headers = {}
        if value is not None:
            body = json.dumps(value, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(
            self._url(**params), data=body, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
        return json.loads(raw) if raw else None

    def get(self, shallow: bool = False):
        return self._request("GET", **({"shallow": "true"} if shallow else {}))

    def set(self, value):
        return self._request("PUT", value=value)

    def delete(self):
        return self._request("DELETE")


def get_rtdb_rest(config):
    """Return a REST-backed RTDB root reference, or ``None`` if not configured.

    Needs only ``FIREBASE_DB_URL`` + ``FIREBASE_DB_SECRET`` — no firebase-admin
    and no service account.
    """
    if not (config.FIREBASE_DB_URL and config.FIREBASE_DB_SECRET):
        return None
    return RestReference(config.FIREBASE_DB_URL, config.FIREBASE_DB_SECRET)


def _credential(config):
    """Build an Admin SDK credential from config, or (None, error)."""
    try:
        from firebase_admin import credentials
    except Exception as exc:  # pragma: no cover - library missing
        return None, f"firebase-admin not available: {exc}"
    if config.FIREBASE_CREDENTIALS_JSON:
        try:
            return credentials.Certificate(
                json.loads(config.FIREBASE_CREDENTIALS_JSON)), None
        except Exception as exc:
            return None, f"invalid FIREBASE_CREDENTIALS_JSON: {exc}"
    if config.GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(
            config.GOOGLE_APPLICATION_CREDENTIALS):
        return credentials.Certificate(
            config.GOOGLE_APPLICATION_CREDENTIALS), None
    return None, "no Firebase credentials configured"


@lru_cache(maxsize=1)
def _get_app(config):
    """Initialise (once) and return the Admin SDK app, or ``None``."""
    global _app, _init_error
    if _app is not None:
        return _app
    try:
        import firebase_admin
    except Exception as exc:  # pragma: no cover - library missing
        _init_error = f"firebase-admin not available: {exc}"
        return None
    cred, err = _credential(config)
    if cred is None:
        _init_error = err
        return None
    opts = {}
    if config.FIREBASE_DB_URL:
        opts["databaseURL"] = config.FIREBASE_DB_URL
    try:
        if firebase_admin._apps:
            _app = firebase_admin.get_app()
        else:
            _app = firebase_admin.initialize_app(cred, opts)
        return _app
    except Exception as exc:
        _init_error = f"firebase init failed: {exc}"
        return None


def get_client(config):
    """Return a Firestore client, or ``None`` if unavailable."""
    global _fs_client, _init_error
    if _fs_client is not None:
        return _fs_client
    app = _get_app(config)
    if app is None:
        return None
    try:
        from firebase_admin import firestore
        _fs_client = firestore.client(app)
        return _fs_client
    except Exception as exc:
        _init_error = f"firestore init failed: {exc}"
        return None


def get_rtdb(config):
    """Return the Realtime Database root reference, or ``None``."""
    global _rtdb_root, _init_error
    if _rtdb_root is not None:
        return _rtdb_root
    if not config.FIREBASE_DB_URL:
        return None
    app = _get_app(config)
    if app is None:
        return None
    try:
        from firebase_admin import db
        _rtdb_root = db.reference("/", app=app)
        return _rtdb_root
    except Exception as exc:
        _init_error = f"rtdb init failed: {exc}"
        return None


def last_error() -> str | None:
    return _init_error
