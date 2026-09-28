---
type: "query"
date: "2026-09-25T09:56:33.296695+00:00"
question: "Trace exactly what information a bot can see"
contributor: "graphify"
outcome: "useful"
source_nodes: ["AutomatedPolicy", "choose_automated_action", "build_seat_observation", "OwnSeatObservation", "OpponentSeatObservation", "PublicConcealedMeldView"]
---

# Q: Trace exactly what information a bot can see

## Answer

Expanded query via graph vocabulary: automated observation seat own opponent legal action private policy tile.
The graph establishes an intended bot policy boundary: PlayerObservation, supplied legal actions, and RandomSource. AutomatedPolicy.choose_action references these types at controllers.py L25, with extracted rationale at L31 to choose synchronously using only supplied observation and actions. The adapter choose_automated_action accepts RoomState but builds a seat observation (L87); adapter access must not be confused with policy access.
OwnSeatObservation uses PhysicalTile (observation.py L69, INFERRED). OpponentSeatObservation uses PublicTileView (L84, INFERRED). The builder calls OwnSeatObservation (L249), OpponentSeatObservation (L267), project_public_meld (L254), project_public_tile (L259), project_public_discard (L295), and PlayerObservation (L313), all EXTRACTED. PublicConcealedMeldView documents exposing kind/count but never tile faces or IDs (public.py L36).
Linked tests name the intended guarantees: only own physical IDs (test_game_milestone3.py L855), only legal discard catalog (L971), and observation/actions/RNG only (test_game_runtime.py L80). Test names and links establish coverage intent, not fresh test results.
The graph does not retain a complete observation field schema, so an exhaustive claim about every concealed-hand or wall-order field needs source verification. No tests were run.


## Outcome

- Signal: useful

## Source Nodes

- AutomatedPolicy
- choose_automated_action
- build_seat_observation
- OwnSeatObservation
- OpponentSeatObservation
- PublicConcealedMeldView