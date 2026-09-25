"""Allow-listed UI projections containing opaque action descriptors only."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .base import GameModel
from .capabilities import (
    MILESTONE_2_CAPABILITIES,
    RoomCapability,
    capabilities_for_ruleset_version,
)
from .config import GameConfig
from .model import (
    HandResult,
    MatchStatus,
    MatchResult,
    PlayerId,
    PlayerRole,
    RoomId,
    RoomState,
    RoomStatus,
    SeatBalance,
    SeatId,
    Wind,
    WindowId,
)
from .observation import (
    OpponentSeatObservation,
    ObservedOccupant,
    OwnSeatObservation,
    PhaseObservation,
    PlayerObservation,
    build_player_observation,
)
from .public import (
    PublicDiscardView,
    PublicMeldView,
    PublicTileView,
    project_public_tile,
)


class OpaqueActionDescriptor(GameModel):
    """Presentation-only handle resolved to a domain action by orchestration."""

    action_id: str = Field(min_length=1, max_length=256)
    label: str = Field(min_length=1, max_length=128)
    enabled: bool = True
    tone: Literal["primary", "neutral", "danger"] | None = None
    disabled_reason: str | None = Field(default=None, min_length=1, max_length=256)
    presentation_slot: Literal[
        "roomActions",
        "invitation",
        "concealedTile",
        "drawnTile",
    ] = "roomActions"
    presentation_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_presentation_target(self) -> "OpaqueActionDescriptor":
        if (self.presentation_slot == "concealedTile") != (
            self.presentation_index is not None
        ):
            raise ValueError(
                "presentationIndex is required only for concealedTile actions"
            )
        return self


class PublicPlayerView(GameModel):
    player_id: PlayerId
    display_name: str
    role: PlayerRole
    ready: bool
    connection_status: Literal["CONNECTED", "DISCONNECTED"] = "CONNECTED"
    disconnect_expires_at_ms: int | None = Field(default=None, ge=0)


class PublicOccupantView(GameModel):
    controller_type: Literal["external", "automated"]
    display_name: str | None = None
    player_id: PlayerId | None = None
    role: PlayerRole | None = None
    ready: bool | None = None


class SelfSeatView(GameModel):
    view: Literal["self"] = "self"
    seat_id: SeatId
    slot: int = Field(ge=0, lt=4)
    wind: Wind | None = None
    occupant: PublicOccupantView | None = None
    concealed_tiles: tuple[PublicTileView, ...] = ()
    drawn_tile: PublicTileView | None = None
    melds: tuple[PublicMeldView, ...] = ()
    bonus_tiles: tuple[PublicTileView, ...] = ()


class OpponentSeatView(GameModel):
    view: Literal["opponent"] = "opponent"
    seat_id: SeatId
    slot: int = Field(ge=0, lt=4)
    wind: Wind | None = None
    occupant: PublicOccupantView | None = None
    concealed_tile_count: int = Field(default=0, ge=0)
    has_drawn_tile: bool = False
    melds: tuple[PublicMeldView, ...] = ()
    bonus_tiles: tuple[PublicTileView, ...] = ()


PublicSeatView = Annotated[
    SelfSeatView | OpponentSeatView,
    Field(discriminator="view"),
]


class PublicGameView(GameModel):
    status: MatchStatus
    prevailing_wind: Wind
    dealer_seat_id: SeatId | None
    phase: PhaseObservation | None = None
    live_wall_tile_count: int = Field(default=0, ge=0)
    reserve_wall_tile_count: int = Field(default=0, ge=0)
    discards: tuple[PublicDiscardView, ...] = ()
    balances: tuple[SeatBalance, ...] = ()
    result: HandResult | None = None
    match_result: MatchResult | None = None


class PublicRoomView(GameModel):
    api_version: Literal["1"] = "1"
    room_id: RoomId
    revision: int = Field(ge=0)
    presence_version: int = Field(default=0, ge=0)
    status: RoomStatus
    ruleset_id: str
    ruleset_version: str
    state_schema_version: int = Field(ge=1)
    capabilities: tuple[RoomCapability, ...] = MILESTONE_2_CAPABILITIES
    config: GameConfig
    viewer_player_id: PlayerId
    server_time_ms: int = Field(ge=0)
    deadline_ms: int | None = Field(default=None, ge=0)
    window_id: WindowId | None = None
    players: tuple[PublicPlayerView, ...]
    seats: tuple[PublicSeatView, ...]
    game: PublicGameView | None = None
    actions: tuple[OpaqueActionDescriptor, ...] = ()


def _project_occupant(value: ObservedOccupant | None) -> PublicOccupantView | None:
    if value is None:
        return None
    return PublicOccupantView(
        controller_type=value.controller_type,
        display_name=value.display_name,
        player_id=value.player_id,
        role=value.role,
        ready=value.ready,
    )


def _project_from_observation(
    observation: PlayerObservation,
) -> tuple[PublicSeatView, ...]:
    seats: list[PublicSeatView] = []
    for seat in observation.seats:
        if isinstance(seat, OwnSeatObservation):
            seats.append(
                SelfSeatView(
                    seat_id=seat.seat_id,
                    slot=seat.slot,
                    wind=seat.wind,
                    occupant=_project_occupant(seat.occupant),
                    concealed_tiles=tuple(
                        project_public_tile(tile) for tile in seat.concealed_tiles
                    ),
                    drawn_tile=(
                        project_public_tile(seat.drawn_tile)
                        if seat.drawn_tile is not None
                        else None
                    ),
                    melds=seat.melds,
                    bonus_tiles=seat.bonus_tiles,
                )
            )
        elif isinstance(seat, OpponentSeatObservation):
            seats.append(
                OpponentSeatView(
                    seat_id=seat.seat_id,
                    slot=seat.slot,
                    wind=seat.wind,
                    occupant=_project_occupant(seat.occupant),
                    concealed_tile_count=seat.concealed_tile_count,
                    has_drawn_tile=seat.has_drawn_tile,
                    melds=seat.melds,
                    bonus_tiles=seat.bonus_tiles,
                )
            )
        else:  # pragma: no cover - exhaustive guard for future variants
            raise TypeError(f"unsupported seat observation: {type(seat)!r}")
    return tuple(seats)


def build_public_room_view(
    room: RoomState,
    viewer_player_id: PlayerId,
    *,
    server_time_ms: int,
    capabilities: tuple[RoomCapability, ...] | None = None,
    actions: tuple[OpaqueActionDescriptor, ...] = (),
    deadline_ms: int | None = None,
    window_id: WindowId | None = None,
    disconnected_players: Mapping[str, int | None] | None = None,
    presence_version: int = 0,
) -> PublicRoomView:
    """Build a UI view without accepting or serializing domain action objects."""

    canonical_deadline_ms = (
        None
        if room.pending_deadline is None
        else room.pending_deadline.deadline_ms
    )
    canonical_window_id = (
        None if room.pending_deadline is None else room.pending_deadline.window_id
    )
    if deadline_ms is not None and deadline_ms != canonical_deadline_ms:
        raise ValueError("projected deadline must match canonical room state")
    if window_id is not None and window_id != canonical_window_id:
        raise ValueError("projected window must match canonical room state")

    selected_capabilities = (
        capabilities_for_ruleset_version(room.ruleset_version)
        if capabilities is None
        else capabilities
    )
    observation = build_player_observation(
        room, viewer_player_id, capabilities=selected_capabilities
    )
    game = None
    if observation.match is not None:
        match = observation.match
        game = PublicGameView(
            status=match.status,
            prevailing_wind=match.prevailing_wind,
            dealer_seat_id=match.dealer_seat_id,
            phase=match.phase,
            live_wall_tile_count=match.live_wall_tile_count,
            reserve_wall_tile_count=match.reserve_wall_tile_count,
            discards=match.discards,
            balances=match.balances,
            result=match.result,
            match_result=match.match_result,
        )
    presence = {} if disconnected_players is None else disconnected_players
    return PublicRoomView(
        room_id=room.room_id,
        revision=room.revision,
        presence_version=presence_version,
        status=room.status,
        ruleset_id=room.ruleset_id,
        ruleset_version=room.ruleset_version,
        state_schema_version=room.state_schema_version,
        capabilities=selected_capabilities,
        config=room.config,
        viewer_player_id=viewer_player_id,
        server_time_ms=server_time_ms,
        deadline_ms=canonical_deadline_ms,
        window_id=canonical_window_id,
        players=tuple(
            PublicPlayerView(
                player_id=player.player_id,
                display_name=player.display_name,
                role=player.role,
                ready=player.ready,
                connection_status=(
                    "DISCONNECTED"
                    if str(player.player_id) in presence
                    else "CONNECTED"
                ),
                disconnect_expires_at_ms=presence.get(str(player.player_id)),
            )
            for player in room.players
        ),
        seats=_project_from_observation(observation),
        game=game,
        actions=actions,
    )
