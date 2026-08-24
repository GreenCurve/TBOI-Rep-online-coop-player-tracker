"""
One-off script to add tags for specific players.
Run this from inside your project directory (next to Setup.py/db.py/main.py),
since Setup.py resolves DB_PATH relative to that location.

Usage:
    python insert_tags.py
"""

import db

entries = [
    ("76561199799228627", "sadstsar", "good player"),
    ("76561199840698899", "denizerengunes44", "kick on sight"),
]

db.init_db()

for steam_id, username, tag in entries:
    # Ensure the player row exists (player_tags has a FK on players.steam_id)
    existing = db.get_player(steam_id)
    if existing is None:
        db.upsert_player(steam_id, username)
        print(f"Inserted new player row: {username} ({steam_id})")
    else:
        print(f"Player already known: {existing[1]} ({steam_id})")

    db.add_tag_to_player(steam_id, tag)
    print(f"  -> tagged '{tag}'")

print("\nDone. Current tags:")
for steam_id, username, tag in entries:
    print(f"  {username} ({steam_id}): {db.get_tags_for_player(steam_id)}")
