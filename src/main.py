"""
Run this file. It starts:
  1. the log watcher, in a background thread (keeps the DB in sync with the
     game's log.txt, whether or not the overlay is visible)
  2. the overlay window + system tray icon, on the main thread

Usage:
    python main.py
    python main.py --log-path "D:\\other\\path\\log.txt"
    python main.py --from-start     # also import players already in today's log
"""

import argparse
import threading

import Setup
import db
import log_watcher
import overlay


def main():
    parser = argparse.ArgumentParser(description="Isaac Player Tracker")
    parser.add_argument("--log-path", default=Setup.LOG_PATH)
    parser.add_argument("--from-start", action="store_true")
    args = parser.parse_args()

    db.init_db()

    watcher_thread = threading.Thread(
        target=log_watcher.run,
        kwargs={"path": args.log_path, "from_start": args.from_start},
        daemon=True,
    )
    watcher_thread.start()

    overlay.main()  # blocks, runs the Qt event loop


if __name__ == "__main__":
    main()
