# ZiMo Mahjong

Milestone 4 of a server-authoritative, real-time multiplayer Mahjong application.
It provides private four-seat rooms, bearer-authenticated sessions, mixed human
and bot tables, revisioned opaque commands, durable three-second discard windows,
and hibernating WebSocket updates. New rooms play a one-hand claims/melds preview
with Chow, Pong, Kong-3, Kong-4, and Pass. Game, Kong-1, scoring, payments,
settings, and additional hands remain explicitly unavailable.

## Architecture

```text
React frontend (Cloudflare Pages)
       │
       ▼
FastAPI backend (Cloudflare Python Worker)
       │
       ├────► Supabase client (retained, non-authoritative)
       │
       └────► GAME_ROOM Durable Object ◄──── hibernating WebSockets
                    │
                    ├──► pure lobby/game transitions and room orchestrator
                    ├──► SQLite snapshot repository
                    └──► pure CPython game package
```

The `room_state` snapshot in Durable Object SQLite is the sole reconstruction
source. Audit events, hashed player/invite credentials, processed commands, and
single-use socket tickets are operational projections and are never replayed to
rebuild game state. Raw capabilities are returned only to their authorized
caller. The game and lobby domain code imports no Workers, HTTP, WebSocket,
JavaScript, or SQLite modules.

## Repository layout

```text
apps/web/    React, Vite, and TypeScript room/lobby client
apps/api/    FastAPI Worker, lobby domain, room orchestrator, and SQLite repository
supabase/    Supabase CLI project configuration
```

## Prerequisites

