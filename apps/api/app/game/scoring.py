"""Pure default Singapore hand legality and fan evaluation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from .config import GameConfig
from .model import FanAward, HandState, MeldKind, PlayerHand, TileFace, TileFamily, Wind, WinSource
from .tiles import ANIMAL_VALUES, DRAGON_VALUES, WIND_VALUES

Face = tuple[TileFamily, int | str]
SUITS = {TileFamily.BAMBOO, TileFamily.DOTS, TileFamily.CHARACTERS}
HONORS = {TileFamily.DRAGON, TileFamily.WIND}
WONDERS = frozenset(
    [(family, rank) for family in SUITS for rank in (1, 9)]
    + [(TileFamily.DRAGON, value) for value in DRAGON_VALUES]
    + [(TileFamily.WIND, value) for value in WIND_VALUES]
)


def _face(tile: TileFace) -> Face:
    return (tile.family, tile.value)


def _key(face: Face) -> tuple[str, str]:
    return face[0].value, str(face[1]).zfill(2)


@dataclass(frozen=True)
class WinEvaluation:
    fan: int
    awards: tuple[FanAward, ...]
    pattern: str


def _decompositions(faces: tuple[Face, ...], set_count: int) -> tuple[tuple[Face, tuple[tuple[str, tuple[Face, ...]], ...]], ...]:
    counts = Counter(faces)
    if sum(counts.values()) != 3 * set_count + 2:
        return ()

    @lru_cache(None)
    def sets(remaining: tuple[tuple[Face, int], ...]) -> tuple[tuple[tuple[str, tuple[Face, ...]], ...], ...]:
        current = Counter(dict(remaining))
        if not current:
            return ((),)
        first = min(current, key=_key)
        choices: list[tuple[tuple[str, tuple[Face, ...]], ...]] = []
        if current[first] >= 3:
            reduced = current.copy()
            reduced[first] -= 3
            reduced += Counter()
            for tail in sets(tuple(sorted(reduced.items(), key=lambda item: _key(item[0])))):
                choices.append((("PONG", (first,) * 3), *tail))
        if first[0] in SUITS and isinstance(first[1], int) and first[1] <= 7:
            run = tuple((first[0], first[1] + offset) for offset in range(3))
            if all(current[value] for value in run):
                reduced = current.copy()
                for value in run:
                    reduced[value] -= 1
                reduced += Counter()
                for tail in sets(tuple(sorted(reduced.items(), key=lambda item: _key(item[0])))):
                    choices.append((("CHOW", run), *tail))
        return tuple(choices)

    result = []
    for eye in sorted((face for face, count in counts.items() if count >= 2), key=_key):
        reduced = counts.copy()
        reduced[eye] -= 2
        reduced += Counter()
        for value in sets(tuple(sorted(reduced.items(), key=lambda item: _key(item[0])))):
            if len(value) == set_count:
                result.append((eye, value))
    return tuple(result)


def _bonus_awards(player: PlayerHand, own_wind: Wind) -> list[FanAward]:
    bonuses = {_face(tile.face) for tile in player.bonus_tiles}
    awards = [FanAward(name=f"Animal {value.title()}", fan=1) for value in ANIMAL_VALUES if (TileFamily.ANIMAL, value) in bonuses]
    if all((TileFamily.ANIMAL, value) in bonuses for value in ANIMAL_VALUES):
        awards.append(FanAward(name="Complete Animal Set", fan=1))
    wind_number = WIND_VALUES.index(own_wind.value) + 1
    for family in (TileFamily.FLOWER, TileFamily.SEASON):
        if (family, wind_number) in bonuses:
            awards.append(FanAward(name=f"Own {family.value.title()}", fan=1))
        if all((family, number) in bonuses for number in range(1, 5)):
            awards.append(FanAward(name=f"Complete {family.value.title()} Set", fan=1))
    return awards


def _event_awards(source: WinSource, *, replacement: bool, last_tile: bool) -> list[FanAward]:
    awards = []
    if source is WinSource.ROBBED_KONG:
        awards.append(FanAward(name="Robbing the Kong", fan=1))
    if replacement and source is WinSource.SELF_DRAW:
        awards.append(FanAward(name="Replacement Tile", fan=1))
    if last_tile:
        awards.append(FanAward(name="Last Valid Tile", fan=1))
    return awards


def _all_chow_wait_is_open(
    faces: tuple[Face, ...], winning: Face, prevailing: Wind, own: Wind,
    set_count: int, exposed: tuple[Face, ...],
) -> bool:
    before = list(faces)
    before.remove(winning)
    occupied = Counter((*before, *exposed))
    waits = 0
    for candidate in sorted(WONDERS | frozenset((family, rank) for family in SUITS for rank in range(1, 10)), key=_key):
        if occupied[candidate] >= 4:
            continue
        for eye, sets in _decompositions(tuple((*before, candidate)), set_count):
            if all(kind == "CHOW" for kind, _ in sets) and eye not in {
                (TileFamily.DRAGON, value) for value in DRAGON_VALUES
            } | {(TileFamily.WIND, prevailing.value), (TileFamily.WIND, own.value)}:
                waits += 1
                break
        if waits > 1:
            return True
    return False


def _standard_awards(
    player: PlayerHand, faces: tuple[Face, ...], eye: Face,
    concealed_sets: tuple[tuple[str, tuple[Face, ...]], ...],
    source: WinSource, winning: Face | None, prevailing: Wind, own: Wind,
) -> list[FanAward]:
    sets = [*concealed_sets, *[(meld.kind.value, tuple(_face(tile.face) for tile in meld.tiles)) for meld in player.melds]]
    all_faces = [*faces, *[face for _, values in sets[len(concealed_sets):] for face in values]]
    awards: list[FanAward] = []
    if len(sets) != 4:
        return awards
    dragon_sets = {values[0][1] for kind, values in sets if kind in {"PONG", "KONG"} and values[0][0] is TileFamily.DRAGON}
    wind_sets = {values[0][1] for kind, values in sets if kind in {"PONG", "KONG"} and values[0][0] is TileFamily.WIND}
    if len(dragon_sets) == 3:
        awards.append(FanAward(name="Big Dragons", fan=7))
    else:
        for value in DRAGON_VALUES:
            if value in dragon_sets:
                awards.append(FanAward(name=f"{value.title()} Dragon Set", fan=1))
        if len(dragon_sets) == 2 and eye[0] is TileFamily.DRAGON and eye[1] not in dragon_sets:
            awards.append(FanAward(name="Small Dragons", fan=1))
    if len(wind_sets) == 4:
        awards.append(FanAward(name="Big Winds", fan=12))
    elif len(wind_sets) == 3 and eye[0] is TileFamily.WIND and eye[1] not in wind_sets:
        awards.append(FanAward(name="Small Winds", fan=4))
    else:
        if prevailing.value in wind_sets:
            awards.append(FanAward(name="Prevailing Wind Set", fan=1))
        if own.value in wind_sets:
            awards.append(FanAward(name="Own Wind Set", fan=1))
    if all(kind == "CHOW" for kind, _ in sets) and eye[0] is not TileFamily.DRAGON and eye not in {(TileFamily.WIND, prevailing.value), (TileFamily.WIND, own.value)}:
        if source is WinSource.SELF_DRAW or (winning is not None and _all_chow_wait_is_open(
            faces, winning, prevailing, own, 4 - len(player.melds),
            tuple(_face(tile.face) for meld in player.melds for tile in meld.tiles),
        )):
            if not player.bonus_tiles:
                awards.append(FanAward(name="Ping Wu", fan=4))
            else:
                awards.append(FanAward(name="All Chow", fan=1))
    if all(kind in {"PONG", "KONG"} for kind, _ in sets):
        awards.append(FanAward(name="All Pong", fan=2))
    awards.extend(_color_terminal_awards(all_faces))
    if not awards:
        awards.append(FanAward(name="Chicken", fan=0))
    return awards


def _color_terminal_awards(all_faces: list[Face]) -> list[FanAward]:
    awards: list[FanAward] = []
    families = {face[0] for face in all_faces}
    suit_families = families & SUITS
    if len(suit_families) == 1 and not families & HONORS:
        awards.append(FanAward(name="Full Color", fan=4))
    elif not suit_families and families <= HONORS:
        awards.append(FanAward(name="Full Color", fan=4))
    elif len(suit_families) == 1 and families & HONORS:
        awards.append(FanAward(name="Half Color", fan=2))
    terminals = all(face[0] in SUITS and face[1] in {1, 9} for face in all_faces)
    half_terminals = (
        any(face[0] in SUITS for face in all_faces)
        and any(face[0] in HONORS for face in all_faces)
        and all((face[0] in SUITS and face[1] in {1, 9}) or face[0] in HONORS for face in all_faces)
    )
    if terminals:
        awards.append(FanAward(name="All Terminal", fan=9))
    elif half_terminals:
        awards.append(FanAward(name="Half Terminal", fan=2))
    return awards


def evaluate_win(
    hand: HandState, player: PlayerHand, *, winning_tile: TileFace | None,
    source: WinSource, prevailing_wind: Wind, own_wind: Wind,
    automatic: str | None = None, minimum_fan: int = 1,
    config: GameConfig | None = None,
) -> WinEvaluation | None:
    """Return the best legal default-rule result, or None below minimum fan."""
    config = config or GameConfig(minimum_fan=minimum_fan)
    minimum_fan = config.minimum_fan
    concealed = tuple(_face(tile.face) for tile in (*player.concealed_tiles, *((player.drawn_tile,) if player.drawn_tile else ())))
    winning = _face(winning_tile) if winning_tile is not None else None
    if source is not WinSource.SELF_DRAW and winning is not None:
        concealed = (*concealed, winning)
    bonus = _bonus_awards(player, own_wind)
    events = _event_awards(source, replacement=player.last_draw_was_replacement, last_tile=not hand.wall.live_tiles)
    if config.concealed_self_draw_bonus_enabled and source is WinSource.SELF_DRAW and not player.melds:
        events.append(FanAward(name="Concealed Self-draw", fan=1))
    honor_sets = {
        (meld.tiles[0].face.family, meld.tiles[0].face.value)
        for meld in player.melds if meld.kind in {MeldKind.PONG, MeldKind.KONG}
    }
    counts = Counter(concealed)
    honor_sets.update(face for face, count in counts.items() if face[0] in HONORS and count >= 3)
    if ((automatic == "ALL_DRAGONS" and not config.automatic_dragon_wins_enabled)
            or (automatic == "ALL_WINDS" and not config.automatic_wind_wins_enabled)):
        automatic = None
    if automatic is None:
        if config.automatic_wind_wins_enabled and all((TileFamily.WIND, value) in honor_sets for value in WIND_VALUES):
            automatic = "ALL_WINDS"
        elif config.automatic_dragon_wins_enabled and all((TileFamily.DRAGON, value) in honor_sets for value in DRAGON_VALUES):
            automatic = "ALL_DRAGONS"
    candidates: list[tuple[str, list[FanAward]]] = []
    if automatic == "EIGHT_FLOWERS":
        awards = (FanAward(name="Eight Flowers", fan=12),)
        return WinEvaluation(fan=12, awards=awards, pattern=automatic) if 12 >= minimum_fan else None
    elif automatic == "SEVEN_FLOWERS":
        awards = (FanAward(name="Seven Flowers", fan=10),)
        return WinEvaluation(fan=10, awards=awards, pattern=automatic) if 10 >= minimum_fan else None
    elif automatic == "ALL_DRAGONS":
        awards = (FanAward(name="All Dragons", fan=7), *bonus, *events)
        total = sum(award.fan for award in awards)
        return WinEvaluation(fan=total, awards=awards, pattern=automatic) if total >= minimum_fan else None
    elif automatic == "ALL_WINDS":
        awards = (FanAward(name="All Winds", fan=12), *bonus, *events)
        total = sum(award.fan for award in awards)
        return WinEvaluation(fan=total, awards=awards, pattern=automatic) if total >= minimum_fan else None
    if config.seven_pairs_enabled and not player.melds and len(concealed) == 14 and all(count % 2 == 0 for count in counts.values()):
        candidates.append(("SEVEN_PAIRS", [FanAward(name="Seven Pairs", fan=3), *_color_terminal_awards(list(concealed))]))
    if len(player.melds) == 0 and len(concealed) == 14 and set(concealed) == WONDERS and max(Counter(concealed).values()) == 2:
        candidates.append(("THIRTEEN_WONDERS", [FanAward(name="13 Wonders", fan=8)]))
    for eye, sets in _decompositions(concealed, 4 - len(player.melds)):
        candidates.append(("STANDARD", _standard_awards(player, concealed, eye, sets, source, winning, prevailing_wind, own_wind)))
    if not candidates:
        return None
    evaluated = []
    for pattern, awards in candidates:
        combined = tuple((*awards, *bonus, *events))
        total = sum(award.fan for award in combined)
        if total >= minimum_fan:
            evaluated.append(WinEvaluation(fan=total, awards=combined, pattern=pattern))
    if not evaluated:
        return None
    return max(evaluated, key=lambda result: (result.fan, result.pattern, tuple(award.name for award in result.awards)))
