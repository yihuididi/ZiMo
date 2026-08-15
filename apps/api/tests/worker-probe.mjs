function roomStub(request, env) {
  const roomId = new URL(request.url).searchParams.get("room");
  if (!roomId) {
    return null;
  }
  return env.GAME_ROOM.getByName(roomId);
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
    return new Response("Not Found", { status: 404 });
  },
};
