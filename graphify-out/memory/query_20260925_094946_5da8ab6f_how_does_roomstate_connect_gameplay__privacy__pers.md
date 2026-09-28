---
type: "query"
date: "2026-09-25T09:49:46.865806+00:00"
question: "How does RoomState connect gameplay, privacy, persistence, and recovery?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["RoomState", "MilestoneThreeEngine", "build_seat_observation", "RoomRepository", "validate_milestone_three_room", "deserialize_room_state"]
---

# Q: How does RoomState connect gameplay, privacy, persistence, and recovery?

## Answer

Expanded from original query via graph vocabulary: room, state, gameplay, observation, repository, snapshot, canonical, recovery, privacy, commit, deserialize, projection.

RoomState is the shared domain boundary connecting gameplay, private observations, persistence, and recovery (model.py L803).
Gameplay: MilestoneThreeEngine.transition references RoomState (engine.py L318), calls validate_milestone_three_room (L386), and constructs TransitionResult (L387).
Privacy: build_public_room_view calls build_player_observation (projection.py L241), which calls build_seat_observation (observation.py L348). choose_automated_action also calls build_seat_observation (controllers.py L87). Its extracted rationale describes a controller-safe observation for external or automated seats (observation.py L214).
Persistence: RoomRepository.compare_and_swap has extracted rationale to commit next room revision and all projections in one transaction (repository.py L214). It calls _record_from_state (L217), which calls validate_milestone_three_room (validation.py L72). This is the strongest cross-community bridge: persistence reuses gameplay validation.
Recovery: RoomRepository.load_room has extracted rationale to reconstruct from room_state and no auxiliary table (repository.py L189). deserialize_room_state is documented as strict and version-checked (serialization.py L17).
These links cross Pure Domain Interfaces, Mahjong Turn Engine, Private Player Observations, Automated Seat Controllers, Persistence Validation, and Canonical State Recovery. Parameter-derived uses edges are INFERRED; cited call and rationale edges are EXTRACTED. This is a graph-based architecture trace, not a fresh source audit or test run.


## Outcome

- Signal: useful

## Source Nodes

- RoomState
- MilestoneThreeEngine
- build_seat_observation
- RoomRepository
- validate_milestone_three_room
- deserialize_room_state