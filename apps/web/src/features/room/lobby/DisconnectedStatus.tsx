import { useEffect, useState } from "react";

function remainingDisconnectSeconds(
  disconnectExpiresAtMs: number,
  estimatedServerTimeMs: number,
) {
  return Math.max(
    0,
    Math.ceil((disconnectExpiresAtMs - estimatedServerTimeMs) / 1_000),
  );
}

function formatCountdown(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

interface DisconnectedStatusProps {
  disconnectExpiresAtMs: number | null;
  serverTimeMs: number;
}

export function DisconnectedStatus({
  disconnectExpiresAtMs,
  serverTimeMs,
}: DisconnectedStatusProps) {
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(() =>
    disconnectExpiresAtMs === null
      ? null
      : remainingDisconnectSeconds(disconnectExpiresAtMs, serverTimeMs),
  );

  useEffect(() => {
    if (disconnectExpiresAtMs === null) {
      setRemainingSeconds(null);
      return;
    }

    const clientBaselineMs = performance.now();
    let timerId: number | undefined;
    const stopTimer = () => {
      if (timerId === undefined) return;
      window.clearInterval(timerId);
      timerId = undefined;
    };
    const update = () => {
      // The server clock is authoritative. The browser contributes only the
      // monotonic time elapsed since this view was received.
      const estimatedServerTimeMs =
        serverTimeMs + Math.max(0, performance.now() - clientBaselineMs);
      const next = remainingDisconnectSeconds(
        disconnectExpiresAtMs,
        estimatedServerTimeMs,
      );
      setRemainingSeconds(next);
      if (next === 0) stopTimer();
    };

    const initial = remainingDisconnectSeconds(
      disconnectExpiresAtMs,
      serverTimeMs,
    );
    setRemainingSeconds(initial);
    if (initial > 0) timerId = window.setInterval(update, 1_000);
    return stopTimer;
  }, [disconnectExpiresAtMs, serverTimeMs]);

  return (
    <div className="disconnected-status">
      <span className="disconnected-chip" role="status">
        Disconnected
      </span>
      {remainingSeconds !== null && (
        <span className="disconnect-countdown">
          {remainingSeconds === 0
            ? "Removing…"
            : `Removing in ${formatCountdown(remainingSeconds)}`}
        </span>
      )}
    </div>
  );
}
