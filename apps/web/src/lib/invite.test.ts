import { beforeEach, describe, expect, it } from "vitest";

import {
  makeInvitePath,
  parseInviteLink,
  readInviteToken,
  scrubInviteFragment,
} from "./invite";

describe("fragment invitations", () => {
  beforeEach(() => history.replaceState(null, "", "/"));

  it("round trips opaque room and invite values", () => {
    const path = makeInvitePath("room/value", "secret + value");
    expect(path).toBe(
      "/rooms/room%2Fvalue#invite=secret%20%2B%20value",
    );
    expect(
      parseInviteLink(`https://mahjong.example${path}`),
    ).toEqual({ roomId: "room/value", inviteToken: "secret + value" });
  });

  it("captures then scrubs the capability without changing query state", () => {
    history.replaceState(null, "", "/rooms/room-a?debug=1#invite=top-secret");
    expect(readInviteToken(location.hash)).toBe("top-secret");
    scrubInviteFragment();
    expect(location.pathname + location.search + location.hash).toBe(
      "/rooms/room-a?debug=1",
    );
  });

  it("rejects a room ID without an invite capability", () => {
    expect(parseInviteLink("https://mahjong.example/rooms/room-a")).toBeNull();
  });
});
