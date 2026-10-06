"""Integrated Game and Kong-1 outcomes on conserved physical rooms."""

from __future__ import annotations

from app.game import (
    AwaitingDiscardPhase, ClaimKind, DeclareWin, Discard, DiscardState, HandOutcome,
    GameConfig, Kong, KongKind, KongRobberyPhase, MeldKind, MeldState, SeatId, TileFamily,
    WinSource, WallState, Pass, PendingClaim, WindowId, validate_room,
)
from app.game.claims import winning_claim
from app.game.singapore_game import _complete_tie, _flower_completion, _room_with_hand, _updated
from app.game.tiles import sort_playable_tiles
from test_game_claims import started
from test_game_setup import IdentityRandomSource


def robbery_room():
    engine, state = started(IdentityRandomSource())
    hand = state.match.current_hand
    pool = [
        *hand.wall.live_tiles,
        *(tile for player in hand.player_hands for tile in (
            *player.concealed_tiles,
            *((player.drawn_tile,) if player.drawn_tile else ()),
        )),
    ]

    def take(family, value):
        tile = next(tile for tile in pool if tile.face.family is family and tile.face.value == value)
        pool.remove(tile)
        return tile

    targets = [take(TileFamily.BAMBOO, 5) for _ in range(4)]
    wait_faces = [
        *((TileFamily.DRAGON, "RED") for _ in range(3)),
        *((TileFamily.DOTS, value) for value in (1, 2, 3, 9, 9)),
        *((TileFamily.CHARACTERS, value) for value in (1, 2, 3)),
        (TileFamily.BAMBOO, 3), (TileFamily.BAMBOO, 4),
    ]
    waiting = [take(family, value) for family, value in wait_faces]
    seat_zero = [pool.pop(0) for _ in range(13)]
    seat_one = [pool.pop(0) for _ in range(10)]
    seat_three = [pool.pop(0) for _ in range(13)]
    meld = MeldState(
        kind=MeldKind.PONG, tiles=tuple(targets[:3]),
        claimed_from_seat_id=SeatId("seat-0"), discard_sequence=1,
    )
    regular = (
        (seat_zero, None, ()),
        (seat_one, targets[3], (meld,)),
        (waiting, None, ()),
        (seat_three, None, ()),
    )
    players = []
    for index, (concealed, drawn, melds) in enumerate(regular):
        original = hand.player_hands[index]
        held = [*concealed, *((drawn,) if drawn else ()), *(tile for item in melds for tile in item.tiles), *original.bonus_tiles]
        players.append(_updated(
            original,
            concealed_tiles=sort_playable_tiles(concealed), drawn_tile=drawn,
            melds=melds, initial_tile_ids=tuple(tile.tile_id for tile in held[:13]),
            last_discard_face=targets[0].face if index == 0 else None,
        ))
    prepared = _updated(
        hand,
        phase=AwaitingDiscardPhase(seat_id=SeatId("seat-1")),
        wall=WallState(live_tiles=tuple(pool), reserve_tiles=hand.wall.reserve_tiles),
        player_hands=tuple(players),
        discards=(DiscardState(
            sequence=1, tile=targets[0], discarded_by_seat_id=SeatId("seat-0"),
            claimed_by_seat_id=SeatId("seat-1"), claim_kind=ClaimKind.PONG,
        ),),
    )
    state = _room_with_hand(state, prepared, pending_deadline=None)
    validate_room(state)
    return engine, state


def test_robbed_kong_one_cancels_meld_and_replacement() -> None:
    engine, state = robbery_room()
    kong = next(action for action in engine.legal_actions(state, SeatId("seat-1")) if isinstance(action, Kong) and action.kind is KongKind.ADDED)
    window = engine.transition(state, kong).state
    assert isinstance(window.match.current_hand.phase, KongRobberyPhase)
    assert SeatId("seat-2") in window.match.current_hand.phase.eligible_seat_ids
    assert window.match.current_hand.wall == state.match.current_hand.wall
    game = next(action for action in engine.legal_actions(window, SeatId("seat-2")) if isinstance(action, DeclareWin))
    responded = engine.transition(window, game).state
    completed = engine.resolve_discard_window(responded, window.match.current_hand.phase.window_id).state
    result = completed.match.current_hand.result
    assert result.outcome is HandOutcome.WIN
    assert result.win_source is WinSource.ROBBED_KONG
    assert result.provider_seat_id == SeatId("seat-1")
    assert result.fan >= 1 and result.capped_fan == min(result.fan, 5)
    assert completed.match.current_hand.wall == state.match.current_hand.wall
    assert completed.match.current_hand.player_hands[1].melds[0].kind is MeldKind.PONG
    validate_room(completed)


