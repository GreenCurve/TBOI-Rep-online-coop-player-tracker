"""
Tails the Isaac Repentance+ log.txt file (like `Get-Content -Wait -Tail`)
and turns the relevant lines into database updates:

  - "Received Player Info message from user NAME [STEAMID]"
        -> record/refresh a known player (name <-> steamid mapping)

  - "User STEAMID (NAME) joined lobby LOBBYID"
        -> add NAME to the *current lobby* roster

  - "User STEAMID (NAME) left lobby LOBBYID"
        -> remove NAME from the current lobby roster

  - "Successfully joined lobby LOBBYID" / "Successfully created lobby LOBBYID"
        -> a fresh lobby session started -> clear old roster

  - "Leaving current lobby LOBBYID"
        -> you left -> clear roster (about to join/create a new one, or quit)

  - "Local user ID = STEAMID"
        -> remember who *you* are, so the overlay can skip showing yourself
"""

import os
import re
import time
import argparse
import logging

import config
import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [watcher] %(message)s")
log = logging.getLogger(__name__)

RE_PLAYER_INFO = re.compile(
    r"Received Player Info message from user (?P<name>.+?) \[(?P<steamid>\d+)\]"
)
RE_JOINED_LOBBY = re.compile(
    r"User (?P<steamid>\d+) \((?P<name>.+?)\) joined lobby (?P<lobby>\d+)"
)
RE_LEFT_LOBBY = re.compile(
    r"User (?P<steamid>\d+) \((?P<name>.+?)\) left lobby (?P<lobby>\d+)"
)
RE_SELF_JOINED_OR_CREATED = re.compile(
    r"Successfully (?:joined|created) lobby (?P<lobby>\d+)"
)
RE_LEAVING = re.compile(r"Leaving current lobby (?P<lobby>\d+)")
RE_LOCAL_USER = re.compile(r"Local user ID = (?P<steamid>\d+)")


def handle_line(line: str):
    m = RE_PLAYER_INFO.search(line)
    if m:
        db.upsert_player(m.group("steamid"), m.group("name"))
        return

    m = RE_JOINED_LOBBY.search(line)
    if m:
        db.upsert_player(m.group("steamid"), m.group("name"))
        db.add_lobby_member(m.group("lobby"), m.group("steamid"), m.group("name"))
        log.info("Joined lobby %s: %s (%s)", m.group("lobby"), m.group("name"), m.group("steamid"))
        return

    m = RE_LEFT_LOBBY.search(line)
    if m:
        db.remove_lobby_member(m.group("steamid"))
        log.info("Left lobby: %s (%s)", m.group("name"), m.group("steamid"))
        return

    m = RE_SELF_JOINED_OR_CREATED.search(line)
    if m:
        db.clear_current_lobby()
        db.set_state("current_lobby_id", m.group("lobby"))
        log.info("New lobby session: %s (roster cleared)", m.group("lobby"))
        return

    m = RE_LEAVING.search(line)
    if m:
        db.clear_current_lobby()
        log.info("Left our lobby %s (roster cleared)", m.group("lobby"))
        return

    m = RE_LOCAL_USER.search(line)
    if m:
        db.set_state("local_steam_id", m.group("steamid"))
        return


def follow(path: str, from_start: bool = False):
    """Generator yielding new lines appended to `path`, handling truncation
    (the game overwrites the log fresh on each launch) and the file not
    existing yet at startup."""
    f = None
    pos = 0
    while True:
        if f is None:
            if not os.path.exists(path):
                time.sleep(1.0)
                continue
            f = open(path, "r", encoding="utf-8", errors="ignore")
            if not from_start:
                f.seek(0, os.SEEK_END)
            pos = f.tell()

        line = f.readline()
        if line:
            pos = f.tell()
            yield line.rstrip("\n")
            continue

        time.sleep(0.3)
        try:
            size = os.path.getsize(path)
        except OSError:
            # file briefly missing (game restarting) - reopen next loop
            f.close()
            f = None
            continue

        if size < pos:
            # log was truncated/recreated - start over from the top
            f.close()
            f = open(path, "r", encoding="utf-8", errors="ignore")
            pos = 0
        else:
            f.seek(pos)


def run(path: str = None, from_start: bool = False):
    path = path or config.LOG_PATH
    db.init_db()
    log.info("Watching: %s", path)
    for line in follow(path, from_start=from_start):
        try:
            handle_line(line)
        except Exception:
            log.exception("Failed handling line: %r", line)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Isaac lobby log watcher")
    parser.add_argument("--log-path", default=config.LOG_PATH)
    parser.add_argument(
        "--from-start",
        action="store_true",
        help="Parse the whole existing log file instead of only new lines",
    )
    args = parser.parse_args()
    run(args.log_path, args.from_start)
