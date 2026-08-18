function roomStub(request, env) {
  const roomId = new URL(request.url).searchParams.get("room");
  if (!roomId) {
    return null;
  }
  return env.GAME_ROOM.getByName(roomId);
}

async function exactJsonBody(request, keys) {
  let value;
  try {
    value = await request.json();
  } catch {
    return null;
  }
  if (
    value === null ||
    Array.isArray(value) ||
    typeof value !== "object" ||
    Object.keys(value).sort().join("\0") !== [...keys].sort().join("\0")
  ) {
    return null;
  }
  return value;
}

function jsonTextResponse(value, status = 200) {
  return new Response(value, {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export default {
  async fetch(request, env) {
    const stub = roomStub(request, env);
    if (stub === null) {
      return new Response("Missing room", { status: 400 });
    }

    const { pathname } = new URL(request.url);
    if (request.method === "POST" && pathname === "/initialize") {
      return new Response(await stub.initialize_room(await request.text()), {
        headers: { "Content-Type": "application/json" },
      });
    }
    if (request.method === "GET" && pathname === "/load") {
      const snapshot = await stub.load_room();
      if (snapshot === null) {
        return new Response(null, { status: 204 });
      }
      return new Response(snapshot, {
        headers: { "Content-Type": "application/json" },
      });
    }
    if (request.method === "GET" && pathname === "/test/tables") {
      return new Response(await stub.test_table_names(), {
        headers: { "Content-Type": "application/json" },
      });
    }
    if (request.method === "GET" && pathname === "/test/counts") {
      return new Response(await stub.test_storage_counts(), {
        headers: { "Content-Type": "application/json" },
      });
    }
    if (request.method === "POST" && pathname === "/test/seed-auxiliary") {
      return new Response(await stub.test_seed_auxiliary_rows(), {
        headers: { "Content-Type": "application/json" },
      });
    }
    if (request.method === "POST" && pathname === "/test/clear-auxiliary") {
      return new Response(await stub.test_clear_auxiliary_rows(), {
        headers: { "Content-Type": "application/json" },
      });
    }
    if (request.method === "POST" && pathname === "/test/room/create") {
      const body = await exactJsonBody(request, ["displayName"]);
      if (body === null || typeof body.displayName !== "string") {
        return jsonTextResponse('{"error":"invalid request"}', 400);
      }
      return jsonTextResponse(
        await stub.create_room(
          new URL(request.url).searchParams.get("room"),
          body.displayName,
        ),
      );
    }
    if (request.method === "POST" && pathname === "/test/room/join") {
      const body = await exactJsonBody(request, ["displayName", "inviteToken"]);
      if (
        body === null ||
        typeof body.displayName !== "string" ||
        typeof body.inviteToken !== "string"
      ) {
        return jsonTextResponse('{"error":"invalid request"}', 400);
      }
      return jsonTextResponse(
        await stub.join_room(body.inviteToken, body.displayName),
      );
    }
    if (request.method === "POST" && pathname === "/test/room/view") {
      const body = await exactJsonBody(request, ["playerToken"]);
      if (body === null || typeof body.playerToken !== "string") {
        return jsonTextResponse('{"error":"invalid request"}', 400);
      }
      return jsonTextResponse(await stub.authenticated_view(body.playerToken));
    }
    if (request.method === "POST" && pathname === "/test/room/events") {
      const body = await exactJsonBody(request, [
        "afterSequence",
        "playerToken",
      ]);
      if (
        body === null ||
        typeof body.playerToken !== "string" ||
        !Number.isSafeInteger(body.afterSequence) ||
        body.afterSequence < 0
      ) {
        return jsonTextResponse('{"error":"invalid request"}', 400);
      }
      return jsonTextResponse(
        await stub.projected_events(body.playerToken, body.afterSequence),
      );
    }
    if (request.method === "POST" && pathname === "/test/room/expire") {
      const body = await exactJsonBody(request, ["playerId"]);
      if (body === null || typeof body.playerId !== "string") {
        return jsonTextResponse('{"error":"invalid request"}', 400);
      }
      return jsonTextResponse(
        await stub.test_expire_disconnected_player(body.playerId),
      );
    }
    if (
      request.method === "POST" &&
      pathname === "/test/room/reconcile-hibernated"
    ) {
      const body = await exactJsonBody(request, ["connectedPlayerIds"]);
      if (
        body === null ||
        !Array.isArray(body.connectedPlayerIds) ||
        body.connectedPlayerIds.some(
          (playerId) => typeof playerId !== "string",
        )
      ) {
        return jsonTextResponse('{"error":"invalid request"}', 400);
      }
      return jsonTextResponse(
        await stub.test_reconcile_hibernated_players(
          JSON.stringify(body.connectedPlayerIds),
        ),
      );
    }
    return new Response("Not Found", { status: 404 });
  },
};