- Node.js 22.12 or newer and npm
- Python 3.13 or newer
- [uv](https://docs.astral.sh/uv/)

## Local development

Set up and start the API:

```bash
cd apps/api
cp .env.example .env
npm install
uv sync
uv run pywrangler dev
```

In another terminal, set up and start the frontend:

```bash
cd apps/web
cp .env.example .env.local
npm install
npm run dev
```

Set `VITE_API_URL=http://localhost:8787` in `apps/web/.env.local`. Local backend
values belong in `apps/api/.env`; neither file should be committed.

Open `http://localhost:5173` to create a private room or open an invitation. The
service health endpoint remains available directly:

```bash
curl http://localhost:8787/health
```

Before pushing frontend changes, verify the production build:

```bash
cd apps/web
npm run build
```

Invite links use `/rooms/{roomId}#invite={token}`. The client removes the fragment
before paint and keeps room-scoped credentials in `localStorage` so the same
browser can rejoin after a restart. Explicit leave, removal, or revocation clears
the saved capability; clearing site data makes the session unrecoverable.

In a pre-match lobby, a player is marked `Disconnected` when their final room
socket closes and any Ready state is cleared immediately. If the disconnected
player was host, permission transfers immediately to the earliest-joined human
who is still connected; when nobody else is connected, the transfer waits until
a member reconnects. The lobby shows a five-minute countdown, and reconnecting
from the same saved browser session cancels the removal. If the deadline expires,
the server revokes that player and opens their seat. Started and finished rooms
retain roles, readiness, and disconnected seats without a removal deadline.

New rooms use Singapore preview ruleset `0.3.0` and snapshot schema `4`.
Existing `0.2.0` rooms retain the original draw/discard preview and schema `3`;
`0.1.0` rooms remain lobby-only. No SQL tables or stored legacy snapshots need
rewriting for milestone 4.

Mandatory draws and bonus replacements are automatic. Every discard waits the
full 3000 ms, including when nobody can claim or everybody passes. Each eligible
player can submit one final Chow, Pong, Kong-3, or Pass. Bots choose their hidden
intents in the opening transaction. At the deadline, Kong/Pong outrank Chow;
equal priority goes to the nearest counterclockwise seat. Chow is restricted to
the next counterclockwise seat. Missed responses count as Pass.

Passed Pong faces stay blocked until that player draws or completes a meld;
Chow/Pong cannot use the player's most recent own discard. Kongs take opposite-end
replacements, exposing any bonus chain while retaining the 15-tile reserve.
Kong-4 faces are public. At the final playable tile, eligible Kong-4 and
**Finish Hand** choices have no timeout; neither takes a replacement or discard.
Otherwise wall exhaustion ends the preview automatically as a tie.

Commands retain `{commandId, expectedRevision, actionId}`. Claim IDs are scoped
to the authenticated seat and current window, and stay valid across other
players' responses. Claim commands accept revisions between the window's opening
revision and current revision; ordinary commands still require an exact revision.
Inputs at or after the deadline cannot add a claim. `(playerId, commandId)`
retries remain idempotent. Reusable credentials never appear in URLs.

New action presentation slots are `claimActions` and `turnActions`, with optional
public tile-face previews. `game.ownClaimSubmitted` acknowledges only the viewer's
response. Exposed melds carry `kongKind`, source seat, and discard sequence;
discards retain their original historical entries with claim annotations.
`claimResolved` and `meldDeclared` audit events contain only public resolution
facts. Pending choices and physical tile IDs never enter public events or views.

Ordinary disconnected human turns and final-tile choices wait indefinitely.
Authenticated reconnect reconstructs the same state, pending response, and
original window deadline from SQLite. The table continues to display
**Preview ruleset**, with Game and Kong-1 visibly unavailable.

## Tests

Run the CPython domain and repository suite:

```bash
cd apps/api
uv run pytest
```

The retained CPython Supabase graph resolves a newer Pydantic 2.x release, while
the game package stays on APIs available in Pydantic 2.10. The game tests also
use `unittest`-compatible cases so the same behavior is verified against the
exact Pydantic 2.10.6 Pyodide environment generated by Pywrangler:

```bash
cd apps/api
uv run pywrangler sync
.venv-workers/bin/python -m unittest discover -s tests -p 'test_game_*.py'
```

Run the integration test against the Python Worker and a real local Durable
Object runtime:

```bash
cd apps/api
npm run test:worker
```

Run the browser-client unit and component tests:

```bash
cd apps/web
npm test
```

The Worker integration suite exercises the public FastAPI routes, native Durable
Object IDs, CORS and cache policy, revisions, one-use tickets, WebSocket
broadcasts, and forced Durable Object eviction with hibernating sockets in real
`workerd`. Its narrow test-only subclass is used only for fixed SQLite
inspection. To verify the deployment bundle:

```bash
cd apps/api
uv run pywrangler deploy --dry-run
```

## Deployment

Cloudflare deploys automatically when changes are merged or pushed to `main`.
Work on a branch, test locally, push the branch, and merge it into `main` when it
is ready. The configured build watch paths deploy only the affected application:

```text
mahjong-web: apps/web/*
mahjong-api: apps/api/*
```

After both Cloudflare builds finish, create a room, start against bots, and verify
the table renders on desktop and mobile. Discard a tile, confirm the countdown
reaches `Resolving…` without a client-side transition, and verify the next
authoritative table update arrives without refreshing the page.

## Environment variables

For local development, change frontend values in `apps/web/.env.local` and
backend values in `apps/api/.env`. These files are ignored by Git. When adding a
new variable, add its name with an empty value to the corresponding
`.env.example` file.

For the deployed frontend, add or change values under `mahjong-web` > **Settings**
> **Environment variables** in Cloudflare Pages, then trigger a new deployment.
All `VITE_` variables are included in the browser build and must not contain
secrets.

For the deployed backend, add or change values under `mahjong-api` > **Settings**
> **Variables and Secrets**. Store credentials and API keys as secrets. If a new
secret is required by the application, also declare its name in `secrets.required`
in `apps/api/wrangler.jsonc` and add it to `apps/api/.env.example`.

Never commit credentials or expose a Supabase service-role key to the frontend.

## Supabase

Per the current project override, the existing Supabase initialization,
configuration, dependencies, secrets declarations, and CLI project are retained.
Supabase remains non-authoritative and unused by the Milestone 4 domain and
persistence foundation. `supabase/config.toml` establishes only the local CLI
project boundary; no Supabase tables, migrations, users, authentication flows, or
database queries are introduced by this milestone.
