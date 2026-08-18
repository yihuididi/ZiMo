"""Canonical immutable room, match, hand, and tile state."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import Field, model_validator
from pydantic_core import core_schema

from .base import GameModel
from .config import GameConfig


class DomainId(str):
    """Runtime-branded immutable identity that persists as a JSON string."""

    def __new__(cls, value: str) -> "DomainId":
        if type(value) not in (str, cls):
            raise TypeError(
                f"{cls.__name__} requires an unbranded string, not "
                f"{type(value).__name__}"
            )
        if not value:
            raise ValueError(f"{cls.__name__} cannot be empty")
        if len(value) > 256:
            raise ValueError(f"{cls.__name__} cannot exceed 256 characters")
        return str.__new__(cls, value)

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other) and str.__eq__(self, other)

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash((type(self), str(self)))

    @classmethod
    def _validate(cls, value: object) -> "DomainId":
        if type(value) not in (str, cls):
            raise ValueError(
                f"{cls.__name__} requires an unbranded string; received "
                f"{type(value).__name__}"
            )
        return cls(value)  # type: ignore[arg-type]

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: object,
        handler: object,
    ) -> core_schema.CoreSchema:
        del source_type, handler
        return core_schema.no_info_plain_validator_function(
            cls._validate,
            json_schema_input_schema=core_schema.str_schema(
                strict=True, min_length=1, max_length=256
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                str, when_used="json"
            ),
        )


class RoomId(DomainId):
    pass


class PlayerId(DomainId):
    pass


class SeatId(DomainId):
    pass


class TileId(DomainId):
    pass


class HandId(DomainId):
    pass


class MatchId(DomainId):
    pass


class WindowId(DomainId):
    pass


class ConnectionId(DomainId):
    pass


class CommandId(DomainId):
    pass


class PolicyId(DomainId):
    pass


class Wind(StrEnum):
    EAST = "EAST"
    SOUTH = "SOUTH"
    WEST = "WEST"
    NORTH = "NORTH"


class RoomStatus(StrEnum):
    CREATED = "CREATED"
    WAITING_FOR_PLAYERS = "WAITING_FOR_PLAYERS"
    READY = "READY"
    IN_MATCH = "IN_MATCH"
    FINISHED = "FINISHED"


class MatchStatus(StrEnum):
    PENDING_SETUP = "PENDING_SETUP"
    ACTIVE = "ACTIVE"
    FINISHED = "FINISHED"


class PlayerRole(StrEnum):
    HOST = "HOST"
    MEMBER = "MEMBER"


class TileFamily(StrEnum):
    CHARACTERS = "CHARACTERS"
    BAMBOO = "BAMBOO"
    DOTS = "DOTS"
    WIND = "WIND"
    DRAGON = "DRAGON"
    FLOWER = "FLOWER"
    SEASON = "SEASON"
    ANIMAL = "ANIMAL"


class MeldKind(StrEnum):
    CHOW = "CHOW"
    PONG = "PONG"
    KONG = "KONG"


class ClaimKind(StrEnum):
    CHOW = "CHOW"
    PONG = "PONG"
    KONG = "KONG"
    WIN = "WIN"
    PASS = "PASS"


class HandOutcome(StrEnum):
    WIN = "WIN"
    TIE = "TIE"
    ABORTED = "ABORTED"


class WinSource(StrEnum):
    SELF_DRAW = "SELF_DRAW"
    DISCARD = "DISCARD"
    ROBBED_KONG = "ROBBED_KONG"


class TileFace(GameModel):
    """Logical face shared by one or more uniquely identified physical tiles."""

    family: TileFamily
    value: int | str

    @model_validator(mode="after")
    def validate_face(self) -> "TileFace":
        if self.family in {
            TileFamily.CHARACTERS,
            TileFamily.BAMBOO,
            TileFamily.DOTS,
        }:
            if not isinstance(self.value, int) or isinstance(self.value, bool):
                raise ValueError("suited tile values must be integer ranks")
            if not 1 <= self.value <= 9:
                raise ValueError("suited tile ranks must be between 1 and 9")
        else:
            if not isinstance(self.value, str) or not self.value.strip():
                raise ValueError("honour and bonus tile values must be non-empty names")
        return self


class PhysicalTile(GameModel):
    tile_id: TileId = Field(min_length=1)
    face: TileFace


class ExternalSeatController(GameModel):
    type: Literal["external"] = "external"
    player_id: PlayerId = Field(min_length=1)


class AutomatedSeatController(GameModel):
    type: Literal["automated"] = "automated"
    policy_id: PolicyId = Field(min_length=1)


SeatController = Annotated[
    ExternalSeatController | AutomatedSeatController,
    Field(discriminator="type"),
]


class PlayerState(GameModel):
    player_id: PlayerId = Field(min_length=1)
    display_name: str = Field(min_length=1, max_length=64)
    role: PlayerRole = PlayerRole.MEMBER
    ready: bool = False
    joined_at_ms: int = Field(ge=0)


class SeatState(GameModel):
    seat_id: SeatId = Field(min_length=1)
    slot: int = Field(ge=0, lt=4)
    controller: SeatController | None = None
    occupant_name: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_occupancy(self) -> "SeatState":
        if self.controller is None and self.occupant_name is not None:
            raise ValueError("an empty seat cannot have an occupant name")
        if self.controller is not None and self.occupant_name is None:
            raise ValueError("an occupied seat requires an occupant name")
        return self


class MeldState(GameModel):
    kind: MeldKind
    tiles: tuple[PhysicalTile, ...]
    claimed_from_seat_id: SeatId | None = None
    discard_sequence: int | None = Field(default=None, ge=1)
    concealed: bool = False

    @model_validator(mode="after")
    def validate_size(self) -> "MeldState":
        expected = 4 if self.kind is MeldKind.KONG else 3
        if len(self.tiles) != expected:
            raise ValueError(f"{self.kind.value} melds require exactly {expected} tiles")
        tile_ids = [tile.tile_id for tile in self.tiles]
        if len(tile_ids) != len(set(tile_ids)):
            raise ValueError("a meld cannot contain the same physical tile twice")
        if (self.claimed_from_seat_id is None) != (self.discard_sequence is None):
            raise ValueError(
                "claimed_from_seat_id and discard_sequence must be set together"
            )
        if self.concealed and self.claimed_from_seat_id is not None:
            raise ValueError("a concealed meld cannot carry discard claim provenance")
        return self


class DiscardState(GameModel):
    sequence: int = Field(ge=1)
    tile: PhysicalTile
    discarded_by_seat_id: SeatId = Field(min_length=1)
    claimed_by_seat_id: SeatId | None = None
    claim_kind: ClaimKind | None = None

    @model_validator(mode="after")
    def validate_claim(self) -> "DiscardState":
        if (self.claimed_by_seat_id is None) != (self.claim_kind is None):
            raise ValueError("claimed seat and claim kind must be recorded together")
        if self.claim_kind is ClaimKind.PASS:
            raise ValueError("a discarded tile cannot be claimed as PASS")
        if self.claimed_by_seat_id == self.discarded_by_seat_id:
            raise ValueError("a seat cannot claim its own discard")
        return self


class PendingClaim(GameModel):
    window_id: WindowId = Field(min_length=1)
    seat_id: SeatId = Field(min_length=1)
    kind: ClaimKind
    tile_ids: tuple[TileId, ...] = ()

    @model_validator(mode="after")
    def validate_claim_tiles(self) -> "PendingClaim":
        if len(self.tile_ids) != len(set(self.tile_ids)):
            raise ValueError("a claim cannot name a physical tile twice")
        required = {
            ClaimKind.CHOW: 2,
            ClaimKind.PONG: 2,
            ClaimKind.KONG: 3,
            ClaimKind.WIN: 0,
            ClaimKind.PASS: 0,
        }[self.kind]
        if len(self.tile_ids) != required:
            raise ValueError(
                f"{self.kind.value} pending claims require exactly {required} tile IDs"
            )
        return self


class Payment(GameModel):
    sequence: int = Field(ge=1)
    payer_seat_id: SeatId = Field(min_length=1)
    recipient_seat_id: SeatId = Field(min_length=1)
    amount: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_parties(self) -> "Payment":
        if self.payer_seat_id == self.recipient_seat_id:
            raise ValueError("payer and recipient must be different seats")
        return self


class FanAward(GameModel):
    name: str = Field(min_length=1, max_length=128)
    fan: int = Field(gt=0)


class HandResult(GameModel):
    outcome: HandOutcome
    winner_seat_id: SeatId | None = None
    provider_seat_id: SeatId | None = None
    win_source: WinSource | None = None
    fan: int = Field(default=0, ge=0)
    fan_awards: tuple[FanAward, ...] = ()
    payments: tuple[Payment, ...] = ()
    reason: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def validate_outcome(self) -> "HandResult":
        if self.outcome is HandOutcome.WIN:
            if self.winner_seat_id is None or self.win_source is None:
                raise ValueError("a winning result requires a winner and win source")
            if (
                self.win_source in {WinSource.DISCARD, WinSource.ROBBED_KONG}
                and self.provider_seat_id is None
            ):
                raise ValueError("a discard-based win requires a provider")
            if (
                self.win_source is WinSource.SELF_DRAW
                and self.provider_seat_id is not None
            ):
                raise ValueError("a self-drawn win cannot have a provider")
            if self.winner_seat_id == self.provider_seat_id:
                raise ValueError("winner and provider must be different seats")
        elif any(
            value is not None
            for value in (
                self.winner_seat_id,
                self.provider_seat_id,
                self.win_source,
            )
        ):
            raise ValueError("a non-winning result cannot identify a winner or source")
        return self


class SetupPhase(GameModel):
    type: Literal["setup"] = "setup"


class AwaitingDrawPhase(GameModel):
    type: Literal["awaitingDraw"] = "awaitingDraw"
    seat_id: SeatId = Field(min_length=1)


class AwaitingDiscardPhase(GameModel):
    type: Literal["awaitingDiscard"] = "awaitingDiscard"
    seat_id: SeatId = Field(min_length=1)


class DiscardClaimsPhase(GameModel):
    type: Literal["discardClaims"] = "discardClaims"
    window_id: WindowId = Field(min_length=1)
    discard_sequence: int = Field(ge=1)
    eligible_seat_ids: tuple[SeatId, ...] = ()


class KongReplacementPhase(GameModel):
    type: Literal["kongReplacement"] = "kongReplacement"
    seat_id: SeatId = Field(min_length=1)


class KongRobberyPhase(GameModel):
    type: Literal["kongRobbery"] = "kongRobbery"
    window_id: WindowId = Field(min_length=1)
    declaring_seat_id: SeatId = Field(min_length=1)
    eligible_seat_ids: tuple[SeatId, ...] = ()


class CompletePhase(GameModel):
    type: Literal["complete"] = "complete"


HandPhase = Annotated[
    SetupPhase
    | AwaitingDrawPhase
    | AwaitingDiscardPhase
    | DiscardClaimsPhase
    | KongReplacementPhase
    | KongRobberyPhase
    | CompletePhase,
    Field(discriminator="type"),
]


class PlayerHand(GameModel):
    seat_id: SeatId = Field(min_length=1)
    concealed_tiles: tuple[PhysicalTile, ...] = ()
    drawn_tile: PhysicalTile | None = None
    melds: tuple[MeldState, ...] = ()
    bonus_tiles: tuple[PhysicalTile, ...] = ()
    initial_tile_ids: tuple[TileId, ...] = ()

    @model_validator(mode="after")
    def validate_physical_tiles(self) -> "PlayerHand":
        tiles = [*self.concealed_tiles, *self.bonus_tiles]
        if self.drawn_tile is not None:
            tiles.append(self.drawn_tile)
        for meld in self.melds:
            tiles.extend(meld.tiles)
        tile_ids = [tile.tile_id for tile in tiles]
        if len(tile_ids) != len(set(tile_ids)):
            raise ValueError("a player hand cannot contain a physical tile twice")
        if len(self.initial_tile_ids) != len(set(self.initial_tile_ids)):
            raise ValueError("initial_tile_ids cannot contain duplicates")
        return self


class WallState(GameModel):
    live_tiles: tuple[PhysicalTile, ...] = ()
    reserve_tiles: tuple[PhysicalTile, ...] = ()

    @model_validator(mode="after")
    def validate_unique_tiles(self) -> "WallState":
        tile_ids = [
            *(tile.tile_id for tile in self.live_tiles),
            *(tile.tile_id for tile in self.reserve_tiles),
        ]
        if len(tile_ids) != len(set(tile_ids)):
            raise ValueError("wall sections cannot contain a physical tile twice")
        return self


class HandState(GameModel):
    hand_id: HandId = Field(min_length=1)
    phase: HandPhase = Field(default_factory=SetupPhase)
    wall: WallState = Field(default_factory=WallState)
    player_hands: tuple[PlayerHand, ...]
    discards: tuple[DiscardState, ...] = ()
    pending_claims: tuple[PendingClaim, ...] = ()
    payments: tuple[Payment, ...] = ()
    result: HandResult | None = None

    @model_validator(mode="after")
    def validate_hand(self) -> "HandState":
        if len(self.player_hands) != 4:
            raise ValueError("a Singapore Mahjong hand requires exactly four seats")
        seat_ids = [hand.seat_id for hand in self.player_hands]
        if len(seat_ids) != len(set(seat_ids)):
            raise ValueError("player_hands must have unique seat IDs")
        sequences = [discard.sequence for discard in self.discards]
        if sequences != list(range(1, len(sequences) + 1)):
            raise ValueError("discard sequences must be contiguous starting at one")
        payment_sequences = [payment.sequence for payment in self.payments]
        if payment_sequences != list(range(1, len(payment_sequences) + 1)):
            raise ValueError("payment sequences must be contiguous starting at one")
        if isinstance(self.phase, CompletePhase) != (self.result is not None):
            raise ValueError("complete phase and hand result must be set together")

        seat_id_set = set(seat_ids)
        if any(
            discard.discarded_by_seat_id not in seat_id_set
            or (
                discard.claimed_by_seat_id is not None
                and discard.claimed_by_seat_id not in seat_id_set
            )
            for discard in self.discards
        ):
            raise ValueError("discard references an unknown seat")
        phase_seat_ids: tuple[SeatId, ...]
        if isinstance(
            self.phase,
            (AwaitingDrawPhase, AwaitingDiscardPhase, KongReplacementPhase),
        ):
            phase_seat_ids = (self.phase.seat_id,)
        elif isinstance(self.phase, DiscardClaimsPhase):
            phase_seat_ids = self.phase.eligible_seat_ids
        elif isinstance(self.phase, KongRobberyPhase):
            phase_seat_ids = (
                self.phase.declaring_seat_id,
                *self.phase.eligible_seat_ids,
            )
        else:
            phase_seat_ids = ()
        if not set(phase_seat_ids).issubset(seat_id_set):
            raise ValueError("hand phase references an unknown seat")
        if len(phase_seat_ids) != len(set(phase_seat_ids)):
            raise ValueError("hand phase seat IDs must be unique")
        if isinstance(self.phase, DiscardClaimsPhase) and (
            not self.discards
            or self.phase.discard_sequence != self.discards[-1].sequence
        ):
            raise ValueError(
                "discard claim phase must identify the current ledger discard"
            )

        if any(claim.seat_id not in seat_id_set for claim in self.pending_claims):
            raise ValueError("pending claim references an unknown seat")
        claim_keys = [
            (claim.window_id, claim.seat_id) for claim in self.pending_claims
        ]
        if len(claim_keys) != len(set(claim_keys)):
            raise ValueError("a seat can submit only one claim per window")
        active_window_id = (
            self.phase.window_id
            if isinstance(self.phase, (DiscardClaimsPhase, KongRobberyPhase))
            else None
        )
        if any(claim.window_id != active_window_id for claim in self.pending_claims):
            raise ValueError("pending claims must belong to the active claim window")
        eligible_claim_seat_ids = (
            set(self.phase.eligible_seat_ids)
            if isinstance(self.phase, (DiscardClaimsPhase, KongRobberyPhase))
            else set()
        )
        if any(
            claim.seat_id not in eligible_claim_seat_ids
            for claim in self.pending_claims
        ):
            raise ValueError("pending claim seat is not eligible for the active phase")
        if any(
            payment.payer_seat_id not in seat_id_set
            or payment.recipient_seat_id not in seat_id_set
            for payment in self.payments
        ):
            raise ValueError("payment references an unknown seat")
        if self.result is not None:
            if any(
                seat_id is not None and seat_id not in seat_id_set
                for seat_id in (
                    self.result.winner_seat_id,
                    self.result.provider_seat_id,
                )
            ):
                raise ValueError("hand result references an unknown seat")
            if any(
                payment.payer_seat_id not in seat_id_set
                or payment.recipient_seat_id not in seat_id_set
                for payment in self.result.payments
            ):
                raise ValueError("hand result payment references an unknown seat")

        live_tile_ids = {
            tile.tile_id for tile in (*self.wall.live_tiles, *self.wall.reserve_tiles)
        }
        held_tiles: list[tuple[PhysicalTile, SeatId, str]] = []
        for hand in self.player_hands:
            held_tiles.extend(
                (tile, hand.seat_id, "concealed") for tile in hand.concealed_tiles
            )
            held_tiles.extend(
                (tile, hand.seat_id, "bonus") for tile in hand.bonus_tiles
            )
            held_tiles.extend(
                (tile, hand.seat_id, "meld")
                for meld in hand.melds
                for tile in meld.tiles
            )
            if hand.drawn_tile is not None:
                held_tiles.append((hand.drawn_tile, hand.seat_id, "drawn"))
        held_tile_ids = [tile.tile_id for tile, _, _ in held_tiles]
        if live_tile_ids.intersection(held_tile_ids):
            raise ValueError("a physical tile cannot be both in the wall and held")
        if len(held_tile_ids) != len(set(held_tile_ids)):
            raise ValueError("a physical tile cannot be held by more than one seat")

        discard_tile_ids = [discard.tile.tile_id for discard in self.discards]
        if len(discard_tile_ids) != len(set(discard_tile_ids)):
            raise ValueError("a physical tile cannot appear in the discard ledger twice")
        if live_tile_ids.intersection(discard_tile_ids):
            raise ValueError("a physical tile cannot be both in the wall and discarded")
        held_by_id = {
            tile.tile_id: (tile, seat_id, location)
            for tile, seat_id, location in held_tiles
        }
        meld_claim_kinds = {ClaimKind.CHOW, ClaimKind.PONG, ClaimKind.KONG}
        meld_kind_to_claim_kind = {
            MeldKind.CHOW: ClaimKind.CHOW,
            MeldKind.PONG: ClaimKind.PONG,
            MeldKind.KONG: ClaimKind.KONG,
        }
        discards_by_sequence = {
            discard.sequence: discard for discard in self.discards
        }
        claimed_meld_sequences: set[int] = set()
        for hand in self.player_hands:
            for meld in hand.melds:
                if meld.discard_sequence is None:
                    continue
                discard = discards_by_sequence.get(meld.discard_sequence)
                if discard is None:
                    raise ValueError(
                        "claimed meld provenance references an unknown discard"
                    )
                if meld.discard_sequence in claimed_meld_sequences:
                    raise ValueError(
                        "a ledger discard cannot provide more than one claimed meld"
                    )
                if (
                    discard.claim_kind is not meld_kind_to_claim_kind[meld.kind]
                    or discard.claimed_by_seat_id != hand.seat_id
                    or discard.discarded_by_seat_id != meld.claimed_from_seat_id
                    or discard.tile not in meld.tiles
                ):
                    raise ValueError(
                        "claimed meld provenance does not match its ledger discard"
                    )
                claimed_meld_sequences.add(meld.discard_sequence)
        for discard in self.discards:
            held = held_by_id.get(discard.tile.tile_id)
            if discard.claim_kind in meld_claim_kinds:
                if (
                    discard.sequence not in claimed_meld_sequences
                    or held is None
                    or held[1] != discard.claimed_by_seat_id
                    or held[2] != "meld"
                    or held[0] != discard.tile
                ):
                    raise ValueError(
                        "a meld-claimed discard must be the same physical tile in "
                        "the claimant's meld"
                    )
            elif held is not None:
                raise ValueError(
                    "only a Chow, Pong, or Kong claimed discard may also appear "
                    "in a player's held tiles"
                )
        return self


class SeatBalance(GameModel):
    seat_id: SeatId = Field(min_length=1)
    points: int = 0


class MatchResult(GameModel):
    final_balances: tuple[SeatBalance, ...]
    winning_seat_ids: tuple[SeatId, ...] = ()
    completed_at_ms: int = Field(ge=0)
    reason: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def validate_result(self) -> "MatchResult":
        if len(self.final_balances) != 4:
            raise ValueError("a match result requires four final balances")
        seat_ids = [balance.seat_id for balance in self.final_balances]
        if len(seat_ids) != len(set(seat_ids)):
            raise ValueError("match result balances must have unique seat IDs")
        if len(self.winning_seat_ids) != len(set(self.winning_seat_ids)):
            raise ValueError("winning_seat_ids cannot contain duplicates")
        if not set(self.winning_seat_ids).issubset(set(seat_ids)):
            raise ValueError("winning_seat_ids must identify match seats")
        return self


class MatchState(GameModel):
    match_id: MatchId = Field(min_length=1)
    status: MatchStatus = MatchStatus.ACTIVE
    prevailing_wind: Wind = Wind.EAST
    dealer_seat_id: SeatId | None = Field(min_length=1)
    current_hand: HandState | None = None
    hand_history: tuple[HandResult, ...] = ()
    balances: tuple[SeatBalance, ...]
    result: MatchResult | None = None

    @model_validator(mode="after")
    def validate_match(self) -> "MatchState":
        if len(self.balances) != 4:
            raise ValueError("a match requires exactly four seat balances")
        seat_ids = [balance.seat_id for balance in self.balances]
        if len(seat_ids) != len(set(seat_ids)):
            raise ValueError("match balances must have unique seat IDs")
        if self.dealer_seat_id is not None and self.dealer_seat_id not in set(seat_ids):
            raise ValueError("dealer_seat_id must identify a match seat")
        seat_id_set = set(seat_ids)
        if self.current_hand is not None and {
            hand.seat_id for hand in self.current_hand.player_hands
        } != seat_id_set:
            raise ValueError("current hand seats must match match balances")
        for result in self.hand_history:
            if any(
                seat_id is not None and seat_id not in seat_id_set
                for seat_id in (result.winner_seat_id, result.provider_seat_id)
            ):
                raise ValueError("hand history result references an unknown seat")
            if any(
                payment.payer_seat_id not in seat_id_set
                or payment.recipient_seat_id not in seat_id_set
                for payment in result.payments
            ):
                raise ValueError(
                    "hand history result payment references an unknown seat"
                )
        if self.status is MatchStatus.PENDING_SETUP:
            if self.dealer_seat_id is not None or self.current_hand is not None:
                raise ValueError(
                    "a pending-setup match cannot have a dealer or current hand"
                )
            if self.hand_history or self.result is not None:
                raise ValueError(
                    "a pending-setup match cannot have history or a result"
                )
            if any(balance.points != 0 for balance in self.balances):
                raise ValueError("a pending-setup match requires zero balances")
        elif self.status is MatchStatus.ACTIVE:
            if self.dealer_seat_id is None:
                raise ValueError("an active match requires a dealer")
            if self.current_hand is None:
                raise ValueError("an active match requires a current hand")
            if self.result is not None:
                raise ValueError("an active match cannot have a result")
        else:
            if self.dealer_seat_id is None:
                raise ValueError("a finished match requires its final dealer")
            if self.current_hand is not None:
                raise ValueError("a finished match cannot retain a current hand")
            if self.result is None:
                raise ValueError("a finished match requires a result")
            if {
                balance.seat_id for balance in self.result.final_balances
            } != seat_id_set:
                raise ValueError("match result seats must match match balances")
        return self


class RoomState(GameModel):
    room_id: RoomId = Field(min_length=1)
    ruleset_id: Literal["singapore"] = "singapore"
    ruleset_version: Literal["0.1.0"] = "0.1.0"
    state_schema_version: Literal[2] = 2
    revision: int = Field(default=0, ge=0)
    config: GameConfig = Field(default_factory=GameConfig)
    status: RoomStatus = RoomStatus.CREATED
    seats: tuple[SeatState, ...]
    players: tuple[PlayerState, ...] = ()
    match: MatchState | None = None
    created_at_ms: int = Field(ge=0)
    updated_at_ms: int = Field(ge=0)

    def canonical_data(self) -> dict[str, Any]:
        # ``model_copy(update=...)`` intentionally skips Pydantic validation.
        # Recheck the capability gate at the persistence serialization boundary.
        if self.config != GameConfig():
            raise ValueError(
                "ruleset 0.1.0 cannot serialize unsupported game configuration"
            )
        return super().canonical_data()

    @model_validator(mode="after")
    def validate_room(self) -> "RoomState":
        if self.config != GameConfig():
            raise ValueError(
                "ruleset 0.1.0 does not permit non-default game configuration"
            )
        if len(self.seats) != 4:
            raise ValueError("a room requires exactly four stable seat slots")
        slots = [seat.slot for seat in self.seats]
        if set(slots) != {0, 1, 2, 3}:
            raise ValueError("room seat slots must be exactly 0, 1, 2, and 3")
        seat_ids = [seat.seat_id for seat in self.seats]
        if len(seat_ids) != len(set(seat_ids)):
            raise ValueError("room seats must have unique seat IDs")
        player_ids = [player.player_id for player in self.players]
        if len(player_ids) != len(set(player_ids)):
            raise ValueError("room players must have unique player IDs")
        host_count = sum(player.role is PlayerRole.HOST for player in self.players)
        if self.players and host_count != 1:
            raise ValueError("a non-empty room must have exactly one host")

        external_player_ids: list[PlayerId] = []
        players_by_id = {player.player_id: player for player in self.players}
        for seat in self.seats:
            if isinstance(seat.controller, ExternalSeatController):
                external_player_ids.append(seat.controller.player_id)
                player = players_by_id.get(seat.controller.player_id)
                if player is not None and seat.occupant_name != player.display_name:
                    raise ValueError(
                        "an external seat occupant name must match its player"
                    )
        if len(external_player_ids) != len(set(external_player_ids)):
            raise ValueError("an external player cannot control more than one seat")
        if set(external_player_ids) != set(player_ids):
            raise ValueError("every room player must control exactly one external seat")

        if self.status is RoomStatus.IN_MATCH:
            if self.match is None or self.match.status not in {
                MatchStatus.PENDING_SETUP,
                MatchStatus.ACTIVE,
            }:
                raise ValueError("IN_MATCH rooms require a pending or active match")
            if any(seat.controller is None for seat in self.seats):
                raise ValueError("IN_MATCH rooms require four occupied seats")
            if (
                self.match.status is MatchStatus.PENDING_SETUP
                and any(not player.ready for player in self.players)
            ):
                raise ValueError(
                    "a pending-setup match requires every human player ready"
                )
        elif self.status is RoomStatus.READY:
            if any(seat.controller is None for seat in self.seats):
                raise ValueError("READY rooms require four occupied seats")
            if any(not player.ready for player in self.players):
                raise ValueError("READY rooms require every human player to be ready")
        elif self.status is RoomStatus.WAITING_FOR_PLAYERS:
            if all(seat.controller is not None for seat in self.seats) and all(
                player.ready for player in self.players
            ):
                raise ValueError(
                    "a fully occupied room with every human ready must be READY"
                )
        elif self.status is RoomStatus.FINISHED:
            if self.match is not None and self.match.status is not MatchStatus.FINISHED:
                raise ValueError("FINISHED rooms cannot retain an active match")
        if self.match is not None and self.status not in {
            RoomStatus.IN_MATCH,
            RoomStatus.FINISHED,
        }:
            raise ValueError("only IN_MATCH or FINISHED rooms may contain a match")
        if self.match is not None and {
            balance.seat_id for balance in self.match.balances
        } != set(seat_ids):
            raise ValueError("match seats must match the room's stable seats")
        if self.updated_at_ms < self.created_at_ms:
            raise ValueError("updated_at_ms cannot precede created_at_ms")
        return self


def standard_seats() -> tuple[SeatState, SeatState, SeatState, SeatState]:
    """Return the four stable empty table slots used by new rooms."""

    return (
        SeatState(seat_id=SeatId("seat-0"), slot=0),
        SeatState(seat_id=SeatId("seat-1"), slot=1),
        SeatState(seat_id=SeatId("seat-2"), slot=2),
        SeatState(seat_id=SeatId("seat-3"), slot=3),
    )