def test_unrobbed_kong_one_upgrades_pong_after_window() -> None:
    engine, state = robbery_room()
    kong = next(action for action in engine.legal_actions(state, SeatId("seat-1")) if isinstance(action, Kong) and action.kind is KongKind.ADDED)
    window = engine.transition(state, kong).state
    resolved = engine.resolve_discard_window(window, window.match.current_hand.phase.window_id).state
    meld = resolved.match.current_hand.player_hands[1].melds[0]
    assert meld.kind is MeldKind.KONG and meld.kong_kind == "KONG_1"
    assert meld.discard_sequence == 1
    assert resolved.match.current_hand.wall != state.match.current_hand.wall
    kong_payments = [payment for payment in resolved.match.current_hand.payments if payment.reason.startswith("Kong-1")]
    assert len(kong_payments) == 3
    assert all(payment.recipient_seat_id == SeatId("seat-1") for payment in kong_payments)
    assert sum(balance.points for balance in resolved.match.balances) == 0
    validate_room(resolved)


def test_wall_tie_retains_immediate_kong_payments() -> None:
    engine, state = robbery_room()
    kong = next(action for action in engine.legal_actions(state, SeatId("seat-1")) if isinstance(action, Kong) and action.kind is KongKind.ADDED)
    window = engine.transition(state, kong).state
    paid = engine.resolve_discard_window(window, window.match.current_hand.phase.window_id).state
    tied = _complete_tie(paid, paid.match.current_hand)
    assert tied.match.current_hand.result.payments == paid.match.current_hand.payments
    assert tied.match.balances == paid.match.balances


def test_discard_game_beats_pong_and_marks_winning_discard() -> None:
    engine, state = robbery_room()
    tile = state.match.current_hand.player_hands[1].drawn_tile
    discard = Discard(seat_id=SeatId("seat-1"), tile_id=tile.tile_id)
    window = engine.transition(state, discard).state
    game = next(action for action in engine.legal_actions(window, SeatId("seat-2")) if isinstance(action, DeclareWin))
    responded = engine.transition(window, game).state
    resolved = engine.resolve_discard_window(responded, window.match.current_hand.phase.window_id).state
    result = resolved.match.current_hand.result
    assert result.outcome is HandOutcome.WIN and result.win_source is WinSource.DISCARD
    assert resolved.match.current_hand.discards[-1].claim_kind is ClaimKind.WIN
    validate_room(resolved)


def test_configured_minimum_fan_removes_below_threshold_game_claim() -> None:
    engine, state = robbery_room()
    state = state.model_copy(update={"config": GameConfig(minimum_fan=2)})
    tile = state.match.current_hand.player_hands[1].drawn_tile
    window = engine.transition(state, Discard(seat_id=SeatId("seat-1"), tile_id=tile.tile_id)).state
    assert not any(isinstance(action, DeclareWin) for action in engine.legal_actions(window, SeatId("seat-2")))


def test_passing_game_blocks_same_face_until_next_move() -> None:
    engine, state = robbery_room()
    tile = state.match.current_hand.player_hands[1].drawn_tile
    window = engine.transition(state, Discard(seat_id=SeatId("seat-1"), tile_id=tile.tile_id)).state
    passed = engine.transition(
        window, next(action for action in engine.legal_actions(window, SeatId("seat-2")) if isinstance(action, Pass)),
    ).state
    other_game = next(action for action in engine.legal_actions(passed, SeatId("seat-3")) if isinstance(action, DeclareWin))
    passed = engine.transition(passed, other_game).state
    resolved = engine.resolve_discard_window(passed, window.match.current_hand.phase.window_id).state
    assert tile.face in resolved.match.current_hand.player_hands[2].passed_game_faces
    validate_room(resolved)


def test_game_claim_has_highest_priority_and_equal_game_uses_nearest_seat() -> None:
    seats = tuple(SeatId(f"seat-{index}") for index in range(4))
    claims = (
        PendingClaim(window_id=WindowId("window-1"), seat_id=seats[3], kind=ClaimKind.WIN),
        PendingClaim(window_id=WindowId("window-1"), seat_id=seats[2], kind=ClaimKind.KONG, tile_ids=("a", "b", "c")),
        PendingClaim(window_id=WindowId("window-1"), seat_id=seats[1], kind=ClaimKind.WIN),
    )
    assert winning_claim(claims, seats, seats[0]).seat_id == seats[1]


