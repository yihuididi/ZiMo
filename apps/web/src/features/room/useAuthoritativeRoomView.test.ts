import { describe, expect, it } from "vitest";

import { roomView } from "../../test/fixtures";
import { shouldAcceptRoomView } from "./useAuthoritativeRoomView";

describe("shouldAcceptRoomView", () => {
  const current = roomView({
    revision: 7,
    presenceVersion: 3,
    serverTimeMs: 1_700_000_000_000,
  });

  it("orders views by revision, presence, then server time", () => {
    expect(shouldAcceptRoomView(current, roomView({ revision: 8 }))).toBe(true);
    expect(
      shouldAcceptRoomView(
        current,
        roomView({
          revision: 7,
          presenceVersion: 4,
          serverTimeMs: current.serverTimeMs - 10_000,
        }),
      ),
    ).toBe(true);
    expect(
      shouldAcceptRoomView(
        current,
        roomView({
          revision: 7,
          presenceVersion: 3,
          serverTimeMs: current.serverTimeMs + 1,
        }),
      ),
    ).toBe(true);
  });

  it("rejects a stale value at any higher-priority ordering field", () => {
    expect(
      shouldAcceptRoomView(
        current,
        roomView({
          revision: 6,
          presenceVersion: 99,
          serverTimeMs: current.serverTimeMs + 99_000,
        }),
      ),
    ).toBe(false);
    expect(
      shouldAcceptRoomView(
        current,
        roomView({
          revision: 7,
          presenceVersion: 2,
          serverTimeMs: current.serverTimeMs + 99_000,
        }),
      ),
    ).toBe(false);
    expect(
      shouldAcceptRoomView(
        current,
        roomView({
          revision: 7,
          presenceVersion: 3,
          serverTimeMs: current.serverTimeMs - 1,
        }),
      ),
    ).toBe(false);
  });

  it("accepts the first and an exactly equal authoritative view", () => {
    expect(shouldAcceptRoomView(null, current)).toBe(true);
    expect(shouldAcceptRoomView(current, current)).toBe(true);
  });
});
