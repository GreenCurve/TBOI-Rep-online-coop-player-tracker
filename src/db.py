"""
SQLite storage layer for Isaac Player Tracker.

Tables
------
players           : every steam id ever seen, with latest known username
player_tags       : many-to-many player <-> tag
tags              : the extensible list of tags ("new player", etc.)
current_lobby     : live roster of the lobby you are in *right now*
                     (cleared / rebuilt whenever you join, create, or leave
                     a lobby, so the overlay always shows "who is with me now")
"""

import sqlite3
import threading
import time
from contextlib import contextmanager

import Setup

_lock = threading.Lock()


def _connect():
    conn = sqlite3.connect(Setup.DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_conn():
    with _lock:
        conn = _connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS players (
                steam_id    TEXT PRIMARY KEY,
                username    TEXT,
                first_seen  TEXT,
                last_seen   TEXT
            );

            CREATE TABLE IF NOT EXISTS tags (
                name TEXT PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS player_tags (
                steam_id TEXT NOT NULL,
                tag      TEXT NOT NULL,
                PRIMARY KEY (steam_id, tag),
                FOREIGN KEY (steam_id) REFERENCES players(steam_id),
                FOREIGN KEY (tag) REFERENCES tags(name)
            );

            CREATE TABLE IF NOT EXISTS current_lobby (
                lobby_id  TEXT,
                steam_id  TEXT,
                username  TEXT,
                joined_at TEXT,
                PRIMARY KEY (steam_id)
            );

            CREATE TABLE IF NOT EXISTS state (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )
        for t in Setup.TAGS:
            conn.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (t,))


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


# ---- players ---------------------------------------------------------------

def upsert_player(steam_id: str, username: str):
    now = _now()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO players(steam_id, username, first_seen, last_seen)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(steam_id) DO UPDATE SET
                username = excluded.username,
                last_seen = excluded.last_seen
            """,
            (steam_id, username, now, now),
        )


def get_player(steam_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT steam_id, username, first_seen, last_seen FROM players WHERE steam_id=?",
            (steam_id,),
        ).fetchone()
        return row


def all_players():
    with get_conn() as conn:
        return conn.execute(
            "SELECT steam_id, username, first_seen, last_seen FROM players ORDER BY last_seen DESC"
        ).fetchall()


# ---- tags -------------------------------------------------------------------

def list_tags():
    with get_conn() as conn:
        return [r[0] for r in conn.execute("SELECT name FROM tags ORDER BY name")]


def create_tag(name: str):
    name = name.strip()
    if not name:
        return
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (name,))


def add_tag_to_player(steam_id: str, tag: str):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (tag,))
        conn.execute(
            "INSERT OR IGNORE INTO player_tags(steam_id, tag) VALUES (?, ?)",
            (steam_id, tag),
        )


def remove_tag_from_player(steam_id: str, tag: str):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM player_tags WHERE steam_id=? AND tag=?", (steam_id, tag)
        )


def get_tags_for_player(steam_id: str):
    with get_conn() as conn:
        return [
            r[0]
            for r in conn.execute(
                "SELECT tag FROM player_tags WHERE steam_id=? ORDER BY tag", (steam_id,)
            )
        ]


# ---- current lobby -----------------------------------------------------------

def clear_current_lobby():
    with get_conn() as conn:
        conn.execute("DELETE FROM current_lobby")


def add_lobby_member(lobby_id: str, steam_id: str, username: str):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO current_lobby(lobby_id, steam_id, username, joined_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(steam_id) DO UPDATE SET
                lobby_id = excluded.lobby_id,
                username = excluded.username,
                joined_at = excluded.joined_at
            """,
            (lobby_id, steam_id, username, _now()),
        )


def remove_lobby_member(steam_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM current_lobby WHERE steam_id=?", (steam_id,))


def get_current_lobby_members():
    with get_conn() as conn:
        return conn.execute(
            "SELECT lobby_id, steam_id, username, joined_at FROM current_lobby ORDER BY joined_at"
        ).fetchall()


# ---- misc state ---------------------------------------------------------------

def set_state(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO state(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def get_state(key: str, default=None):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return row[0] if row else default
