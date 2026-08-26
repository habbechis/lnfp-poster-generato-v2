"""Administrator accounts.

Passwords are only ever stored as PBKDF2 hashes (via Werkzeug, which ships
with Flask); the plaintext exists just long enough to be shown once to the
super administrator who created or reset it.
"""
from __future__ import annotations

import logging
import secrets
import string
import time

from werkzeug.security import check_password_hash, generate_password_hash

log = logging.getLogger(__name__)

ACTIVE = "active"
SUSPENDED = "suspended"

# Ambiguous glyphs are left out so a generated password can be read aloud or
# copied off a screen without confusion.
_ALPHABET = (
    "".join(c for c in string.ascii_uppercase if c not in "IO") +
    "".join(c for c in string.ascii_lowercase if c not in "l") +
    "".join(c for c in string.digits if c not in "01") +
    "!@#$%*?-_"
)

MIN_PASSWORD_LEN = 8


def generate_password(length: int = 16) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def public(record: dict) -> dict:
    """The safe view of an account — never includes the hash."""
    return {
        "username": record.get("username", ""),
        "status": record.get("status", ACTIVE),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "last_login": record.get("last_login"),
    }


class AdminService:
    def __init__(self, store, config):
        self.store = store
        self.config = config
        self.super_user = (config.SUPER_ADMIN_USER or "superadmin").strip()
        password = config.SUPER_ADMIN_PASSWORD
        self._generated = not password
        if self._generated:
            password = generate_password(18)
            log.warning(
                "SUPER_ADMIN_PASSWORD is not set. Generated a temporary "
                "password for %r: %s  — set the environment variable to keep "
                "a stable one.", self.super_user, password)
        self._super_hash = generate_password_hash(password)

    # -- authentication ---------------------------------------------------
    def check_super(self, username: str, password: str) -> bool:
        """Verify the super-admin credentials in constant time."""
        expected = secrets.compare_digest((username or "").strip(),
                                          self.super_user)
        # Always run the hash comparison so a wrong username and a wrong
        # password cost the same.
        ok = check_password_hash(self._super_hash, password or "")
        return expected and ok

    def check_admin(self, username: str, password: str) -> dict | None:
        record = self.store.get_admin((username or "").strip())
        if not record or record.get("status") != ACTIVE:
            return None
        if not check_password_hash(record.get("password_hash", ""),
                                   password or ""):
            return None
        record["last_login"] = time.time()
        self.store.put_admin(record)
        return record

    # -- management -------------------------------------------------------
    def list(self) -> list[dict]:
        return sorted((public(r) for r in self.store.list_admins()),
                      key=lambda r: r["username"])

    def counts(self) -> dict:
        rows = self.store.list_admins()
        active = sum(1 for r in rows if r.get("status") == ACTIVE)
        return {"total": len(rows), "active": active,
                "suspended": len(rows) - active}

    def create_or_reset(self, username: str, password: str) -> tuple[dict, bool]:
        """Create the account, or reset its password when it already exists."""
        username = (username or "").strip()
        if not username:
            raise ValueError("اسم المستخدم مطلوب")
        if len(username) > 40 or not all(
                c.isalnum() or c in "._-" for c in username):
            raise ValueError("اسم المستخدم غير صالح (حروف وأرقام و . _ - فقط)")
        if username == self.super_user:
            raise ValueError("لا يمكن استخدام اسم المدير العام")
        if len(password or "") < MIN_PASSWORD_LEN:
            raise ValueError(
                f"كلمة السر قصيرة (الحد الأدنى {MIN_PASSWORD_LEN} رموز)")

        now = time.time()
        existing = self.store.get_admin(username)
        record = {
            "username": username,
            "password_hash": generate_password_hash(password),
            "status": (existing or {}).get("status", ACTIVE),
            "created_at": (existing or {}).get("created_at", now),
            "updated_at": now,
            "last_login": (existing or {}).get("last_login"),
        }
        self.store.put_admin(record)
        return public(record), existing is None

    def set_status(self, username: str, status: str) -> dict:
        if status not in (ACTIVE, SUSPENDED):
            raise ValueError("حالة غير معروفة")
        record = self.store.get_admin((username or "").strip())
        if not record:
            raise LookupError("الحساب غير موجود")
        record["status"] = status
        record["updated_at"] = time.time()
        self.store.put_admin(record)
        return public(record)

    def delete(self, username: str) -> bool:
        return self.store.delete_admin((username or "").strip())
