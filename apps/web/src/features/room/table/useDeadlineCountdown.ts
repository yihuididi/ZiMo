import { useEffect, useState } from "react";

interface DeadlineCountdown {
  remainingMs: number | null;
  resolving: boolean;
}

function initialRemaining(deadlineMs: number | null, serverTimeMs: number) {
  return deadlineMs === null ? null : Math.max(0, deadlineMs - serverTimeMs);
}

export function useDeadlineCountdown({
  deadlineMs,
  serverTimeMs,
  windowId,
}: {
  deadlineMs: number | null;
  serverTimeMs: number;
  windowId: string | null;
}): DeadlineCountdown {
  const [remainingMs, setRemainingMs] = useState<number | null>(() =>
    initialRemaining(deadlineMs, serverTimeMs),
  );

  useEffect(() => {
    const initial = initialRemaining(deadlineMs, serverTimeMs);
    setRemainingMs(initial);
    if (initial === null || initial === 0) return;

    const clientBaselineMs = performance.now();
    let timerId: number | undefined;
    const update = () => {
      const estimatedServerTimeMs =
        serverTimeMs + Math.max(0, performance.now() - clientBaselineMs);
      const next = Math.max(0, (deadlineMs ?? serverTimeMs) - estimatedServerTimeMs);
      setRemainingMs(next);
      if (next === 0 && timerId !== undefined) {
        window.clearInterval(timerId);
        timerId = undefined;
      }
    };

    timerId = window.setInterval(update, 50);
    return () => {
      if (timerId !== undefined) window.clearInterval(timerId);
    };
  }, [deadlineMs, serverTimeMs, windowId]);

  return {
    remainingMs,
    resolving: deadlineMs !== null && remainingMs === 0,
  };
}

export function formatDeadlineCountdown(remainingMs: number): string {
  return `${(Math.ceil(remainingMs / 100) / 10).toFixed(1)}s`;
}
