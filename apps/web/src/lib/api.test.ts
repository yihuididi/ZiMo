import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  createRoom,
  createSocketTicket,
  getEvents,
  getRoom,
  joinRoom,
  submitCommand,
  updateConfig,
} from "./api";
import { roomView } from "../test/fixtures";

const jsonResponse = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });

describe("room API client", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  it("creates and joins rooms without putting capabilities in URLs", async () => {
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({
          roomId: "room/a",
          playerId: "host",
          playerToken: "host-secret",
          inviteToken: "invite-secret",
          view: roomView(),
        }, 201),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          roomId: "room/a",
          playerId: "member",
          playerToken: "member-secret",
          view: roomView(),
        }, 201),
      );

    await createRoom("Mei");
    await joinRoom("room/a", "invite-secret", "Wei");

    expect(new URL(String(fetchMock.mock.calls[0][0]), location.origin).pathname).toBe(
      "/rooms",
    );
    expect(fetchMock.mock.calls[0][1]?.body).toBe(
      JSON.stringify({ displayName: "Mei" }),
    );
    expect(
      new Headers(fetchMock.mock.calls[0][1]?.headers).has("Authorization"),
    ).toBe(false);
    expect(new URL(String(fetchMock.mock.calls[1][0]), location.origin).pathname).toBe(
      "/rooms/room%2Fa/join",
    );
    expect(fetchMock.mock.calls[1][1]?.body).toBe(
      JSON.stringify({ inviteToken: "invite-secret", displayName: "Wei" }),
    );
    expect(
      new Headers(fetchMock.mock.calls[1][1]?.headers).has("Authorization"),
    ).toBe(false);
    expect(String(fetchMock.mock.calls[1][0])).not.toContain("invite-secret");
  });

  it("uses bearer auth and the exact idempotent command body", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(roomView()))
      .mockResolvedValueOnce(
        jsonResponse({ type: "view", view: roomView({ revision: 8 }) }),
      );

    await getRoom("room-a", "player-secret");
    await submitCommand("room-a", "player-secret", {
      commandId: "command-uuid",
      expectedRevision: 7,
      actionId: "opaque-action",
    });

    for (const [, init] of fetchMock.mock.calls) {
      expect(new Headers(init?.headers).get("Authorization")).toBe(
        "Bearer player-secret",
      );
      expect(init?.cache).toBe("no-store");
      expect(init?.credentials).toBe("omit");
    }
    expect(fetchMock.mock.calls[1][1]?.body).toBe(
      JSON.stringify({
        commandId: "command-uuid",
        expectedRevision: 7,
        actionId: "opaque-action",
      }),
    );
  });

  it("requests bodyless socket tickets and supports event cursors", async () => {
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({ ticket: "one-shot", expiresAtMs: Date.now() + 30_000 }),
      )
      .mockResolvedValueOnce(jsonResponse({ events: [], nextSequence: 42 }));

    await createSocketTicket("room-a", "player-secret");
    await getEvents("room-a", "player-secret", 41);

    const ticketInit = fetchMock.mock.calls[0][1];
    expect(ticketInit?.body).toBeUndefined();
    expect(new Headers(ticketInit?.headers).has("Content-Type")).toBe(false);
    const eventsUrl = new URL(String(fetchMock.mock.calls[1][0]), location.origin);
    expect(eventsUrl.pathname + eventsUrl.search).toBe(
      "/rooms/room-a/events?afterSequence=41",
    );
  });

  it("sends the complete config with bearer auth and retains the view discriminator", async () => {
    const current = roomView();
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ type: "view", view: current }),
    );

    const response = await updateConfig(
      "room-a",
      "host-secret",
      current.revision,
      current.config,
    );

    expect(response.type).toBe("view");
    const [, init] = fetchMock.mock.calls[0];
    expect(init?.method).toBe("PATCH");
    expect(new Headers(init?.headers).get("Authorization")).toBe(
      "Bearer host-secret",
    );
    expect(init?.body).toBe(
      JSON.stringify({
        expectedRevision: current.revision,
        config: current.config,
      }),
    );
  });

  it("maps the structured conflict envelope without leaking auth", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          error: {
            code: "REVISION_CONFLICT",
            message: "Room changed",
            currentRevision: 12,
          },
        },
        409,
      ),
    );

    const error = await getRoom("room-a", "never-in-error").catch(
      (reason: unknown) => reason,
    );
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 409,
      code: "REVISION_CONFLICT",
      currentRevision: 12,
      message: "Room changed",
    });
    expect(String(error)).not.toContain("never-in-error");
  });
});
