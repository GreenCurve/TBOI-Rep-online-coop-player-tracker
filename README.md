# Isaac Player Tracker

Tracks everyone you've ever shared a Binding of Isaac: Repentance+ online
lobby with, in a local SQLite DB, with an in-game overlay for tagging
players without alt-tabbing.

## Install

```powershell
python -m pip install -r requirements.txt
```

Use `python -m pip`, not bare `pip` — on Windows it commonly resolves to
the wrong Python. Verify with `python -c "import sys; print(sys.executable)"`.

## Quick start

1. Set Isaac's display mode to **Windowed Fullscreen** or **Borderless**
   (Options → Graphics/Video). True exclusive fullscreen blocks all
   overlays, not just this one.
2. If your log isn't at the default path, either pass a flag or drop a
   `config.json` next to `Setup.py`:
   ```json
   { "log_path": "D:\\some\\other\\log.txt", "hotkey": "ctrl+alt+t" }
   ```
3. Run it:
   ```powershell
   python main.py
   ```
   Leave the terminal running in the background while you play.

| Flag | Effect |
|---|---|
| `--log-path "..."` | Override log path for this run only |
| `--from-start` | Parse the whole existing log, not just new lines (testing/backfill) |

**Overlay**: `F9` (or your configured hotkey) shows/hides it without
stealing focus from the game. Drag anywhere to move it. `+ tag` on a
player row to tag them; tags are shared across all players. Roster
refreshes every second and clears when you leave a lobby or close the
game.

Data lives in `isaac_players.db` next to the scripts (`players`,
`tags`/`player_tags`, `current_lobby`). Delete it to wipe everything.

## What we learned from log.txt

The tracker works by tailing `log.txt` (default:
`C:\Users\<you>\Documents\My Games\Binding of Isaac Repentance+\log.txt`,
only exists after first launch). A few behaviors drove the design:

| Observation | Implication |
|---|---|
| Pre-existing lobby members never fire a `joined lobby` line for you — only the `Received Player Info message from user NAME [STEAMID]` heartbeat does | Roster is built from **both** join lines and Player Info lines, not join lines alone |
| `Isaac is shutting down...` can fire while the log still shows you "in" a lobby (no prior `Leaving current lobby` line) | Roster is cleared unconditionally on shutdown, independent of last-known lobby state |
| The log file is truncated/recreated on each game relaunch, not just appended to | The watcher detects file-size shrink and reopens from the top instead of erroring |
| A lobby ID persists across multiple runs (post-run lobby ≠ new lobby) | Roster is only cleared on join/leave/shutdown events, never on run end |
| Display names can contain non-ASCII bytes that don't decode cleanly (UTF-8/CP1252 mismatch) | Log is read with lenient/replace-on-error decoding |

Open question we haven't resolved: whether `Isaac is shutting down...`
fires on a crash or forced kill, not just a graceful close. If it doesn't,
the roster can go stale until your next lobby join — no fallback for that
yet.

## Extending

Schema is in `db.py` — tag colors, a full history browser tab, or per-tag
notes are all straightforward additions.

Auto-start with Windows: point a shortcut at `pythonw.exe main.py` and
drop it in `shell:startup`.
