import type { OpaqueActionDescriptor } from "../../../lib/types";

export type GameplayPresentationSlot = "concealedTile" | "drawnTile";

export function isGameplayPresentationSlot(
  slot: OpaqueActionDescriptor["presentationSlot"],
): slot is GameplayPresentationSlot {
  return slot === "concealedTile" || slot === "drawnTile";
}

export interface TileActionBindings {
  valid: boolean;
  concealed: ReadonlyMap<number, OpaqueActionDescriptor>;
  drawn: OpaqueActionDescriptor | null;
}

export function bindTileActions(
  actions: readonly OpaqueActionDescriptor[],
  concealedTileCount: number,
  hasDrawnTile: boolean,
): TileActionBindings {
  const concealed = new Map<number, OpaqueActionDescriptor>();
  let drawn: OpaqueActionDescriptor | null = null;
  let valid = true;
  let gameplayActionCount = 0;
  const gameplayActionIds = new Set<string>();

  for (const action of actions) {
    if (action.presentationSlot === "concealedTile") {
      gameplayActionCount += 1;
      if (gameplayActionIds.has(action.actionId)) valid = false;
      gameplayActionIds.add(action.actionId);
      const index = action.presentationIndex;
      if (
        typeof index !== "number" ||
        !Number.isInteger(index) ||
        index < 0 ||
        index >= concealedTileCount ||
        concealed.has(index)
      ) {
        valid = false;
        continue;
      }
      concealed.set(index, action);
      continue;
    }

    if (action.presentationSlot === "drawnTile") {
      gameplayActionCount += 1;
      if (gameplayActionIds.has(action.actionId)) valid = false;
      gameplayActionIds.add(action.actionId);
      if (
        !hasDrawnTile ||
        (action.presentationIndex !== undefined &&
          action.presentationIndex !== null) ||
        drawn !== null
      ) {
        valid = false;
        continue;
      }
      drawn = action;
    }
  }

  if (
    gameplayActionCount > 0 &&
    (concealed.size !== concealedTileCount || (drawn !== null) !== hasDrawnTile)
  ) {
    valid = false;
  }

  if (!valid) {
    return { valid: false, concealed: new Map(), drawn: null };
  }
  return { valid: true, concealed, drawn };
}
