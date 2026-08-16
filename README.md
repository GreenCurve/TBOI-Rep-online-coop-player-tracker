# Isaac Player Tracker

Tracks everyone who's ever been in a Binding of Isaac: Repentance+ online
lobby with you, stored locally in a SQLite database, with an in-game
overlay for tagging players (e.g. "ok player", "bad player") without
alt-tabbing or losing focus on the game.

## What it does

- Watches the game's `log.txt` in the background and builds a live roster
  of everyone in your current lobby — including people who were already
  in a public lobby before you joined it.
- Remembers every player you've ever shared a lobby with, keyed by Steam
  ID, so name changes don't split their history.
- Lets you tag players from a small overlay window, without leaving the
  game or losing input focus.
- Clears the roster automatically when you leave a lobby or close the
  game, so it always reflects who's with you *right now*.

## Requirements

- Windows
- Python 3.10+ (a conda env or venv is recommended — see below)
- Binding of Isaac: Repentance+ with online co-op

## 1. Install

Open a terminal **inside your Python environment** (conda env, venv,
whatever you use) and run:

```powershell
python -m pip install -r requirements.txt
```

Use `python -m pip` rather than a bare `pip` command — on Windows it's
common for `pip` on PATH to silently resolve to a different Python
installation than the one you think is active (see
[Troubleshooting](#troubleshooting) if you hit install errors).

## 2. Configure your log path (if needed)

The default log path is already set to:
`C:\Users\Egor\Documents\My Games\Binding of Isaac Repentance+\log.txt`

If yours is different, either pass a flag every time you run it:

```powershell
python main.py --log-path "D:\some\other\log.txt"
```

or create a `config.json` file next to `config.py` so you don't have to
remember the flag:

```json
{
  "log_path": "D:\\some\\other\\log.txt",
  "hotkey": "ctrl+alt+t"
}
```

`hotkey` (optional) sets the key combo that shows/hides the overlay.
Defaults to `f9`. Use `+`-joined names as understood by the `keyboard`
library, e.g. `"f9"`, `"ctrl+alt+t"`, `"shift+f10"`.

## 3. Put Isaac in borderless/windowed mode

**This step matters.** True exclusive fullscreen bypasses Windows'
compositor entirely, so no overlay — this one, Discord's, RTSS, anything —
can draw on top of it. In Isaac: Options → Graphics/Video → set display
mode to **Windowed Fullscreen** or **Borderless** if available. If Isaac
only offers plain Windowed mode, use a free tool like
[ihateborders](https://github.com/Z1xus/ihateborders) to strip the window
border and fill the screen — see [Troubleshooting](#troubleshooting) for
details.

## 4. Run it

```powershell
python main.py
```

This starts the log watcher in the background and opens the overlay. Leave
the terminal window running in the background while you play (minimize
it, don't close it).

Optional flags:
- `--log-path "..."` — override the log path for this run only
- `--from-start` — parse the entire existing log file on launch instead of
  only new lines from this point forward (useful for testing/backfilling)

## Using the overlay

- Press your hotkey (default **F9**) to show/hide it — works while Isaac
  is focused, and clicking it never steals focus back from the game.
- Click-and-drag anywhere on the window to reposition it.
- Each player currently in your lobby shows as a row with their name,
  Steam ID, and tags.
  - Click **+ tag** to attach an existing tag, or choose "New tag…" to
    create one on the fly. Tags are shared across all players, so the list
    grows over time.
  - Click the **✕** on a tag chip to remove it from that player.
- The roster refreshes once a second and updates live as people join,
  leave, or you close the game.
- A system tray icon is also available for show/hide and quitting.

## Where your data lives

Everything is stored in `isaac_players.db` (SQLite) next to the scripts —
one file, easy to back up or inspect with any SQLite browser (e.g.
[DB Browser for SQLite](https://sqlitebrowser.org/)).

- `players` — every Steam ID you've ever shared a lobby with, with their
  latest known name.
- `player_tags` / `tags` — your tag assignments.
- `current_lobby` — the live "who's with me right now" roster the overlay
  reads from (only meaningful while the game is running).

Full player history isn't browsable in the overlay UI yet, but you can
query it directly:

```sql
SELECT * FROM players ORDER BY last_seen DESC;
```

Deleting `isaac_players.db` wipes everything — including tag history —
and starts fresh.

## Troubleshooting

**`pip install` fails with a file-in-use / WinError 2 error, or warnings
about invalid distributions (`~ip`, `~umpy`, etc.)**
This is almost always pip installing into the wrong, possibly-corrupted
global Python instead of your isolated environment. Confirm which
Python is actually active:
```powershell
python -c "import sys; print(sys.executable)"
```
If that doesn't point into your conda env or venv folder, your
environment isn't actually activated on PATH. For conda users, run
`conda init cmd.exe` (or `conda init powershell`) once, **fully close and
reopen your terminal**, then `conda activate <env>` again and re-check
with the command above before installing.

**F9 (or your hotkey) doesn't do anything**
1. Test the hook in isolation, independent of the overlay:
   ```powershell
   python -c "import keyboard; keyboard.add_hotkey('f9', lambda: print('fired!')); keyboard.wait()"
   ```
   Press the key while Isaac is focused. If nothing prints, it's a
   permissions/conflict issue — try running your terminal **as
   Administrator**, and check other overlay software (GeForce Experience,
   Xbox Game Bar, RTSS) isn't already bound to the same key.
2. If it prints there but still doesn't toggle the overlay, make sure
   you're on the latest version of `overlay.py` — earlier versions had a
   cross-thread bug where the hotkey fired but the toggle silently
   failed to reach the Qt event loop.

**Overlay only shows when Isaac isn't fullscreen**
Expected — see step 3 above. If Isaac has no native borderless option,
use [ihateborders](https://github.com/Z1xus/ihateborders) (free,
open-source): set Isaac to Windowed mode, run the tool, pick the Isaac
window, check "Resize to screen," click "Make Borderless." Avoid random
"Borderless Gaming" downloads outside of GitHub — the original free tool
went paid on Steam and free binaries were pulled, so a lot of "free
download" sites for it are unofficial and not trustworthy.

**Roster doesn't clear after closing the game**
Should be fixed as of the version with `Isaac is shutting down...`
handling in `log_watcher.py` — this line fires on graceful exit and clears
the roster unconditionally, even if you didn't explicitly leave the lobby
first. If the game crashes or is force-killed rather than closed normally,
the log won't show this line and the roster may persist until your next
lobby join (which also clears it). There's currently no fallback for
ungraceful exits.

## Extending it

The schema in `db.py` is intentionally small — tag colors, a full player
history browser tab, or per-tag notes are all straightforward additions.

To auto-start with Windows, point a shortcut at `pythonw.exe main.py`
(the `w` variant suppresses the console window) and drop it in your
Startup folder (`Win+R` → `shell:startup`).
