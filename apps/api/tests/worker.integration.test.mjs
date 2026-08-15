import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createTestHarness } from "wrangler";

const ROOM_NAME = "milestone-1-reconstruction";
const SNAPSHOT_JSON = JSON.stringify({
  roomId: ROOM_NAME,
  seats: [0, 1, 2, 3].map((slot) => ({
    seatId: `seat-${slot}`,
    slot,
  })),
  createdAtMs: 1_700_000_000_000,
  updatedAtMs: 1_700_000_000_000,
});

const harness = createTestHarness({
  workers: [
    {
      configPath: new URL("../wrangler.jsonc", import.meta.url),
      secrets: {
        SUPABASE_URL: "https://example.invalid",
        SUPABASE_PUBLISHABLE_KEY: "test-publishable-key",
        FRONTEND_ORIGIN: "http://localhost:5173",
      },
    },
    {
      configPath: new URL("../worker-runtime.wrangler.jsonc", import.meta.url),
      secrets: {
        SUPABASE_URL: "https://example.invalid",
        SUPABASE_PUBLISHABLE_KEY: "test-publishable-key",
        FRONTEND_ORIGIN: "http://localhost:5173",
      },
    },
    {
      configPath: new URL("./worker-probe.wrangler.jsonc", import.meta.url),
    },
  ],
});

let worker;
let probe;

beforeAll(async () => {
  await harness.listen();
  worker = harness.getWorker("mahjong-api-runtime-test");
  probe = harness.getWorker("mahjong-api-probe");
});

afterAll(async () => {
  await harness.close();
});

async function initializeRoom(snapshotJson) {
  const response = await probe.fetch(
    `http://probe.invalid/initialize?room=${encodeURIComponent(ROOM_NAME)}`,
    { method: "POST", body: snapshotJson },
  );
  if (!response.ok) {
    throw new Error(`Room initialization failed: ${await response.text()}`);
  }
  return response.text();
}

async function loadRoom() {
  const response = await probe.fetch(
    `http://probe.invalid/load?room=${encodeURIComponent(ROOM_NAME)}`,
  );
  if (response.status === 204) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Room load failed: ${await response.text()}`);
  }
  return response.text();
}

async function testRpc(pathname, method = "GET") {
  const response = await probe.fetch(
    `http://probe.invalid${pathname}?room=${encodeURIComponent(ROOM_NAME)}`,
    { method },
  );
  if (!response.ok) {
    throw new Error(`Test RPC ${pathname} failed: ${await response.text()}`);
  }
  return response.json();
}

describe("Milestone 1 Python Worker", () => {
  it("keeps only the existing public health surface", async () => {
    const response = await harness.fetch("/health");

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      ok: true,
      service: "mahjong-api",
    });

    const roomResponse = await harness.fetch(`/rooms/${ROOM_NAME}`);
    expect(roomResponse.status).toBe(404);
  });

  it("reconstructs the canonical room after Durable Object eviction", async () => {
    await expect(loadRoom()).resolves.toBeNull();

    const canonicalSnapshot = await initializeRoom(SNAPSHOT_JSON);
    expect(JSON.parse(canonicalSnapshot)).toMatchObject({
      roomId: ROOM_NAME,
      revision: 0,
      rulesetId: "singapore",
      rulesetVersion: "0.1.0",
      stateSchemaVersion: 1,
    });
    await expect(loadRoom()).resolves.toBe(canonicalSnapshot);

    await expect(testRpc("/test/tables")).resolves.toEqual([
      "_sql_schema_migrations",
      "events",
      "players",
      "processed_commands",
      "room_state",
      "socket_tickets",
    ]);
    await expect(testRpc("/test/counts")).resolves.toEqual({
      _sql_schema_migrations: 1,
      events: 0,
      players: 0,
      processed_commands: 0,
      room_state: 1,
      socket_tickets: 0,
    });

    await expect(
      testRpc("/test/seed-auxiliary", "POST"),
    ).resolves.toEqual({
      _sql_schema_migrations: 1,
      events: 1,
      players: 1,
      processed_commands: 1,
      room_state: 1,
      socket_tickets: 1,
    });
    await expect(
      testRpc("/test/clear-auxiliary", "POST"),
    ).resolves.toEqual({
      _sql_schema_migrations: 1,
      events: 0,
      players: 0,
      processed_commands: 0,
      room_state: 1,
      socket_tickets: 0,
    });

    await expect(worker.listDurableObjectIds("GAME_ROOM")).resolves.toHaveLength(
      1,
    );

    await worker.evictDurableObject("GAME_ROOM", { name: ROOM_NAME });
    await expect(loadRoom()).resolves.toBe(canonicalSnapshot);
  });
});
