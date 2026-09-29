"""Default-rule winning patterns and award composition."""

from __future__ import annotations

from app.game import HandId, HandState, PhysicalTile, PlayerHand, SeatId, TileFace, TileFamily, TileId, WallState, Wind, WinSource
from app.game.scoring import evaluate_win


def face(family: TileFamily, value: int | str) -> TileFace:
    return TileFace(family=family, value=value)


def player(values: list[TileFace], bonuses: list[TileFace] | None = None) -> PlayerHand:
    return PlayerHand(
        seat_id=SeatId("seat-0"),
        concealed_tiles=tuple(PhysicalTile(tile_id=TileId(f"tile-{index}"), face=value) for index, value in enumerate(values)),
        bonus_tiles=tuple(PhysicalTile(tile_id=TileId(f"bonus-{index}"), face=value) for index, value in enumerate(bonuses or [])),
    )


def score(
    values: list[TileFace], *, bonuses: list[TileFace] | None = None,
    automatic: str | None = None, last_tile: bool = False,
    replacement: bool = False,
):
    winner = player(values, bonuses)
    winner = winner.model_copy(update={"last_draw_was_replacement": replacement})
    hand = HandState(
        hand_id=HandId("hand-test"), wall=WallState(live_tiles=() if last_tile else (PhysicalTile(tile_id=TileId("wall-1"), face=face(TileFamily.BAMBOO, 9)),)),
        player_hands=(winner, *(PlayerHand(seat_id=SeatId(f"seat-{index}")) for index in range(1, 4))),
    )
    return evaluate_win(
        hand, winner, winning_tile=None, source=WinSource.SELF_DRAW,
        prevailing_wind=Wind.EAST, own_wind=Wind.EAST, automatic=automatic,
    )


def names(result) -> set[str]:
    return {award.name for award in result.awards}


def test_all_pong_and_full_color_stack_but_cap_at_five() -> None:
    values = [face(TileFamily.BAMBOO, value) for value in (1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5)]
    result = score(values)
    assert result is not None
    assert result.fan == 6
    assert {"All Pong", "Full Color"} <= names(result)


def test_ping_wu_replaces_all_chow_and_bonus_removes_ping_wu() -> None:
    values = [face(TileFamily.DOTS, value) for value in (1, 2, 3, 2, 3, 4, 3, 4, 5, 4, 5, 6, 7, 7)]
    plain = score(values)
    with_animal = score(values, bonuses=[face(TileFamily.ANIMAL, "CAT")])
    assert plain is not None and "Ping Wu" in names(plain) and "All Chow" not in names(plain)
    assert with_animal is not None and "All Chow" in names(with_animal) and "Ping Wu" not in names(with_animal)


def test_thirteen_wonders_and_small_winds_suppress_constituents() -> None:
    wonders = [face(family, rank) for family in (TileFamily.BAMBOO, TileFamily.DOTS, TileFamily.CHARACTERS) for rank in (1, 9)]
    wonders += [face(TileFamily.DRAGON, value) for value in ("RED", "GREEN", "WHITE")]
    wonders += [face(TileFamily.WIND, value) for value in ("EAST", "SOUTH", "WEST", "NORTH", "EAST")]
    result = score(wonders)
    assert result is not None and "13 Wonders" in names(result) and result.fan == 8
    small_winds = [face(TileFamily.WIND, value) for value in ("EAST",) * 3 + ("SOUTH",) * 3 + ("WEST",) * 3 + ("NORTH",) * 2]
    small_winds += [face(TileFamily.BAMBOO, 1)] * 3
    result = score(small_winds)
    assert result is not None and "Small Winds" in names(result)
    assert "Prevailing Wind Set" not in names(result)


def test_special_flower_totals_are_not_inflated_by_own_flower_awards() -> None:
    bonuses = [face(family, number) for family in (TileFamily.FLOWER, TileFamily.SEASON) for number in range(1, 5)]
    eight = score([], bonuses=bonuses, automatic="EIGHT_FLOWERS")
    seven = score([], bonuses=bonuses, automatic="SEVEN_FLOWERS")
    assert eight is not None and eight.fan == 12 and names(eight) == {"Eight Flowers"}
    assert seven is not None and seven.fan == 10 and names(seven) == {"Seven Flowers"}


def test_chicken_without_bonus_does_not_meet_minimum_fan() -> None:
    values = [face(TileFamily.BAMBOO, value) for value in (1, 2, 3, 4, 5, 6)]
    values += [face(TileFamily.DOTS, value) for value in (1, 2, 3, 4, 5, 6)]
    values += [face(TileFamily.DRAGON, "RED")] * 2
    assert score(values) is None
    with_animal = score(values, bonuses=[face(TileFamily.ANIMAL, "CAT")])
    assert with_animal is not None and with_animal.fan == 1


def test_automatic_dragon_sets_and_replacement_last_tile_bonuses() -> None:
    dragon_sets = [face(TileFamily.DRAGON, value) for value in ("RED", "GREEN", "WHITE") for _ in range(3)]
    dragon_sets += [face(TileFamily.BAMBOO, value) for value in (1, 2, 3, 4, 5)]
    automatic = score(dragon_sets)
    assert automatic is not None and automatic.pattern == "ALL_DRAGONS"
    assert "All Dragons" in names(automatic)

    standard = [face(TileFamily.BAMBOO, value) for value in (1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5)]
    result = score(standard, replacement=True, last_tile=True)
    assert result is not None
    assert {"Replacement Tile", "Last Valid Tile"} <= names(result)
