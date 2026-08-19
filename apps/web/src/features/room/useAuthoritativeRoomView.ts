import { useCallback, useRef, useState } from "react";

import type { PublicRoomView } from "../../lib/types";

export function shouldAcceptRoomView(
  current: PublicRoomView | null,
  incoming: PublicRoomView,
): boolean {
  if (!current) return true;
  if (incoming.revision !== current.revision) {
    return incoming.revision > current.revision;
  }
  if (incoming.presenceVersion !== current.presenceVersion) {
    return incoming.presenceVersion > current.presenceVersion;
  }
  return incoming.serverTimeMs >= current.serverTimeMs;
}

export function useAuthoritativeRoomView(
  initialView: PublicRoomView | null,
  onSessionValidated: () => void,
) {
  const [view, setView] = useState(initialView);
  const latestViewRef = useRef(initialView);
  const onSessionValidatedRef = useRef(onSessionValidated);
  onSessionValidatedRef.current = onSessionValidated;

  const acceptView = useCallback((incoming: PublicRoomView) => {
    onSessionValidatedRef.current();
    if (!shouldAcceptRoomView(latestViewRef.current, incoming)) return false;
    latestViewRef.current = incoming;
    setView(incoming);
    return true;
  }, []);

  const getCurrentView = useCallback(() => latestViewRef.current, []);

  return { view, acceptView, getCurrentView };
}
