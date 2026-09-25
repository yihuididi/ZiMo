import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  formatDeadlineCountdown,
  useDeadlineCountdown,
} from "./useDeadlineCountdown";

describe("authoritative discard countdown", () => {
  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it("uses elapsed monotonic time and resolves only at the server deadline", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() =>
      useDeadlineCountdown({
        deadlineMs: 13_000,
        serverTimeMs: 10_000,
        windowId: "window-a",
      }),
    );

    expect(formatDeadlineCountdown(result.current.remainingMs ?? 0)).toBe("3.0s");
    act(() => vi.advanceTimersByTime(2_950));
    expect(formatDeadlineCountdown(result.current.remainingMs ?? 0)).toBe("0.1s");
    expect(result.current.resolving).toBe(false);

    act(() => vi.advanceTimersByTime(50));
    expect(result.current.remainingMs).toBe(0);
    expect(result.current.resolving).toBe(true);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("resets from a newer authoritative window and server clock", () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(
      ({ deadlineMs, serverTimeMs, windowId }) =>
        useDeadlineCountdown({ deadlineMs, serverTimeMs, windowId }),
      {
        initialProps: {
          deadlineMs: 13_000,
          serverTimeMs: 10_000,
          windowId: "window-a" as string | null,
        },
      },
    );
    act(() => vi.advanceTimersByTime(1_000));
    expect(formatDeadlineCountdown(result.current.remainingMs ?? 0)).toBe("2.0s");

    rerender({
      deadlineMs: 24_000,
      serverTimeMs: 20_000,
      windowId: "window-b",
    });
    expect(formatDeadlineCountdown(result.current.remainingMs ?? 0)).toBe("4.0s");
  });
});
