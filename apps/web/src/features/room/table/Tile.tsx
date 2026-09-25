import { useId } from "react";

import type {
  OpaqueActionDescriptor,
  PublicTileView,
} from "../../../lib/types";
import { TILE_BACK_ASSET, tileAsset } from "./tileCatalog";

interface TileFaceProps {
  tile: PublicTileView;
  size?: "mini" | "regular";
  className?: string;
}

export function TileFace({
  tile,
  size = "regular",
  className = "",
}: TileFaceProps) {
  const asset = tileAsset(tile.face);
  return (
    <span
      className={`mahjong-tile tile-${size} ${className}`.trim()}
      role="img"
      aria-label={asset.label}
    >
      <img src={asset.src} alt="" aria-hidden="true" draggable={false} />
    </span>
  );
}

export function TileBack({
  separated = false,
}: {
  separated?: boolean;
}) {
  return (
    <span
      className={`mahjong-tile tile-back${separated ? " tile-separated" : ""}`}
      aria-hidden="true"
    >
      <img src={TILE_BACK_ASSET} alt="" draggable={false} />
    </span>
  );
}

interface DiscardTileProps {
  tile: PublicTileView;
  action: OpaqueActionDescriptor | undefined;
  groupLocked: boolean;
  actionsValid: boolean;
  onRunAction: (action: OpaqueActionDescriptor) => void;
  separated?: boolean;
}

export function DiscardTile({
  tile,
  action,
  groupLocked,
  actionsValid,
  onRunAction,
  separated = false,
}: DiscardTileProps) {
  const disabledReasonId = useId();
  const asset = tileAsset(tile.face);
  const disabled =
    !actionsValid || !action || !action.enabled || groupLocked;
  const disabledReason = action?.disabledReason;

  if (!action) {
    return (
      <TileFace
        tile={tile}
        className={separated ? "tile-separated" : undefined}
      />
    );
  }

  return (
    <span className="discard-tile-entry">
      <button
        type="button"
        className={`tile-button${separated ? " tile-separated" : ""}`}
        aria-label={`Discard ${asset.label}`}
        aria-describedby={disabledReason ? disabledReasonId : undefined}
        disabled={disabled}
        onClick={() => onRunAction(action)}
      >
        <img src={asset.src} alt="" aria-hidden="true" draggable={false} />
      </button>
      {disabledReason && (
        <span className="sr-only" id={disabledReasonId}>
          {disabledReason}
        </span>
      )}
    </span>
  );
}
