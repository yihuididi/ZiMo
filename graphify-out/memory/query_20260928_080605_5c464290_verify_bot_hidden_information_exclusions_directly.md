---
type: "query"
date: "2026-09-28T08:06:05.505914+00:00"
question: "Verify bot hidden-information exclusions directly in source and run relevant tests"
contributor: "graphify"
outcome: "useful"
source_nodes: ["AutomatedPolicy", "RandomBotPolicy", "build_seat_observation", "RoomGameplay", "legal_actions"]
---

# Q: Verify bot hidden-information exclusions directly in source and run relevant tests

## Answer

Verified directly against source after graph traversal. AutomatedPolicy.choose_action receives PlayerObservation, legal_actions and RandomSource (controllers.py L25). RandomBotPolicy ignores observation and chooses a random supplied action (L42). RoomGameplay builds the seat observation and rejects a choice outside the legal catalog (gameplay.py L282).
Observation contains own concealed/drawn PhysicalTiles, opponents' concealed counts and drawn-tile boolean, public melds/bonuses/discards, live/reserve wall counts, own pending claims, room/match metadata and results. It excludes opponents' concealed/drawn tile contents, other seats' pending claims, wall contents/order and tile_id_salt (observation.py L63-L327). Concealed meld projections contain only kind/count (public.py L35). Current preview legal_actions only enumerates the active seat's own concealed/drawn discard tile IDs (engine.py L293). Runtime defaults to SystemRandomSource (kernel.py L111).
Validation: apps/api/.venv/bin/python -m pytest tests/test_game_privacy.py tests/test_game_runtime.py tests/test_game_milestone3.py tests/test_room_gameplay.py -q completed with 38 passed in 5.50s. Initial uv invocation could not access its global cache; existing project interpreter succeeded. No code changes. Findings concern the current supplied-input boundary and existing tests, not isolation of arbitrary malicious in-process policy code.


## Outcome

- Signal: useful

## Source Nodes

- AutomatedPolicy
- RandomBotPolicy
- build_seat_observation
- RoomGameplay
- legal_actions