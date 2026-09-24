"""Account storage and request-local paths for the threaded revision server."""
from contextvars import ContextVar
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import threading
import time

BASE_DIR = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get("REVISION_DATA_DIR", BASE_DIR / "data")).resolve()
CURRENT_USER = ContextVar("revision_user", default=None)
_locks = {}
_lock_guard = threading.Lock()


def database():
    connection = sqlite3.connect(DATA_ROOT / "accounts.sqlite3", timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def db():
    connection = database()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def password_hash(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return salt + ":" + digest.hex()


def password_matches(password, stored):
    salt, expected = stored.split(":", 1)
    actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return hmac.compare_digest(actual.hex(), expected)


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + secrets.token_hex(6) + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as output:
            json.dump(value, output, indent=2, ensure_ascii=False)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def initialize():
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    (DATA_ROOT / "users").mkdir(exist_ok=True)
    with db() as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL, password_hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY, user_id TEXT, csrf TEXT NOT NULL, expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS attempts (
                kind TEXT NOT NULL, identity TEXT NOT NULL, created REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS attempts_lookup ON attempts(kind, identity, created);
        """)
        connection.execute("BEGIN IMMEDIATE")
        if not connection.execute("SELECT 1 FROM users WHERE username='joe'").fetchone():
            # A fixed destination makes an interrupted first migration safe to retry.
            destination = DATA_ROOT / "users" / "legacy-joe"
            destination.mkdir(exist_ok=True)
            for source in DATA_ROOT.iterdir():
                if source.name == "users" or source.name.startswith("accounts.sqlite3"):
                    continue
                target = destination / source.name
                if source.is_dir():
                    shutil.copytree(source, target, dirs_exist_ok=True)
                elif source.is_file():
                    shutil.copy2(source, target)
            uploads = Path(os.environ.get("REVISION_LEGACY_UPLOADS", BASE_DIR / "uploads"))
            if uploads.is_dir():
                shutil.copytree(uploads, destination / "uploads", dirs_exist_ok=True)
            connection.execute("INSERT INTO users VALUES (?, ?, ?, ?)",
                               ("legacy-joe", "joe", "Joe", password_hash("joe")))


def create_user(username, password, display_name):
    username = username.strip().casefold()
    if not re.fullmatch(r"[a-z0-9_\-]{3,32}", username):
        raise ValueError("Use 3–32 letters, numbers, underscores or hyphens for your username.")
    if not 3 <= len(password) <= 128:
        raise ValueError("Choose a password between 3 and 128 characters.")
    display_name = display_name.strip() or username
    if len(display_name) > 60:
        raise ValueError("Your name must be 60 characters or fewer.")
    user_id = secrets.token_hex(16)
    with db() as connection:
        try:
            connection.execute("INSERT INTO users VALUES (?, ?, ?, ?)",
                               (user_id, username, display_name, password_hash(password)))
        except sqlite3.IntegrityError:
            raise ValueError("That username is already taken. Please choose another.") from None
        (DATA_ROOT / "users" / user_id).mkdir(parents=True, exist_ok=True)
        return dict(connection.execute("SELECT id, username, display_name FROM users WHERE id=?", (user_id,)).fetchone())


def authenticate(username, password):
    if len(password) > 128:
        return None
    with db() as connection:
        row = connection.execute("SELECT * FROM users WHERE username=?", (username.strip().casefold(),)).fetchone()
    # Do equivalent hashing for unknown accounts, too.
    if row is None:
        password_hash(password)
        return None
    if not password_matches(password, row["password_hash"]):
        return None
    return {key: row[key] for key in ("id", "username", "display_name")}


def new_session(user_id=None, previous=None):
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    expires = time.time() + (14 * 86400 if user_id else 7200)
    with db() as connection:
        connection.execute("DELETE FROM sessions WHERE expires < ? OR token = ?", (time.time(), previous or ""))
        connection.execute("INSERT INTO sessions VALUES (?, ?, ?, ?)",
                           (hashlib.sha256(token.encode()).hexdigest(), user_id, csrf, expires))
    return token


def get_session(token):
    digest = hashlib.sha256(token.encode()).hexdigest()
    with db() as connection:
        row = connection.execute("""SELECT sessions.*, users.username, users.display_name
            FROM sessions LEFT JOIN users ON users.id=sessions.user_id
            WHERE token=? AND expires>?""", (digest, time.time())).fetchone()
    return dict(row) if row else None


def consume_limit(kind, identity, limit, seconds):
    now = time.time()
    with db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM attempts WHERE created < ?", (now - 86400,))
        count = connection.execute("SELECT count(*) FROM attempts WHERE kind=? AND identity=? AND created>?",
                                   (kind, identity, now - seconds)).fetchone()[0]
        if count >= limit:
            return False
        connection.execute("INSERT INTO attempts VALUES (?, ?, ?)", (kind, identity, now))
    return True


def current_user():
    user = CURRENT_USER.get()
    if user is None:
        raise RuntimeError("Personal data requires a signed-in account.")
    return user


def user_dir():
    return DATA_ROOT / "users" / current_user()["id"]


def user_file(name):
    return user_dir() / name


def user_lock(user_id):
    with _lock_guard:
        return _locks.setdefault(user_id, threading.RLock())
