from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.game import (
    ClaimKind,
    DiscardState,
    DiscardClaimsPhase,
    Draw,
    ExternalSeatController,
    HandId,
    HandState,
    MatchId,
    MatchState,
    MeldKind,
    MeldState,
    OpponentSeatObservation,
    OpponentSeatView,
    OpaqueActionDescriptor,
    PendingClaim,
    PhysicalTile,
    PlayerHand,
    PlayerId,
    PlayerRole,
    PlayerState,
    PublicConcealedMeldView,
    PublicExposedMeldView,
    RoomId,
    RoomState,
    RoomStatus,
    SeatBalance,
    SeatId,
    SeatState,
    TileFace,
    TileFamily,
    TileId,
    WallState,
    WindowId,
    build_player_observation,
    build_public_room_view,
)


def tile(
    tile_id: str,
    *,
    family: TileFamily = TileFamily.DOTS,
    value: int | str = 1,
) -> PhysicalTile:
    return PhysicalTile(
        tile_id=TileId(tile_id),
        face=TileFace(family=family, value=value),
    )


def private_room() -> RoomState:
    player_ids = tuple(PlayerId(f"player-{index}") for index in range(4))
    seat_ids = tuple(SeatId(f"seat-{index}") for index in range(4))
    players = tuple(
        PlayerState(
            player_id=player_id,
            display_name=f"Player {index}",
            role=PlayerRole.HOST if index == 0 else PlayerRole.MEMBER,
            ready=True,
            joined_at_ms=index,
        )
        for index, player_id in enumerate(player_ids)
    )
    seats = tuple(
        SeatState(
            seat_id=seat_id,
            slot=index,
            controller=ExternalSeatController(player_id=player_ids[index]),
            occupant_name=f"Player {index}",
        )
        for index, seat_id in enumerate(seat_ids)
    )
    hands = (
        PlayerHand(
            seat_id=seat_ids[0],
            concealed_tiles=(tile("OWN_CONCEALED_SENTINEL"),),
            drawn_tile=tile("OWN_DRAWN_SENTINEL"),
            melds=(
                MeldState(
                    kind=MeldKind.PONG,
                    tiles=(
                        tile("OWN_EXPOSED_MELD_ID_1"),
                        tile("OWN_EXPOSED_MELD_ID_2"),
                        tile("OWN_EXPOSED_MELD_ID_3"),
                    ),
                ),
            ),
            bonus_tiles=(
                tile(
                    "OWN_BONUS_TILE_ID",
                    family=TileFamily.ANIMAL,
                    value="OWN_BONUS_FACE_PUBLIC",
                ),
            ),
        ),
        PlayerHand(
            seat_id=seat_ids[1],
            concealed_tiles=(tile("OPPONENT_CONCEALED_SENTINEL"),),
            drawn_tile=tile("OPPONENT_DRAWN_SENTINEL"),
            melds=(
                MeldState(
                    kind=MeldKind.PONG,
                    tiles=(
                        tile("OPPONENT_EXPOSED_MELD_ID_1"),
                        tile("OPPONENT_EXPOSED_MELD_ID_2"),
                        tile("OPPONENT_EXPOSED_MELD_ID_3"),
                    ),
                ),
                MeldState(
                    kind=MeldKind.KONG,
                    concealed=True,
                    tiles=tuple(
                        tile(
                            f"CONCEALED_MELD_PHYSICAL_ID_{index}",
                            family=TileFamily.DRAGON,
                            value="CONCEALED_MELD_FACE_SENTINEL",
                        )
                        for index in range(4)
                    ),
                ),
            ),
            bonus_tiles=(
                tile(
                    "OPPONENT_BONUS_TILE_ID",
                    family=TileFamily.ANIMAL,
                    value="OPPONENT_BONUS_FACE_PUBLIC",
                ),
            ),
        ),
        PlayerHand(
            seat_id=seat_ids[2], concealed_tiles=(tile("SEAT_TWO_SECRET"),)
        ),
        PlayerHand(
            seat_id=seat_ids[3], concealed_tiles=(tile("SEAT_THREE_SECRET"),)
        ),
    )
    hand = HandState(
        hand_id=HandId("hand-1"),
        phase=DiscardClaimsPhase(
            window_id=WindowId("window-PRIVATE_PHASE"),
            discard_sequence=1,
            eligible_seat_ids=(seat_ids[0], seat_ids[1]),
        ),
        wall=WallState(
            live_tiles=(tile("LIVE_WALL_SENTINEL"),),
            reserve_tiles=(tile("RESERVE_WALL_SENTINEL"),),
        ),
        player_hands=hands,
        discards=(
            DiscardState(
                sequence=1,
                tile=tile(
                    "DISCARD_PHYSICAL_TILE_ID",
                    family=TileFamily.DRAGON,
                    value="DISCARD_FACE_PUBLIC",
                ),
                discarded_by_seat_id=seat_ids[2],
            ),
        ),
        pending_claims=(
            PendingClaim(
                window_id=WindowId("window-PRIVATE_PHASE"),
                seat_id=seat_ids[0],
                kind=ClaimKind.CHOW,
                tile_ids=(
                    TileId("OWN_PENDING_CLAIM_SENTINEL"),
                    TileId("OWN_PENDING_CLAIM_HELPER"),
                ),
            ),
            PendingClaim(
                window_id=WindowId("window-PRIVATE_PHASE"),
                seat_id=seat_ids[1],
                kind=ClaimKind.PONG,
                tile_ids=(
                    TileId("OPPONENT_PENDING_CLAIM_SENTINEL"),
                    TileId("OPPONENT_PENDING_CLAIM_HELPER"),
                ),
            ),
        ),
    )
    match = MatchState(
        match_id=MatchId("match-1"),
        dealer_seat_id=seat_ids[0],
        current_hand=hand,
        balances=tuple(SeatBalance(seat_id=seat_id) for seat_id in seat_ids),
    )
    return RoomState(
        room_id=RoomId("room-private"),
        revision=3,
        status=RoomStatus.IN_MATCH,
        seats=seats,
        players=players,
        match=match,
        created_at_ms=10,
        updated_at_ms=20,
    )


class ObservationPrivacyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.room = private_room()
        self.viewer = PlayerId("player-0")

    def test_observation_exposes_only_viewers_private_tiles_and_claim(self) -> None:
        observation = build_player_observation(self.room, self.viewer)
        encoded = observation.canonical_json()
        self.assertIn("OWN_CONCEALED_SENTINEL", encoded)
        self.assertIn("OWN_DRAWN_SENTINEL", encoded)
        self.assertIn("OWN_PENDING_CLAIM_SENTINEL", encoded)
        self.assertNotIn("OPPONENT_CONCEALED_SENTINEL", encoded)
        self.assertNotIn("OPPONENT_DRAWN_SENTINEL", encoded)
        self.assertNotIn("OPPONENT_PENDING_CLAIM_SENTINEL", encoded)
        self.assertNotIn("LIVE_WALL_SENTINEL", encoded)
        self.assertNotIn("RESERVE_WALL_SENTINEL", encoded)
        for physical_id in (
            "OWN_EXPOSED_MELD_ID_1",
            "OWN_BONUS_TILE_ID",
            "OPPONENT_EXPOSED_MELD_ID_1",
            "OPPONENT_BONUS_TILE_ID",
            "CONCEALED_MELD_PHYSICAL_ID_1",
            "DISCARD_PHYSICAL_TILE_ID",
        ):
            self.assertNotIn(physical_id, encoded)
        self.assertNotIn("CONCEALED_MELD_FACE_SENTINEL", encoded)
        self.assertIn("OWN_BONUS_FACE_PUBLIC", encoded)
        self.assertIn("OPPONENT_BONUS_FACE_PUBLIC", encoded)
        self.assertIn("DISCARD_FACE_PUBLIC", encoded)

        own = observation.seats[0]
        opponent = observation.seats[1]
        self.assertIsInstance(own.melds[0], PublicExposedMeldView)
        self.assertFalse(hasattr(own.melds[0].tiles[0], "tile_id"))
        self.assertFalse(hasattr(own.bonus_tiles[0], "tile_id"))
        self.assertIsInstance(opponent.melds[1], PublicConcealedMeldView)
        self.assertEqual(opponent.melds[1].kind, MeldKind.KONG)
        self.assertEqual(opponent.melds[1].tile_count, 4)
        self.assertFalse(hasattr(opponent.melds[1], "tiles"))
        self.assertFalse(hasattr(observation.match.discards[0].tile, "tile_id"))

        self.assertIsInstance(opponent, OpponentSeatObservation)
        self.assertEqual(opponent.concealed_tile_count, 1)
        self.assertTrue(opponent.has_drawn_tile)
        self.assertFalse(hasattr(opponent, "concealed_tiles"))

    def test_observation_and_projection_reject_advertised_capabilities(self) -> None:
        with self.assertRaises(ValidationError):
            build_player_observation(
                self.room,
                self.viewer,
                capabilities=("draw",),  # type: ignore[arg-type]
            )
        with self.assertRaises(ValidationError):
            build_public_room_view(
                self.room,
                self.viewer,
                server_time_ms=30,
                capabilities=("draw",),  # type: ignore[arg-type]
            )

    def test_ui_projection_is_separate_and_never_exposes_pending_claims(self) -> None:
        view = build_public_room_view(
            self.room,
            self.viewer,
            server_time_ms=30,
            actions=(OpaqueActionDescriptor(action_id="opaque-123", label="Choice"),),
        )
        encoded = view.canonical_json()
        self.assertIn("OWN_CONCEALED_SENTINEL", encoded)
        self.assertIn("opaque-123", encoded)
        for sentinel in (
            "OPPONENT_CONCEALED_SENTINEL",
            "OPPONENT_DRAWN_SENTINEL",
            "OWN_PENDING_CLAIM_SENTINEL",
            "OPPONENT_PENDING_CLAIM_SENTINEL",
            "LIVE_WALL_SENTINEL",
            "RESERVE_WALL_SENTINEL",
            "OWN_EXPOSED_MELD_ID_1",
            "OWN_BONUS_TILE_ID",
            "OPPONENT_EXPOSED_MELD_ID_1",
            "OPPONENT_BONUS_TILE_ID",
            "CONCEALED_MELD_PHYSICAL_ID_1",
            "CONCEALED_MELD_FACE_SENTINEL",
            "DISCARD_PHYSICAL_TILE_ID",
        ):
            self.assertNotIn(sentinel, encoded)
        self.assertIn("OWN_BONUS_FACE_PUBLIC", encoded)
        self.assertIn("OPPONENT_BONUS_FACE_PUBLIC", encoded)
        self.assertIn("DISCARD_FACE_PUBLIC", encoded)

        opponent = view.seats[1]
        self.assertIsInstance(opponent, OpponentSeatView)
        self.assertFalse(hasattr(opponent, "concealed_tiles"))

    def test_ui_action_catalog_rejects_domain_actions(self) -> None:
        with self.assertRaises(ValidationError):
            build_public_room_view(
                self.room,
                self.viewer,
                server_time_ms=30,
                actions=(Draw(seat_id=SeatId("seat-0")),),  # type: ignore[arg-type]
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
