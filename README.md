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

Open `http://localhost:5173` and use **Test API**, or check the API directly:

```bash
curl http://localhost:8787/health
```

Before pushing frontend changes, verify the production build:

```bash
cd apps/web
npm run build
```

## Deployment

Cloudflare deploys automatically when changes are merged or pushed to `main`.
Work on a branch, test locally, push the branch, and merge it into `main` when it
is ready. The configured build watch paths deploy only the affected application:

```text
mahjong-web: apps/web/*
mahjong-api: apps/api/*
```

After both Cloudflare builds finish, open the production frontend and use
**Test API** to smoke-test the deployment.

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

`supabase/config.toml` only establishes the local CLI project boundary. No
tables, migrations, users, authentication flows, or database queries exist yet.
