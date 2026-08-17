# The Binding of Isaac: Repentance+ — Online Lobby Log Reference

Purpose of this document: a factual catalog of what has been directly observed
in a real `log.txt` from a live Repentance+ online session, for use as
domain knowledge by an LLM that will later write a parser/tracker. No code
is included here — only file locations, verbatim/near-verbatim log line
patterns, and notes on their observed behavior and open questions.

All observations below come from two consecutive `Get-Content -Wait -Tail 20`
capture sessions on a real Windows machine, playing actual Public Match
online co-op. Nothing here is speculative unless explicitly marked
"OPEN QUESTION" or "UNCONFIRMED."

---

## 1. Environment / File Location

- OS: Windows.
- Game install path (binaries, mods folder, DLLs — NOT where the log lives):
  `C:\Program Files (x86)\Steam\steamapps\common\The Binding of Isaac Rebirth\`
- Live log file actually used by the running game (confirmed working):
  `C:\Users\Egor\Documents\My Games\Binding of Isaac Repentance+\log.txt`
  - Note the trailing `+` in the folder name — Repentance (base) and
    Repentance+ (the online beta DLC) use **separate** folders, each with
    their own `log.txt` / `options.ini`.
  - Folder/file only exists after the game has been launched at least once.
- Game version observed in this session: `Binding of Isaac: Repentance+ v1.9.7.17.J460`
  (also appears as `Game Version: J460` on a separate line).
- The log is appended to live, in real time, as events happen — confirmed by
  successfully tailing it with `Get-Content -Wait -Tail 20` while playing.
- Log lines are not timestamped by the game itself; they appear in a fixed
  format `[LEVEL] - <message>`, where LEVEL is `INFO` or `WARN` (only these
  two seen so far). Any timestamping for tracking purposes has to be added
  externally (e.g. wall-clock time at the moment the parser reads the line).

---

## 2. IMPORTANT correction to prior assumption

Earlier research (community posts, ~2024) suggested mods/REPENTOGON are
fully disabled during Repentance+ online play. **This session's log
contradicts that** — the log shows mods, including REPENTOGON, being
loaded (`LOADED MOD ...`) immediately before an online match started:

```
[INFO] - begin list mods
[INFO] - LOADED MOD c:\program files (x86)\steam\steamapps\common\the binding of isaac rebirth/mods/antibirth soundtrack mod/content/
[INFO] - LOADED MOD c:\program files (x86)\steam\steamapps\common\the binding of isaac rebirth/mods/eden-token-debt_3128993268/content/
[INFO] - LOADED MOD c:\program files (x86)\steam\steamapps\common\the binding of isaac rebirth/mods/eyeguy's character portraits_946369715/content/
[INFO] - LOADED MOD c:\program files (x86)\steam\steamapps\common\the binding of isaac rebirth/mods/repentogon_3127536138/content/
[INFO] - LOADED MOD c:\program files (x86)\steam\steamapps\common\the binding of isaac rebirth/mods/timemachine_2617557401/content/
[INFO] - LOADED MOD c:\program files (x86)\steam\steamapps\common\the binding of isaac rebirth/mods/unlock all items and characters_2675591919/content/
```

**OPEN QUESTION**: whether this means mod Lua callbacks actually *run*
during the online match on this build/version, or whether they're merely
loaded into memory but sandboxed/inert while online. Not confirmed either
way from the log alone — would need a mod that logs its own callback
firings to verify. If mods do run online now, a Lua-side approach to
reading player info (e.g. via REPENTOGON's expanded API) may be worth
reconsidering as an alternative to log-scraping, but this is unverified.

---

## 3. Log line catalog

Placeholders: `<STEAMID>` = 17-digit SteamID64 (e.g. `76561198138444495`),
`<NAME>` = Steam display name (arbitrary string, can contain spaces/symbols),
`<LOBBYID>` = numeric lobby identifier (observed as large numbers like
`109775242301907426` — distinct namespace from SteamID64s, don't confuse
the two), `<N>` = generic number, `<FRAME>` = frame counter integer.

### 3.1 Lobby lifecycle

| Pattern | Example | Notes |
|---|---|---|
| `Creating public lobby...` | as-is | Fires when host starts a Public Match. Precedes lobby creation confirmation. |
| `Successfully created lobby <LOBBYID>` | `Successfully created lobby 109775242301286572` | Local player is the host/creator of this lobby. |
| `Successfully joined lobby <LOBBYID>` | `Successfully joined lobby 109775242298099731` | Fires both when creating your own lobby (immediately after "Successfully created lobby") AND when joining someone else's existing lobby. This is the reliable "I am now in lobby X" signal regardless of host/guest role. |
| `Leaving current lobby <LOBBYID>` | as-is | Fires when leaving a lobby (queueing into a new match, backing out to menu, etc.) |
| `Menu_OnlineLobby::broadcast_lobby_info_message() broadcasting lobby info message` | as-is (no params) | Fires repeatedly, in bursts, around lobby join/create and periodically while sitting in a lobby menu. OPEN QUESTION: burst count does NOT reliably correlate with member count (observed 8-9 in a row even when apparently solo in lobby) — semantics of exact trigger/frequency unconfirmed. Not a reliable participant-counting signal on its own. |
| `Attempting to send a reliable message to a user without an active connection, this message will be converted to non-reliable` (WARN level) | as-is | Seen immediately after "Leaving current lobby" lines. Appears to be a harmless side-effect of tearing down the connection, not informative about identities. |

### 3.2 Explicit join/leave events (for lobbies you were already in)

| Pattern | Example | Notes |
|---|---|---|
| `[Frame <FRAME>] User <STEAMID> (<NAME>) joined lobby <LOBBYID>` | `[Frame 0] User 76561199101983703 (Koulis) joined lobby 109775242301286572` | Fires when someone joins a lobby you are already sitting in. Gives SteamID64 + display name directly. Frame number observed as `0` in every case so far — likely just a lobby-menu-context counter reset, not meaningful for ordering. |
| `Menu_OnlineLobby::on_lobby_user_modified() eLobbyUserModification::Joined: Sending lobby info` | as-is | Fires immediately after the join line above, no new data. |
| `Menu_OnlineLobby::on_lobby_user_modified() eLobbyUserModification::Joined: Sending local save data` | as-is | Fires immediately after, no new data. |
| `[Frame <FRAME>] User <STEAMID> (<NAME>) left lobby <LOBBYID>` | `[Frame 0] User 76561198791159138 (dimonik649) left lobby 109775242300673142` | Explicit leave event with full identity. |
| `Menu_OnlineLobby::on_lobby_user_modified() Player <STEAMID> left` | `Menu_OnlineLobby::on_lobby_user_modified() Player 76561198791159138 left` | Fires alongside the leave line above; redundant SteamID only, no name. |

**Important asymmetry**: when YOU join an *existing* lobby that already has
people in it, those pre-existing members do **not** produce a "joined
lobby" line for you (you weren't there to observe their join). Confirmed
directly in the sample: joining lobby `109775242300673142`/`298099731`
mid-populated showed no join lines for `DECADENT`, `activa_tore`, or
`TToshtet`/`Romash` — they only appeared via the heartbeat pattern below.

### 3.3 Player info / heartbeat events (works for pre-existing members too)

| Pattern | Example | Notes |
|---|---|---|
| `[Frame <FRAME>] Received Player Info message from user <NAME> [<STEAMID>]` | `[Frame 0] Received Player Info message from user DECADENT [76561199782635318]` | **Most reliable signal for "who is in the lobby right now."** Repeats continuously/periodically for every member of the current lobby, including the local player themself, and including members who were already present before you joined. Note the ID is in `[brackets]` here vs. bare in the join/leave lines above — different formatting between event types. |
| `[Frame <FRAME>] Received Save Data message from user <NAME> [<STEAMID>]` | `[Frame 0] Received Save Data message from user TToshtet [76561199512737612]` | Fires once (not repeating like Player Info) per member, presumably when their co-op save data syncs. Also gives name+ID, format matches Player Info line. |

**Frequency pattern observed**: the "Received Player Info" line for a given
user repeats many times in short succession (looked like once every very
short interval, several per second), for as long as that user remains in
the lobby. This is good for liveness/"still connected" detection but means
a naive parser must deduplicate rather than log every occurrence as a new
event.

### 3.4 Local player self-identification

| Pattern | Example | Notes |
|---|---|---|
| `Local user ID = <STEAMID>` | `Local user ID = 76561198138444495` | Explicit, unambiguous statement of the local account's own SteamID64. **Confirmed reliable way to filter "self" out of any participant list**, rather than inferring it. |
| `Shared save user ID = <STEAMID>` | `Shared save user ID = 76561198138444495` | First occurrence matches local user ID above. |
| `Shared save user ID = 0` (repeated ×3 in sample) | as-is | Empty/unused shared-save slots (game supports up to 4 local save-sharing slots for Eden tokens etc.). **NOT related to online lobby membership** — this is a local save-file mechanic, do not conflate with remote players. |

**Timing caveat**: in the observed session, `Local user ID = ...` only
appeared once, and only *after* a run had ended (post "Game Over" / post
"NotifyGameEnd"), not immediately at lobby creation or game start. OPEN
QUESTION: whether it also appears earlier in other sessions/circumstances —
not confirmed either way. Don't assume it's available before a run
completes.

### 3.5 Game-start transition (lobby → actual run)

Sequence observed, in order, when a lobby's host starts the match:

1. `Menu_OnlineLobby::send_game_start()`
2. A large block of engine/asset reinitialization follows — OpenGL/OpenAL
   version strings, Theora video library init, `Command Line:` + full exe
   path, `Game Version: J460`, Lua VM reservation (`Successfully reserved
   1073741824 bytes of memory for Lua`), `Running Lua Script:
   resources/scripts/enums.lua` then `main.lua`, version string
   `Binding of Isaac: Repentance+ v1.9.7.17.J460`, `load archives: <N>
   milliseconds`, full shader init block, viewport/framebuffer resize
   lines (noise, window resolution bookkeeping), `begin list mods` +
   `LOADED MOD <path>` lines (see §2), intro cutscene playback, then a
   long `Menu <X> Init` sequence (Title, Save, Game, Daily, Character,
   SpecialSeed, Challenge, Collection, Stats, Mods, Options, Controller,
   Key Config, Cutscene, Bestiary, Custom Challenge, **Online Lobby**,
   **Friend Lobbies**, **Multiplayer**, **Options Online**, **Create
   Lobby**, **Online Awards**), then PersistentData/SteamCloud save
   loading chunks (Achievements, Counters, Level Counters, Collectibles,
   Mini Bosses, Bosses, Challenge Counters, Cutscene Counters,
   GameSettings, Special Seed Counters, Bestiary Counters — this chunk
   list repeats for save slots 1/2/3, with slots 2/3 typically showing
   "SteamCloud could not find or open ..." / "Starting with a clean save
   state." if those slots are unused).
   **This whole block appears to be routine engine reload noise, not
   player-identity-bearing** — safe to ignore for lobby-tracking purposes,
   but documented here so it isn't mistaken for something meaningful.
3. `[Frame <FRAME>] Received Join New Game message from user <NAME> [<STEAMID>]`
   — example: `[Frame 0] Received Join New Game message from user Dont Touch My Pickups [76561198138444495]`.
   In this sample the NAME/ID here matched the **local player's own**
   identity (confirmed by the later `Local user ID = 76561198138444495`
   line matching). OPEN QUESTION: does this line also fire once per
   *other* party member when the run actually starts (i.e., is it a
   general "this user has entered the run" event for everyone), or does
   it only ever echo the local user? Only one occurrence was observed in
   this sample, for the local account, in a lobby that — per the
   preceding lines — appears to have been solo at the moment of start.
   Needs a multi-player-at-game-start sample to confirm.
4. `Menu_OnlineLobby::notify_game_start()`
5. `[Frame <FRAME>] Notify Game Start`
6. `Setting PersistentGameData ReadOnly to False`
7. `Start Networked` — marks the actual transition into networked gameplay.
8. `RNG Start Seed: <SEED_TEXT> (<SEED_NUM>) [Net, 1]` — example:
   `RNG Start Seed: XDQP 306T (2536743718) [Net, 1]`. The `[Net, 1]` tag
   appears to mark this as a networked/online run specifically — could be
   a useful discriminator for "this log segment is an online match" vs.
   offline play, worth testing against a solo/offline run's seed line for
   comparison (UNCONFIRMED whether offline runs omit the `[Net, ...]` tag
   or use a different value).
9. Player/controller setup: `[Frame: 0] Adding local player, device ID = 0`,
   `[Frame: 0] Initialized player with Variant <N> and Subtype <N>`
   (character selection — variant/subtype numbers, not decoded here),
   `Entity_Player::SetControllerId() Setting controller ID to <N>, (Prev: <N>)`,
   `Assigning Player Color (<N>) to Controller(<N>)`,
   `Reassigning Player Color (<N>) Prev(<N>) New(<N>)`,
   `Assinging player entity <N> (ControlerIndex = <N>) to HUD slot <N>`
   (note: "Assinging" is a typo in the game's own log, verbatim).
   These describe **local input/color slot assignment only** — no
   SteamIDs appear in this block. Not useful for identifying remote
   players, only for local UI/controller bookkeeping. Player colors 0-3
   confirm a hard cap of 4 co-op slots.

### 3.6 In-run gameplay noise (not participant-related, listed for completeness so it isn't mistaken for relevant data)

Level/room generation, RNG seeds per room, entity spawns, pickups,
collectibles, costumes, music track queuing, e.g.:
```
[RoomConfig] load stage <N>: <StageName> (mode <N>)
Level::Init m_Stage <N>, m_StageType <N> Seed <N>
Room <N>.<N>(<RoomName>)
[Frame <N>] SpawnRNG seed: <N>
[Frame <N>] Spawn Entity with Type(<N>), Variant(<N>), Pos(<N>,<N>)
[Frame <N>] Entity Pickup Initialized as: <N>.<N>.<N>  Seed: <hex>
Adding collectible <N> (<ItemName>) to player <N> (<CharacterName>) from pool <PoolName>
Queued Path music/<Track>.ogg
```
None of this carries SteamIDs or lobby membership info. Safe to ignore
entirely for the player-tracking goal.

### 3.7 Run end / return to lobby

| Pattern | Example | Notes |
|---|---|---|
| `[Frame <FRAME>] NetManager::NotifyGameEnd() Result = <CODE>` | `Result = 2`, `Result = 0` both observed | Fires possibly more than once per run-end (seen twice with Result=2, once with Result=0, in sequence). Semantics of the result codes are UNCONFIRMED — plausibly death vs. quit vs. disconnect, but not verified. Worth collecting more samples across different end conditions (death, manual quit, host disconnect, full clear) to map codes to causes. |
| `Game Over. Killed by (<N>.<N>) spawned by (<N>.<N>) damage flags (<N>)` | `Game Over. Killed by (0.0) spawned by (0.0) damage flags (8224)` | Fires once, on death specifically. The "Killed by"/"spawned by" numbers look like entity Type.Variant pairs (both `0.0` here, meaning unclear — possibly a generic/unattributed death cause). Not player-identity-bearing. |
| `music stopped playing` | as-is | Generic transition marker, fires at multiple points (death, lobby leave), not specific to run-end alone. |
| `[Frame: <FRAME>] Input device (ID = <N>) disconnected` | `[Frame: 0] Input device (ID = 1) disconnected` | Local controller/input device disconnect. UNCONFIRMED whether this can also reflect a *remote* player's input stream dropping in an online context, or if it's purely local hardware. Treat as local-only until proven otherwise. |
| `Clearing player color assignments` + `Clearing player color assignment for color <N>` (×4, colors 0-3) | as-is | Post-run cleanup of all 4 possible player-color slots. Confirms 4 as the hard cap again, not participant-identifying. |

After run-end, the game replays the same "Menu Manager reinit" /
"PersistentData reload" block seen in §3.5 step 2, then returns to the
lobby menu. Critically: **the same lobby ID persisted across the run** —
in the sample, lobby `109775242301907426` was created, a run was played
and ended (death), and afterward two NEW players (`raligarh`,
`IamZenith`) joined that *same* lobby ID while back in the post-run lobby
screen, before it was finally left. So a lobby's lifetime is NOT
"one lobby = one run" — it can persist across multiple runs with
membership changing in between. A tracker should not assume a lobby ID
closes the moment a run ends.

---

## 4. Regex-relevant field formats (for whoever writes the parser)

- SteamID64: always a 17-digit number starting with `7656119...` in every
  sample so far (standard SteamID64 range). Two textual placements seen:
  - Bare, no brackets: `User 76561199101983703 (Koulis) joined lobby ...`
  - In square brackets, after the name: `... from user DECADENT [76561199782635318]`
- Lobby ID: also a large numeric string but from a visibly different
  numeric range/pattern (`109775242...`, consistently 18 digits, consistent
  `1097752423...` prefix across every lobby ID observed) — should not be
  confused with SteamID64 even though both are long digit strings. A
  parser matching "any long digit string" indiscriminately would wrongly
  conflate these two ID types; matching should anchor on the surrounding
  words (`lobby `, `[`, etc.) rather than digit-length alone.
- Display names: freeform, observed examples include spaces
  (`Dont Touch My Pickups`), underscores (`activa_tore`), mixed case
  (`TToshtet`, `IamZenith`), no observed length limit or character
  restriction beyond what's visible — should not assume names are
  whitespace-free when building regex.

---

## 5. Summary of open questions for future verification

1. Does `[Frame 0] Received Join New Game message from user ...` fire once
   per party member at game start, or only ever for the local player?
2. Do REPENTOGON/mod Lua callbacks actually execute during an online match
   on this build (v1.9.7.17.J460), given they're now confirmed to load?
3. What do `NetManager::NotifyGameEnd() Result = 0` vs `Result = 2` (and
   any other codes) actually correspond to?
4. Does `RNG Start Seed: ... [Net, 1]` reliably distinguish online from
   offline runs, and is the second number in `[Net, 1]` ever something
   other than `1` (e.g. does it scale with player count)?
5. Does `Input device (ID = N) disconnected` ever correspond to a remote
   player, or is it strictly local hardware?
6. Does `Menu_OnlineLobby::broadcast_lobby_info_message()` burst frequency
   ever correlate meaningfully with lobby member count, or is it purely
   periodic/unrelated?
