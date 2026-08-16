# Isaac Player Tracker

Tracks everyone who's ever been in a Binding of Isaac: Repentance+ lobby with
you, stored locally in a SQLite database, with an in-game overlay for
adding/removing tags without alt-tabbing.

## How it works

- **`log_watcher.py`** tails your `log.txt` (the same way your PowerShell
  `Get-Content -Wait` does) and parses lines like:
  - `User 123 (Name) joined lobby 456` → adds them to the current lobby roster
  - `User 123 (Name) left lobby 456` → removes them from the roster
  - `Received Player Info message from user Name [123]` → keeps the
    steamid ↔ username mapping fresh
  - `Successfully joined/created lobby` / `Leaving current lobby` → resets
    the "who's with me right now" roster
- **`db.py`** stores everything in `isaac_players.db` (SQLite, one file, easy
  to inspect with any SQLite browser). Players are keyed by Steam ID so
  name changes don't split their history.
- **`overlay.py`** is a small always-on-top window. It uses the Windows
  `WS_EX_NOACTIVATE` style, which means clicking its buttons **never makes
  it the foreground window** — the game keeps thinking it has focus, so it
  won't pause or minimize. Toggle it with a global hotkey (default **F9**)
  that works even while the game is focused.
- **`main.py`** runs the watcher in a background thread and the overlay on
  the main thread. Run this one file.

## Setup (Windows)

```powershell
pip install -r requirements.txt
python main.py
```

The default log path is already set to yours:
`C:\Users\Egor\Documents\My Games\Binding of Isaac Repentance+\log.txt`

To change it, either pass a flag:

```powershell
python main.py --log-path "D:\some\other\log.txt"
```

or create a `config.json` next to `config.py`:

```json
{
  "log_path": "D:\\some\\other\\log.txt",
  "hotkey": "f9"
}
```

`--from-start` also parses everything already in the current log file
instead of only new lines from the moment you launch it.

## Using the overlay

- Press **F9** (or your configured hotkey) to show/hide it. Works while the
  game is focused.
- Drag it anywhere by clicking and holding on the window itself.
- Each player in your current lobby shows as a row with their name, Steam
  ID, and their tags. Click **+ tag** to attach an existing tag or type a
  new one — the tag list grows over time and is shared across all players.
- Click the ✕ on a tag chip to remove it.
- The roster refreshes automatically once a second from the database, so it
  reflects players joining/leaving in real time as the log updates.

## Notes / limitations

- This only works reliably if Isaac runs in **borderless windowed** mode
  (Options → Fullscreen: off, or "Windowed Fullscreen"). True exclusive
  fullscreen won't let any overlay draw on top of it — this is a Windows/GPU
  limitation, not something any app-level overlay can get around.
- The `keyboard` library's global hotkey hook sometimes needs the terminal
  to be running **as Administrator** to catch key presses while another
  app (the game) has focus — if F9 doesn't do anything, try that.
- All data lives in `isaac_players.db` next to these scripts. Back it up if
  you want to keep your tagging history across reinstalls.
- Player history (everyone you've ever played with, not just your current
  lobby) is in the `players` table — there's no UI for browsing it yet in
  this version, but it's simple SQL:
  `SELECT * FROM players ORDER BY last_seen DESC;`

## Extending it

- Want tag colors, a "full history" browser tab, or per-tag notes? The
  schema in `db.py` is small and deliberately simple to extend.
- Want it to auto-start with Windows? Point a shortcut at
  `pythonw.exe main.py` (the `w` variant avoids a console window) and drop
  it in your Startup folder.
