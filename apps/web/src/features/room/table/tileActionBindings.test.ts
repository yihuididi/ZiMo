import { describe, expect, it } from "vitest";

import type { OpaqueActionDescriptor } from "../../../lib/types";
import { discardActions } from "../../../test/fixtures";
import { bindTileActions } from "./tileActionBindings";

function concealed(index: number | null): OpaqueActionDescriptor {
  return {
    actionId: `action-${index}`,
    label: "Discard",
    enabled: true,
    presentationSlot: "concealedTile",
    presentationIndex: index,
  };
}

describe("opaque tile action bindings", () => {
  it("binds complete positional catalogs without exposing a tile identity", () => {
    const result = bindTileActions(discardActions(3), 3, true);

    expect(result.valid).toBe(true);
    expect([...result.concealed.keys()]).toEqual([0, 1, 2]);
    expect(result.drawn?.actionId).toBe("opaque-discard-drawn");
  });

  it("allows an empty catalog for a non-active viewer", () => {
    const result = bindTileActions([], 13, true);
    expect(result.valid).toBe(true);
    expect(result.concealed.size).toBe(0);
    expect(result.drawn).toBeNull();
  });

  it.each([
    ["missing", [concealed(0)], 2, false],
    ["duplicate", [concealed(0), concealed(0)], 1, false],
    [
      "duplicate action ID",
      [concealed(0), { ...concealed(1), actionId: "action-0" }],
      2,
      false,
    ],
    ["out of bounds", [concealed(2)], 2, false],
    ["missing index", [concealed(null)], 1, false],
    [
      "drawn action without a drawn tile",
      [
        {
          ...concealed(0),
          presentationSlot: "drawnTile" as const,
          presentationIndex: null,
        },
      ],
      0,
      false,
    ],
  ])("fails closed for a %s catalog", (_name, actions, count, hasDrawn) => {
    const result = bindTileActions(actions, count, hasDrawn);
    expect(result.valid).toBe(false);
    expect(result.concealed.size).toBe(0);
    expect(result.drawn).toBeNull();
  });
});
