# Mahjong

Infrastructure-only monorepo for a future real-time multiplayer Mahjong application.
There are intentionally no game rules, rooms, matchmaking, WebSockets, scoring, or
other application logic in this milestone.

## Architecture

```text
React frontend (Cloudflare Pages)
       │
       ▼
FastAPI backend (Cloudflare Python Worker)
       │
       ├────► Supabase client (configuration only)
       │
       └────► GAME_ROOM Durable Object binding (skeleton only)
```

## Repository layout

```text
apps/web/    React, Vite, and TypeScript status page
apps/api/    FastAPI Cloudflare Python Worker
supabase/    Supabase CLI project configuration
```

## Prerequisites

- Node.js 22.12 or newer and npm
- Python 3.13 or newer
- [uv](https://docs.astral.sh/uv/)

## Frontend development

```bash
cd apps/web
cp .env.example .env.local
npm install
npm run dev
```

Set `VITE_API_URL=http://localhost:8787` in `.env.local` to test the local API.
The Supabase variables are reserved for later integration; no authentication or
database queries are implemented yet.

## Backend development

```bash
cd apps/api
cp .env.example .env
npm install
uv sync
uv run pywrangler dev
```

`npm install` installs the project-local Cloudflare Wrangler CLI. `uv sync`
installs the Python dependencies, including `pywrangler`, which invokes Wrangler
to run the Worker locally.

The Worker is served at `http://localhost:8787` by default. Verify it with:

```bash
curl http://localhost:8787/health
```

Local values in `apps/api/.env` are loaded by Wrangler. For a deployed Worker,
configure `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and `FRONTEND_ORIGIN` as
Cloudflare Worker secrets or environment variables. Never add a Supabase
service-role or secret key to frontend environment variables.

Deploy the backend after authenticating Wrangler with:

```bash
cd apps/api
uv run pywrangler deploy
```

## Cloudflare Pages

Configure the frontend project with:

```text
Root directory:         apps/web
Build command:          npm run build
Build output directory: dist
```

Add `VITE_API_URL`, `VITE_SUPABASE_URL`, and
`VITE_SUPABASE_PUBLISHABLE_KEY` in the Cloudflare Pages environment settings.

## Supabase

`supabase/config.toml` only establishes the local CLI project boundary. No
tables, migrations, users, authentication flows, or database queries exist yet.
