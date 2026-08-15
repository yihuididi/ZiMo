"""Seat-specific, allow-listed inputs for controllers."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .base import GameModel
from .config import GameConfig
from .model import (
    AutomatedSeatController,
    AwaitingDiscardPhase,
    AwaitingDrawPhase,
    CompletePhase,
    DiscardClaimsPhase,
    ExternalSeatController,
    HandResult,
    KongReplacementPhase,
    KongRobberyPhase,
    MatchStatus,
    MatchResult,
    PendingClaim,
    PhysicalTile,
    PlayerId,
    PlayerRole,
    RoomId,
    RoomState,
    RoomStatus,
    SeatBalance,
    SeatId,
    SetupPhase,
    Wind,
    WindowId,
)
from .public import (
    PublicDiscardView,
    PublicMeldView,
    PublicTileView,
    project_public_discard,
    project_public_meld,
    project_public_tile,
)


class ObservationError(ValueError):
    """Raised when no authorized player observation can be constructed."""


class ObservedOccupant(GameModel):
    controller_type: Literal["external", "automated"]
    display_name: str | None = None
    player_id: PlayerId | None = None
    role: PlayerRole | None = None
    ready: bool | None = None


class OwnSeatObservation(GameModel):
    view: Literal["self"] = "self"
    seat_id: SeatId
    slot: int = Field(ge=0, lt=4)
    wind: Wind | None = None
    occupant: ObservedOccupant | None = None
    concealed_tiles: tuple[PhysicalTile, ...] = ()
    drawn_tile: PhysicalTile | None = None
    melds: tuple[PublicMeldView, ...] = ()
    bonus_tiles: tuple[PublicTileView, ...] = ()


class OpponentSeatObservation(GameModel):
    view: Literal["opponent"] = "opponent"
    seat_id: SeatId
    slot: int = Field(ge=0, lt=4)
    wind: Wind | None = None
    occupant: ObservedOccupant | None = None
    concealed_tile_count: int = Field(default=0, ge=0)
    has_drawn_tile: bool = False
    melds: tuple[PublicMeldView, ...] = ()
    bonus_tiles: tuple[PublicTileView, ...] = ()


SeatObservation = Annotated[
    OwnSeatObservation | OpponentSeatObservation,
    Field(discriminator="view"),
]


class PhaseObservation(GameModel):
    type: Literal[
        "setup",
        "awaitingDraw",
        "awaitingDiscard",
        "discardClaims",
        "kongReplacement",
        "kongRobbery",
        "complete",
    ]
    active_seat_id: SeatId | None = None
    window_id: WindowId | None = None
    discard_sequence: int | None = Field(default=None, ge=1)
    declaring_seat_id: SeatId | None = None


class MatchObservation(GameModel):
    status: MatchStatus
    prevailing_wind: Wind
    dealer_seat_id: SeatId
    phase: PhaseObservation | None = None
    live_wall_tile_count: int = Field(default=0, ge=0)
    reserve_wall_tile_count: int = Field(default=0, ge=0)
    discards: tuple[PublicDiscardView, ...] = ()
    balances: tuple[SeatBalance, ...] = ()
    own_pending_claims: tuple[PendingClaim, ...] = ()
    result: HandResult | None = None
    match_result: MatchResult | None = None


class PlayerObservation(GameModel):
    room_id: RoomId
    revision: int = Field(ge=0)
    room_status: RoomStatus
    ruleset_id: str
    ruleset_version: str
    state_schema_version: int = Field(ge=1)
    capabilities: tuple[()] = ()
    config: GameConfig
    viewer_player_id: PlayerId
    seats: tuple[SeatObservation, ...]
    match: MatchObservation | None = None


def _occupant(room: RoomState, seat_id: SeatId) -> ObservedOccupant | None:
    seat = next(seat for seat in room.seats if seat.seat_id == seat_id)
    controller = seat.controller
    if controller is None:
        return None
    if isinstance(controller, ExternalSeatController):
        player = next(
            player for player in room.players if player.player_id == controller.player_id
        )
        return ObservedOccupant(
            controller_type="external",
            display_name=player.display_name,
            player_id=player.player_id,
            role=player.role,
            ready=player.ready,
        )
    if isinstance(controller, AutomatedSeatController):
        return ObservedOccupant(
            controller_type="automated",
            display_name=seat.occupant_name,
        )
    raise TypeError(f"unsupported controller descriptor: {type(controller)!r}")


def _seat_winds(room: RoomState) -> dict[SeatId, Wind]:
    if room.match is None:
        return {}
    seats = sorted(room.seats, key=lambda seat: seat.slot)
    dealer_index = next(
        index
        for index, seat in enumerate(seats)
        if seat.seat_id == room.match.dealer_seat_id
    )
    winds = (Wind.EAST, Wind.SOUTH, Wind.WEST, Wind.NORTH)
    return {
        seat.seat_id: winds[(index - dealer_index) % 4]
        for index, seat in enumerate(seats)
    }


def _phase_observation(phase: object) -> PhaseObservation:
    if isinstance(phase, SetupPhase):
        return PhaseObservation(type="setup")
    if isinstance(phase, AwaitingDrawPhase):
        return PhaseObservation(type="awaitingDraw", active_seat_id=phase.seat_id)
    if isinstance(phase, AwaitingDiscardPhase):
        return PhaseObservation(type="awaitingDiscard", active_seat_id=phase.seat_id)
    if isinstance(phase, DiscardClaimsPhase):
        return PhaseObservation(
            type="discardClaims",
            window_id=phase.window_id,
            discard_sequence=phase.discard_sequence,
        )
    if isinstance(phase, KongReplacementPhase):
        return PhaseObservation(
            type="kongReplacement", active_seat_id=phase.seat_id
        )
    if isinstance(phase, KongRobberyPhase):
        return PhaseObservation(
            type="kongRobbery",
            window_id=phase.window_id,
            declaring_seat_id=phase.declaring_seat_id,
        )
    if isinstance(phase, CompletePhase):
        return PhaseObservation(type="complete")
    raise TypeError(f"unsupported hand phase: {type(phase)!r}")


def build_player_observation(
    room: RoomState,
    viewer_player_id: PlayerId,
    *,
    capabilities: tuple[()] = (),
) -> PlayerObservation:
    """Build an observation solely from explicitly selected safe fields."""

    if not any(player.player_id == viewer_player_id for player in room.players):
        raise ObservationError("viewer is not a room player")

    viewer_seat_id = next(
        (
            seat.seat_id
            for seat in room.seats
            if isinstance(seat.controller, ExternalSeatController)
            and seat.controller.player_id == viewer_player_id
        ),
        None,
    )
    winds = _seat_winds(room)
    hands = (
        {hand.seat_id: hand for hand in room.match.current_hand.player_hands}
        if room.match is not None and room.match.current_hand is not None
        else {}
    )

    observed_seats: list[SeatObservation] = []
    for seat in sorted(room.seats, key=lambda item: item.slot):
        hand = hands.get(seat.seat_id)
        common = {
            "seat_id": seat.seat_id,
            "slot": seat.slot,
            "wind": winds.get(seat.seat_id),
            "occupant": _occupant(room, seat.seat_id),
        }
        if seat.seat_id == viewer_seat_id:
            observed_seats.append(
                OwnSeatObservation(
                    **common,
                    concealed_tiles=hand.concealed_tiles if hand else (),
                    drawn_tile=hand.drawn_tile if hand else None,
                    melds=(
                        tuple(project_public_meld(meld) for meld in hand.melds)
                        if hand
                        else ()
                    ),
                    bonus_tiles=(
                        tuple(project_public_tile(tile) for tile in hand.bonus_tiles)
                        if hand
                        else ()
                    ),
                )
            )
        else:
            observed_seats.append(
                OpponentSeatObservation(
                    **common,
                    concealed_tile_count=len(hand.concealed_tiles) if hand else 0,
                    has_drawn_tile=hand is not None and hand.drawn_tile is not None,
                    melds=(
                        tuple(project_public_meld(meld) for meld in hand.melds)
                        if hand
                        else ()
                    ),
                    bonus_tiles=(
                        tuple(project_public_tile(tile) for tile in hand.bonus_tiles)
                        if hand
                        else ()
                    ),
                )
            )

    match_observation = None
    if room.match is not None:
        hand = room.match.current_hand
        match_observation = MatchObservation(
            status=room.match.status,
            prevailing_wind=room.match.prevailing_wind,
            dealer_seat_id=room.match.dealer_seat_id,
            phase=_phase_observation(hand.phase) if hand else None,
            live_wall_tile_count=len(hand.wall.live_tiles) if hand else 0,
            reserve_wall_tile_count=len(hand.wall.reserve_tiles) if hand else 0,
            discards=(
                tuple(project_public_discard(discard) for discard in hand.discards)
                if hand
                else ()
            ),
            balances=room.match.balances,
            own_pending_claims=(
                tuple(
                    claim
                    for claim in hand.pending_claims
                    if claim.seat_id == viewer_seat_id
                )
                if hand is not None and viewer_seat_id is not None
                else ()
            ),
            result=hand.result if hand else None,
            match_result=room.match.result,
        )

    return PlayerObservation(
        room_id=room.room_id,
        revision=room.revision,
        room_status=room.status,
        ruleset_id=room.ruleset_id,
        ruleset_version=room.ruleset_version,
        state_schema_version=room.state_schema_version,
        capabilities=capabilities,
        config=room.config,
        viewer_player_id=viewer_player_id,
        seats=tuple(observed_seats),
        match=match_observation,
    )
