"""Canonical Singapore tile manifest, physical deck, and server sort order."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from .model import HandId, PhysicalTile, TileFace, TileFamily, TileId


DRAGON_VALUES = ("RED", "GREEN", "WHITE")
WIND_VALUES = ("EAST", "SOUTH", "WEST", "NORTH")
ANIMAL_VALUES = ("CAT", "MOUSE", "ROOSTER", "CENTIPEDE")

_FAMILY_SORT_ORDER = {
    TileFamily.CHARACTERS: 0,
    TileFamily.DOTS: 1,
    TileFamily.BAMBOO: 2,
    TileFamily.WIND: 3,
    TileFamily.DRAGON: 4,
    TileFamily.FLOWER: 5,
    TileFamily.SEASON: 6,
    TileFamily.ANIMAL: 7,
}
_STRING_VALUE_SORT_ORDER = {
    **{value: index for index, value in enumerate(WIND_VALUES)},
    **{value: index for index, value in enumerate(DRAGON_VALUES)},
    **{value: index for index, value in enumerate(ANIMAL_VALUES)},
}


def canonical_tile_faces() -> tuple[TileFace, ...]:
    """Return the exact 46 logical faces in stable server order."""

    faces: list[TileFace] = []
    for family in (
        TileFamily.CHARACTERS,
        TileFamily.DOTS,
        TileFamily.BAMBOO,
    ):
        faces.extend(TileFace(family=family, value=rank) for rank in range(1, 10))
    faces.extend(TileFace(family=TileFamily.WIND, value=value) for value in WIND_VALUES)
    faces.extend(
        TileFace(family=TileFamily.DRAGON, value=value) for value in DRAGON_VALUES
    )
    faces.extend(TileFace(family=TileFamily.FLOWER, value=value) for value in range(1, 5))
    faces.extend(TileFace(family=TileFamily.SEASON, value=value) for value in range(1, 5))
    faces.extend(
        TileFace(family=TileFamily.ANIMAL, value=value) for value in ANIMAL_VALUES
    )
    return tuple(faces)


def canonical_physical_deck(hand_id: HandId) -> tuple[PhysicalTile, ...]:
    """Build the 148 pre-shuffle templates later relabeled by the engine."""

    tiles: list[PhysicalTile] = []
    for face in canonical_tile_faces():
        copies = 1 if is_bonus_face(face) else 4
        value = str(face.value).lower()
        family = face.family.value.lower()
        for copy_index in range(1, copies + 1):
            tiles.append(
                PhysicalTile(
                    tile_id=TileId(
                        f"{hand_id}:{family}:{value}:{copy_index}"
                    ),
                    face=face,
                )
            )
    return tuple(tiles)


def is_bonus_face(face: TileFace) -> bool:
    return face.family in {
        TileFamily.FLOWER,
        TileFamily.SEASON,
        TileFamily.ANIMAL,
    }


def is_bonus_tile(tile: PhysicalTile) -> bool:
    return is_bonus_face(tile.face)


def tile_sort_key(tile: PhysicalTile) -> tuple[int, int, str]:
    value = tile.face.value
    value_order = (
        value
        if isinstance(value, int) and not isinstance(value, bool)
        else _STRING_VALUE_SORT_ORDER[str(value)]
    )
    return (_FAMILY_SORT_ORDER[tile.face.family], value_order, str(tile.tile_id))


def sort_playable_tiles(
    tiles: Iterable[PhysicalTile],
) -> tuple[PhysicalTile, ...]:
    values = tuple(tiles)
    if any(is_bonus_tile(tile) for tile in values):
        raise ValueError("playable concealed tiles cannot contain bonus tiles")
    return tuple(sorted(values, key=tile_sort_key))


def canonical_face_counts() -> Counter[tuple[TileFamily, int | str]]:
    return Counter(
        {
            (face.family, face.value): 1 if is_bonus_face(face) else 4
            for face in canonical_tile_faces()
        }
    )


__all__ = [
    "ANIMAL_VALUES",
    "DRAGON_VALUES",
    "WIND_VALUES",
    "canonical_face_counts",
    "canonical_physical_deck",
    "canonical_tile_faces",
    "is_bonus_face",
    "is_bonus_tile",
    "sort_playable_tiles",
    "tile_sort_key",
]
