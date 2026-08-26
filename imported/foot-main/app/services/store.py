"""Persistence abstraction for saved data.

Presents one small CRUD surface to the rest of the app and hides where the
data lives: Firebase Realtime Database (RTDB), Firestore, or a local JSON
file. Backend selection follows ``Config.DB_BACKEND`` ("auto" | "firebase" |
"rtdb" | "local"); in "auto" it prefers RTDB when ``FIREBASE_DB_URL`` and
credentials are present, then Firestore, then the local file — so the app
always boots and starts persisting to Firebase the moment it is wired up.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid

from . import firebase_service

_lock = threading.Lock()

# RTDB keys may not contain these characters, so encode them for ids/usernames.
_RTDB_FORBIDDEN = {".": "%2E", "$": "%24", "#": "%23",
                   "[": "%5B", "]": "%5D", "/": "%2F"}


def _rtdb_key(value) -> str:
    s = str(value)
    for ch, rep in _RTDB_FORBIDDEN.items():
        s = s.replace(ch, rep)
    return s


class Store:
    def __init__(self, config):
        self.config = config
        self.collection = config.FIRESTORE_COLLECTION
        self.admin_collection = config.FIRESTORE_ADMIN_COLLECTION
        self._fs = None
        self._rtdb = None
        backend = (config.DB_BACKEND or "auto").lower()
        if backend in ("auto", "firebase", "rtdb"):
            # Prefer the Realtime Database when a database URL is configured.
            # A legacy database secret (REST) is tried first — it needs no
            # service account — then the Admin SDK (service-account) path.
            if config.FIREBASE_DB_URL:
                self._rtdb = firebase_service.get_rtdb_rest(config)
                if self._rtdb is None:
                    self._rtdb = firebase_service.get_rtdb(config)
            if self._rtdb is None and backend != "rtdb":
                self._fs = firebase_service.get_client(config)
            if backend in ("firebase", "rtdb") and self._rtdb is None \
                    and self._fs is None:
                raise RuntimeError(
                    f"DB_BACKEND={backend} but Firebase is unavailable: "
                    f"{firebase_service.last_error()}")

    # -- introspection ----------------------------------------------------
    @property
    def backend(self) -> str:
        if self._rtdb is not None:
            return "rtdb"
        if self._fs is not None:
            return "firebase"
        return "local"

    def status(self) -> dict:
        return {
            "backend": self.backend,
            "firebase_error": firebase_service.last_error()
            if self.backend == "local" else None,
            "collection": self.collection,
        }

    def ping(self) -> tuple[bool, str]:
        """Live connectivity check for the heartbeat indicator.

        Returns ``(connected, detail)``. "Connected" means a remote Firebase
        backend answered a light request; the local JSON fallback reports
        ``False`` so the UI shows that persistence is not durable.
        """
        try:
            if self._rtdb is not None:
                self._rtdb.get(shallow=True)
                return True, "rtdb"
            if self._fs is not None:
                next(iter(self._fs.collection(self.collection)
                          .limit(1).stream()), None)
                return True, "firebase"
        except Exception as exc:  # network / auth / library failure
            return False, str(exc)
        return False, firebase_service.last_error() or "local"

    # -- match-days -------------------------------------------------------
    def list_matchdays(self) -> list[dict]:
        if self._rtdb is not None:
            data = self._rtdb.child(self.collection).get() or {}
            return sorted(data.values(),
                          key=lambda m: m.get("updated_at", 0), reverse=True)
        if self._fs is not None:
            docs = (self._fs.collection(self.collection)
                    .order_by("updated_at", direction="DESCENDING").stream())
            return [{**d.to_dict(), "id": d.id} for d in docs]
        return sorted(self._read_local().values(),
                      key=lambda m: m.get("updated_at", 0), reverse=True)

    def get_matchday(self, mid: str) -> dict | None:
        if self._rtdb is not None:
            return self._rtdb.child(self.collection).child(_rtdb_key(mid)).get()
        if self._fs is not None:
            doc = self._fs.collection(self.collection).document(mid).get()
            return {**doc.to_dict(), "id": doc.id} if doc.exists else None
        return self._read_local().get(mid)

    def save_matchday(self, data: dict) -> dict:
        now = time.time()
        mid = data.get("id") or uuid.uuid4().hex[:12]
        record = {
            "id": mid,
            "title": data.get("title", ""),
            "date_label": data.get("date_label", ""),
            "date_iso": data.get("date_iso", ""),
            "competition": data.get("competition", ""),
            "brand_logo": data.get("brand_logo", ""),
            "mode": data.get("mode", "fixtures"),
            "title_image": data.get("title_image", ""),
            "matches": data.get("matches", []),
            "updated_at": now,
            "created_at": data.get("created_at", now),
        }
        if self._rtdb is not None:
            self._rtdb.child(self.collection).child(_rtdb_key(mid)).set(record)
        elif self._fs is not None:
            self._fs.collection(self.collection).document(mid).set(record)
        else:
            with _lock:
                db = self._read_local()
                db[mid] = record
                self._write_local(db)
        return record

    def delete_matchday(self, mid: str) -> bool:
        if self._rtdb is not None:
            self._rtdb.child(self.collection).child(_rtdb_key(mid)).delete()
            return True
        if self._fs is not None:
            self._fs.collection(self.collection).document(mid).delete()
            return True
        with _lock:
            db = self._read_local()
            if mid in db:
                del db[mid]
                self._write_local(db)
                return True
        return False

    # -- standings (one document per league / pool) -----------------------
    # Keyed by squad id ("ligue1", "l2-pool1", "l2-pool2") so each league keeps
    # exactly one live table that is overwritten on save.
    def _standings_collection(self) -> str:
        return f"{self.collection}_standings"

    def get_standing(self, league: str) -> dict | None:
        if self._rtdb is not None:
            return (self._rtdb.child(self._standings_collection())
                    .child(_rtdb_key(league)).get())
        if self._fs is not None:
            doc = (self._fs.collection(self._standings_collection())
                   .document(league).get())
            return {**doc.to_dict(), "league": doc.id} if doc.exists else None
        return self._read_standings().get(league)

    def save_standing(self, league: str, data: dict) -> dict:
        now = time.time()
        record = {
            "league": league,
            "title": data.get("title", ""),
            "subtitle": data.get("subtitle", ""),
            "rows": data.get("rows", []),
            "updated_at": now,
        }
        if self._rtdb is not None:
            (self._rtdb.child(self._standings_collection())
             .child(_rtdb_key(league)).set(record))
        elif self._fs is not None:
            (self._fs.collection(self._standings_collection())
             .document(league).set(record))
        else:
            with _lock:
                db = self._read_standings()
                db[league] = record
                self._write_standings(db)
        return record

    def _standings_path(self) -> str:
        base = self.config.LOCAL_DB_PATH
        root, ext = os.path.splitext(base)
        return f"{root}-standings{ext or '.json'}"

    def _read_standings(self) -> dict:
        return self._read_json(self._standings_path())

    def _write_standings(self, db: dict) -> None:
        self._write_json(self._standings_path(), db)

    # -- admin accounts ---------------------------------------------------
    # Kept in their own collection/file so poster data and credentials never
    # share a document.
    def list_admins(self) -> list[dict]:
        if self._rtdb is not None:
            data = self._rtdb.child(self.admin_collection).get() or {}
            return list(data.values())
        if self._fs is not None:
            docs = self._fs.collection(self.admin_collection).stream()
            return [{**d.to_dict(), "username": d.id} for d in docs]
        return list(self._read_admins().values())

    def get_admin(self, username: str) -> dict | None:
        if self._rtdb is not None:
            return (self._rtdb.child(self.admin_collection)
                    .child(_rtdb_key(username)).get())
        if self._fs is not None:
            doc = self._fs.collection(self.admin_collection).document(username).get()
            return {**doc.to_dict(), "username": doc.id} if doc.exists else None
        return self._read_admins().get(username)

    def put_admin(self, record: dict) -> dict:
        username = record["username"]
        if self._rtdb is not None:
            (self._rtdb.child(self.admin_collection)
             .child(_rtdb_key(username)).set(record))
        elif self._fs is not None:
            self._fs.collection(self.admin_collection).document(username).set(record)
        else:
            with _lock:
                db = self._read_admins()
                db[username] = record
                self._write_admins(db)
        return record

    def delete_admin(self, username: str) -> bool:
        if self._rtdb is not None:
            (self._rtdb.child(self.admin_collection)
             .child(_rtdb_key(username)).delete())
            return True
        if self._fs is not None:
            self._fs.collection(self.admin_collection).document(username).delete()
            return True
        with _lock:
            db = self._read_admins()
            if username in db:
                del db[username]
                self._write_admins(db)
                return True
        return False

    def _admin_path(self) -> str:
        base = self.config.LOCAL_DB_PATH
        root, ext = os.path.splitext(base)
        return f"{root}-admins{ext or '.json'}"

    def _read_admins(self) -> dict:
        return self._read_json(self._admin_path())

    def _write_admins(self, db: dict) -> None:
        self._write_json(self._admin_path(), db)

    # -- local JSON backend ----------------------------------------------
    def _read_local(self) -> dict:
        return self._read_json(self.config.LOCAL_DB_PATH)

    def _write_local(self, db: dict) -> None:
        self._write_json(self.config.LOCAL_DB_PATH, db)

    @staticmethod
    def _read_json(path: str) -> dict:
        if not os.path.exists(path):
            return {}
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return {}

    @staticmethod
    def _write_json(path: str, db: dict) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(db, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