def test_every_claim_priority_pair_uses_priority_then_counterclockwise_distance() -> None:
    seats = tuple(SeatId(f"seat-{index}") for index in range(4))
    priority = {ClaimKind.WIN: 3, ClaimKind.KONG: 2, ClaimKind.PONG: 2, ClaimKind.CHOW: 1}
    tiles_required = {ClaimKind.WIN: 0, ClaimKind.KONG: 3, ClaimKind.PONG: 2, ClaimKind.CHOW: 2}
    for first_kind, first_priority in priority.items():
        for second_kind, second_priority in priority.items():
            first = PendingClaim(
                window_id=WindowId("window-1"), seat_id=seats[1], kind=first_kind,
                tile_ids=tuple(f"first-{index}" for index in range(tiles_required[first_kind])),
            )
            second = PendingClaim(
                window_id=WindowId("window-1"), seat_id=seats[2], kind=second_kind,
                tile_ids=tuple(f"second-{index}" for index in range(tiles_required[second_kind])),
            )
            expected = first if first_priority >= second_priority else second
            assert winning_claim((first, second), seats, seats[0]) == expected
            assert winning_claim((second, first), seats, seats[0]) == expected


def test_seventh_flower_holder_receives_eighth_and_wins() -> None:
    _engine, state = started(IdentityRandomSource())
    hand = state.match.current_hand
    unheld = [*hand.wall.live_tiles, *hand.wall.reserve_tiles]
    flowers = [tile for tile in unheld if tile.face.family in {TileFamily.FLOWER, TileFamily.SEASON}]
    assert len(flowers) == 8
    remaining = [tile for tile in unheld if tile not in flowers]
    players = tuple(
        _updated(
            player,
            bonus_tiles=(*player.bonus_tiles, *(flowers[:7] if index == 2 else flowers[7:] if index == 1 else ())),
        )
        for index, player in enumerate(hand.player_hands)
    )
    prepared = _updated(
        hand,
        player_hands=players,
        wall=WallState(live_tiles=tuple(remaining[:-15]), reserve_tiles=tuple(remaining[-15:])),
    )
    state = _room_with_hand(state, prepared, pending_deadline=None)
    validate_room(state)
    result = _flower_completion(state)
    assert result is not None
    completed = result.state
    assert completed.match.current_hand.result.reason == "SEVEN_FLOWERS"
    assert completed.match.current_hand.result.fan == 10
    assert completed.match.current_hand.result.provider_seat_id == SeatId("seat-1")
    assert len(completed.match.current_hand.player_hands[2].bonus_tiles) == 8
    assert len(completed.match.current_hand.player_hands[1].bonus_tiles) == 0
    assert result.domain_events[0].type == "flowerTransferred"
    validate_room(completed)


def test_self_draw_game_uses_best_decomposition_and_server_fan() -> None:
    engine, state = started(IdentityRandomSource())
    hand = state.match.current_hand
    pool = [
        *hand.wall.live_tiles,
        *(tile for player in hand.player_hands for tile in (
            *player.concealed_tiles,
            *((player.drawn_tile,) if player.drawn_tile else ()),
        )),
    ]
    winning = []
    for rank, count in ((1, 3), (2, 3), (3, 3), (4, 3), (5, 2)):
        for _ in range(count):
            tile = next(tile for tile in pool if tile.face.family is TileFamily.BAMBOO and tile.face.value == rank)
            pool.remove(tile)
            winning.append(tile)
    regular = [winning[:13], [pool.pop(0) for _ in range(13)], [pool.pop(0) for _ in range(13)], [pool.pop(0) for _ in range(13)]]
    players = tuple(
        _updated(
            original, concealed_tiles=sort_playable_tiles(regular[index]),
            drawn_tile=winning[13] if index == 0 else None,
            initial_tile_ids=tuple(tile.tile_id for tile in regular[index]),
        )
        for index, original in enumerate(hand.player_hands)
    )
    prepared = _updated(
        hand, phase=AwaitingDiscardPhase(seat_id=SeatId("seat-0")),
        player_hands=players,
        wall=WallState(live_tiles=tuple(pool), reserve_tiles=hand.wall.reserve_tiles),
    )
    state = _room_with_hand(state, prepared, pending_deadline=None)
    validate_room(state)
    game = next(action for action in engine.legal_actions(state, SeatId("seat-0")) if isinstance(action, DeclareWin))
    completed = engine.transition(state, game).state
    result = completed.match.current_hand.result
    assert result.win_source is WinSource.SELF_DRAW
    assert result.fan == 6 and result.capped_fan == 5
    assert {award.name for award in result.fan_awards} >= {"All Pong", "Full Color"}
    validate_room(completed)
