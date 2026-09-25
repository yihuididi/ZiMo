import type {
  BonusNumber,
  TileFace,
  TileRank,
  Wind,
} from "../../../lib/types";

export interface TileAsset {
  src: string;
  label: string;
  source: "mahjong_tiles";
}

const MAHJONG_ROOT = "/mahjong_tiles";

const ranks: readonly TileRank[] = [1, 2, 3, 4, 5, 6, 7, 8, 9];
const bonusNumbers: readonly BonusNumber[] = [1, 2, 3, 4];
const winds: readonly Wind[] = ["EAST", "SOUTH", "WEST", "NORTH"];

const flowerNames: Record<BonusNumber, string> = {
  1: "Plum",
  2: "Orchid",
  3: "Chrysanthemum",
  4: "Bamboo",
};

const seasonNames: Record<BonusNumber, string> = {
  1: "Spring",
  2: "Summer",
  3: "Autumn",
  4: "Winter",
};

const animalNames = {
  CAT: "Cat",
  MOUSE: "Mouse",
  ROOSTER: "Rooster",
  CENTIPEDE: "Centipede",
} as const;

const animalFiles = {
  CAT: "cat.png",
  MOUSE: "mouse.png",
  ROOSTER: "rooster.png",
  CENTIPEDE: "centipede.png",
} as const;

export const ALL_TILE_FACES: readonly TileFace[] = [
  ...ranks.map((value) => ({ family: "CHARACTERS" as const, value })),
  ...ranks.map((value) => ({ family: "DOTS" as const, value })),
  ...ranks.map((value) => ({ family: "BAMBOO" as const, value })),
  ...winds.map((value) => ({ family: "WIND" as const, value })),
  ...(["RED", "GREEN", "WHITE"] as const).map((value) => ({
    family: "DRAGON" as const,
    value,
  })),
  ...bonusNumbers.map((value) => ({ family: "FLOWER" as const, value })),
  ...bonusNumbers.map((value) => ({ family: "SEASON" as const, value })),
  ...(["CAT", "MOUSE", "ROOSTER", "CENTIPEDE"] as const).map((value) => ({
    family: "ANIMAL" as const,
    value,
  })),
];

export const TILE_BACK_ASSET = `${MAHJONG_ROOT}/back.png`;

export function tileFaceKey(face: TileFace): string {
  return `${face.family}:${face.value}`;
}

function suitedLabel(rank: TileRank, singular: string, plural = singular) {
  return `${rank} ${rank === 1 ? singular : plural}`;
}

export function tileLabel(face: TileFace): string {
  switch (face.family) {
    case "CHARACTERS":
      return suitedLabel(face.value, "Character", "Characters");
    case "BAMBOO":
      return suitedLabel(face.value, "Bamboo");
    case "DOTS":
      return suitedLabel(face.value, "Dot", "Dots");
    case "WIND":
      return `${face.value[0]}${face.value.slice(1).toLowerCase()} Wind`;
    case "DRAGON":
      return `${face.value[0]}${face.value.slice(1).toLowerCase()} Dragon`;
    case "FLOWER":
      return `${flowerNames[face.value]} Flower ${face.value}`;
    case "SEASON":
      return `${seasonNames[face.value]} Season ${face.value}`;
    case "ANIMAL":
      return `${animalNames[face.value]} Animal`;
  }
}

export function tileAsset(face: TileFace): TileAsset {
  switch (face.family) {
    case "CHARACTERS":
      return {
        src: `${MAHJONG_ROOT}/character_${face.value}.png`,
        label: tileLabel(face),
        source: "mahjong_tiles",
      };
    case "BAMBOO":
      return {
        src: `${MAHJONG_ROOT}/bamboo_${face.value}.png`,
        label: tileLabel(face),
        source: "mahjong_tiles",
      };
    case "DOTS":
      return {
        src: `${MAHJONG_ROOT}/dot_${face.value}.png`,
        label: tileLabel(face),
        source: "mahjong_tiles",
      };
    case "WIND":
      return {
        src: `${MAHJONG_ROOT}/wind_${face.value.toLowerCase()}.png`,
        label: tileLabel(face),
        source: "mahjong_tiles",
      };
    case "DRAGON":
      return {
        src: `${MAHJONG_ROOT}/dragon_${face.value.toLowerCase()}.png`,
        label: tileLabel(face),
        source: "mahjong_tiles",
      };
    case "FLOWER":
      return {
        src: `${MAHJONG_ROOT}/flower_${flowerNames[face.value].toLowerCase()}.png`,
        label: tileLabel(face),
        source: "mahjong_tiles",
      };
    case "SEASON":
      return {
        src: `${MAHJONG_ROOT}/season_${seasonNames[face.value].toLowerCase()}.png`,
        label: tileLabel(face),
        source: "mahjong_tiles",
      };
    case "ANIMAL":
      return {
        src: `${MAHJONG_ROOT}/${animalFiles[face.value]}`,
        label: tileLabel(face),
        source: "mahjong_tiles",
      };
  }
}
