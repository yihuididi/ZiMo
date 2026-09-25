import { describe, expect, it } from "vitest";

import {
  ALL_TILE_FACES,
  TILE_BACK_ASSET,
  tileAsset,
  tileFaceKey,
  tileLabel,
} from "./tileCatalog";

describe("tile asset catalog", () => {
  it("covers the canonical 46 logical faces exactly once in server order", () => {
    expect(ALL_TILE_FACES).toHaveLength(46);
    expect(new Set(ALL_TILE_FACES.map(tileFaceKey))).toHaveProperty("size", 46);
    expect(ALL_TILE_FACES.slice(0, 3)).toEqual([
      { family: "CHARACTERS", value: 1 },
      { family: "CHARACTERS", value: 2 },
      { family: "CHARACTERS", value: 3 },
    ]);
    expect(ALL_TILE_FACES[9]).toEqual({ family: "DOTS", value: 1 });
    expect(ALL_TILE_FACES[18]).toEqual({ family: "BAMBOO", value: 1 });
    expect(ALL_TILE_FACES.map(tileAsset).filter((asset) => asset.source === "mahjong_tiles"))
      .toHaveLength(46);
  });

  it("maps regular, bonus, and back artwork to pinned local asset paths", () => {
    expect(tileAsset({ family: "CHARACTERS", value: 1 }).src).toBe(
      "/mahjong_tiles/character_1.png",
    );
    expect(tileAsset({ family: "WIND", value: "WEST" }).src).toBe(
      "/mahjong_tiles/wind_west.png",
    );
    expect(tileAsset({ family: "DRAGON", value: "WHITE" }).src).toBe(
      "/mahjong_tiles/dragon_white.png",
    );
    expect(tileAsset({ family: "FLOWER", value: 3 }).src).toBe(
      "/mahjong_tiles/flower_chrysanthemum.png",
    );
    expect(tileAsset({ family: "ANIMAL", value: "CENTIPEDE" }).src).toBe(
      "/mahjong_tiles/centipede.png",
    );
    expect(tileAsset({ family: "ANIMAL", value: "CAT" }).src).toBe(
      "/mahjong_tiles/cat.png",
    );
    expect(tileAsset({ family: "ANIMAL", value: "MOUSE" }).src).toBe(
      "/mahjong_tiles/mouse.png",
    );
    expect(tileAsset({ family: "ANIMAL", value: "ROOSTER" }).src).toBe(
      "/mahjong_tiles/rooster.png",
    );
    expect(TILE_BACK_ASSET).toBe("/mahjong_tiles/back.png");
  });

  it("provides semantic labels for every family", () => {
    expect(tileLabel({ family: "CHARACTERS", value: 9 })).toBe("9 Characters");
    expect(tileLabel({ family: "DOTS", value: 1 })).toBe("1 Dot");
    expect(tileLabel({ family: "BAMBOO", value: 4 })).toBe("4 Bamboo");
    expect(tileLabel({ family: "WIND", value: "EAST" })).toBe("East Wind");
    expect(tileLabel({ family: "DRAGON", value: "RED" })).toBe("Red Dragon");
    expect(tileLabel({ family: "FLOWER", value: 1 })).toBe("Plum Flower 1");
    expect(tileLabel({ family: "SEASON", value: 4 })).toBe("Winter Season 4");
    expect(tileLabel({ family: "ANIMAL", value: "MOUSE" })).toBe("Mouse Animal");
  });
});
