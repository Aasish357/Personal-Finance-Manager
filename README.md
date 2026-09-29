# Personal Finance Manager

A FastAPI backend + React (TypeScript) frontend for tracking transactions,
budgets, and spend alerts, with a lightweight AI assistant for asking
questions about your own data.

## Current state

A working full-stack app: 28 endpoints, 8 frontend pages, 60 passing backend
tests, clean `tsc` and a compiling production build.

This README describes the app **as it is now**, not its history — `git log` is
the changelog. (An earlier version of this file carried a "what changed" list,
which went stale within a few commits.)

Feature highlights:

- **Automatic budget alerts.** Recording an expense against a budgeted
  category re-checks utilization and raises an alert at 75% / 90% / 100%.
  There is no "create alert" button, by design.
- **Alerts reconcile both ways.** Deleting — or editing down — the
  transactions that pushed a budget over stands the alert down, so the alerts
  page can never disagree with the budget-vs-actual numbers.
- **A local AI assistant** that answers only from your own figures, backed by
  an Ollama model on your machine.
- **Supabase Postgres** as the database, with Alembic-managed schema.
- **Per-user data isolation**, including categories.

### Verified

| Check | Result |
|---|---|
| `pytest` | 60 passed |
| `npx tsc --noEmit` | clean |
| `npm run build` | Compiled successfully |
| `alembic upgrade head` → `downgrade base` | round trip, constraints enforced |
| Assistant against a live local model | grounded answers, correct figures |

## Backend

```bash
cd <project root>
python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt

cp .env.example .env   # then paste your Supabase connection string into DATABASE_URL

# Create the schema in Supabase (once):
alembic upgrade head

uvicorn app.main:app --reload
```

### Database: Supabase (Postgres)

The app targets **Supabase Postgres**. `DATABASE_URL` in `.env` takes the
connection string from **Supabase Dashboard → Project Settings → Database →
Connection string (URI)**:

```
postgresql://postgres.PROJECT-REF:YOUR-PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres?sslmode=require
```

- Use the **transaction pooler (`:6543`)** for a long-running API server. The
  session pooler (`:5432`) is only needed for prepared statements or advisory
  locks. Keep `?sslmode=require` — Supabase rejects plaintext connections.
  Paste the dashboard string verbatim: a bare `postgresql://` scheme is
  rewritten to the psycopg 3 dialect (`postgresql+psycopg://`) automatically in
  `app/db/database.py`.
- Schema is managed by **Alembic**: `alembic upgrade head` applies the
  baseline migration, and later changes go through
  `alembic revision --autogenerate -m "..."`. `DB_AUTO_CREATE_TABLES` is
  therefore `false` — `create_all` only ever creates *missing* tables, so
  against a real database it would silently ignore column and constraint
  changes. Set it back to `true` (with a SQLite `DATABASE_URL`) for local work.
- `app/db/database.py` configures the engine per dialect: `pool_pre_ping` and
  `pool_recycle` for hosted Postgres (Supabase's pooler reaps idle
  connections), `check_same_thread=False` for SQLite.
- To go back to local SQLite: `DATABASE_URL=sqlite:///./finance.db` and
  `DB_AUTO_CREATE_TABLES=true`.

- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health — unauthenticated, returns
  `{"status": "ok"|"degraded", "database": {"connected": bool}, "warnings": [...]}`
  and answers `200` either way, so a bad database reads as *degraded* rather
  than *down*. It flags a default `SECRET_KEY` or wildcard `CORS_ORIGINS` in
  `warnings` — check those before deploying. The app also logs a loud warning
  at startup if `DATABASE_URL` still contains the `.env.example` placeholders.
- Run tests: `pytest` (runs against throwaway SQLite by default; set
  `TEST_DATABASE_URL` to point the suite at a real Postgres instead)
- The AI assistant runs entirely on a **local Ollama model** — no API key
  and no data leaves your machine. Pull the model once:
  `ollama pull llama3:latest` (set `OLLAMA_MODEL` in `.env` to use a different
  one, e.g. `phi3:mini` for a faster/smaller model). If Ollama isn't running,
  the assistant falls back to rule-based replies computed from your real data
  and says so in the reply.

## Frontend

```bash
cd <project root>
npm install
npm start
```

- Runs at http://localhost:3000, expects the API at
  `REACT_APP_API_URL` (defaults to `http://localhost:8000/api/v1` — see
  `.env.example`).
- `npm run build` produces a production build in `build/`.

## Project structure

```
app/                  FastAPI backend
  main.py             App factory, CORS, startup lifespan
  api/
    health.py         GET /health (unauthenticated liveness + config warnings)
    v1/               Route handlers (auth, transactions, budgets, alerts,
                      categories, analytics, assistant)
  core/
    config.py         Settings from .env
    security.py       bcrypt hashing, JWT encode/decode
    deps.py           get_current_user dependency
    rate_limit.py     In-process fixed-window limiter for auth
  db/
    database.py       Engine + session, branched per dialect
    models/           User, Category, Transaction, Budget, Alert
    mixins.py         TimestampMixin (created_at / updated_at)
    migrations/       Alembic env + versions/
  schemas/            Pydantic request/response models
  utils/
    budget_alerts.py  Alert reconciliation (raise + resolve)
    ollama.py         Local LLM client (native /api/chat over httpx)
    helpers.py        Small shared helpers
  tests/              pytest suite (8 files, 60 tests)

src/                  React frontend
  pages/              8 components, one per route
  components/         AppLayout (shell) + ProtectedRoute (route guard)
  services/           apiClient (axios + interceptors) + one module per resource
  contexts/           AuthContext (session state, login/register/logout)
  types/              Shared TypeScript interfaces matching the API schemas
  utils/              Currency/date formatting, API error extraction
```

## Notable design decisions

- **Alerts are automatic, not manual.** Recording an expense against a
  budgeted category re-checks utilization and raises an alert once it
  crosses 75% / 90% / 100% — there's no "create alert" button in the UI, by
  design. Alerts are also *reconciled* in the other direction: deleting the
  transactions that pushed a budget over stands the alert down (status
  `resolved`), so the alerts page can never disagree with the
  budget-vs-actual numbers. `dismissed` means the user closed it by hand and
  suppresses a re-raise; `resolved` means the system did, and the same
  threshold can legitimately fire again if the spend returns.
- **The assistant is grounded in your real data.** Every chat request pulls
  your current balance and budget-vs-actual numbers server-side and includes
  them in the prompt, rather than answering from general knowledge. The prompt
  spells out whether each budget is over or how much is left, so the model
  doesn't have to subtract and can't misread a utilization percentage as a
  currency overage.
- **The LLM is local, via Ollama.** `app/utils/ollama.py` talks to Ollama's
  native `/api/chat` endpoint over plain `httpx` — no vendor SDK, no API key,
  no outbound network. The blocking call runs in a threadpool so a slow local
  model can't stall the event loop. `GET /api/v1/assistant/status` reports which
  model is configured and whether Ollama is reachable; the assistant page shows
  it and warns if the model isn't pulled. If Ollama is down, the endpoint still
  answers from the rule-based fallback and says why.
- **Postgres is the target; SQLite is the convenience fallback.** The engine in
  `app/db/database.py` branches on the URL, so `DATABASE_URL=sqlite:///./finance.db`
  with `DB_AUTO_CREATE_TABLES=true` still works for offline work, but Supabase
  is what the schema and migrations target.
- **Everything is scoped to the authenticated user.** Categories used to be a
  single global table, so any signed-in user could list and delete everyone
  else's. They now carry `user_id`, and the budget/transaction endpoints
  reject a `category_id` the caller doesn't own (404, not 403, so ids can't be
  probed). Uniqueness moved from a global `name` to `(user_id, name)`, so two
  people can each have "Groceries". Migration `c2d91f4a7b30` backfills existing
  rows by attributing each category to a user who actually used it, and drops
  categories nobody referenced.
- **Login is rate limited** to 5 failures per IP+email per 5 minutes, returning
  `429` with `Retry-After`. The counter is in-process, so behind multiple
  workers each gets its own budget — put Redis (or Postgres) in front if you
  scale out. Login also hashes a dummy password when the email is unknown, so
  response timing can't be used to enumerate accounts.
- **Editing a transaction keeps alerts honest.** `PATCH /transactions/{id}`
  reconciles both the old and new category/month, so lowering an amount
  stands an alert down and moving spending to another category resolves the
  one it left behind.

## Security notes

Read this before exposing the app to anyone.

- **`.env` is gitignored and must stay that way.** It holds the real Supabase
  connection string, the JWT secret, and any API keys. `.env.example` (the
  placeholder template) *is* committed, which is intentional. `.gitignore`
  also excludes `.venv/`, `node_modules/`, `build/` and `*.db` — without the
  `.venv/` rule a `git add .` would commit ~5,000 virtualenv files.
- **Set a real `SECRET_KEY`.** The default `dev-secret-key-change-me` is
  committed in `app/core/config.py`, so anyone can forge a valid JWT with it.
  Generate one with
  `python -c "import secrets; print(secrets.token_hex(32))"`. `/health`
  reports `degraded` while it's still the default.
- **Restrict `CORS_ORIGINS`.** `*` lets any site call the API from a browser.
  Set it to your real frontend origin. `/health` also flags this.
- **The rate limiter is per-process.** Counters live in memory, so behind N
  workers the effective limit is N× what you configured. Put a shared store
  (Redis, or Postgres via Supabase) in front of it if you scale out.
- **JWTs are stored in `localStorage`**, which is readable by any script that
  gets injected into the page. Acceptable for a single-user app; for anything
  public-facing, prefer an httpOnly cookie.
- **Passwords**: bcrypt via passlib, minimum 8 characters. There is no
  complexity requirement, no breached-password check, and no email
  verification.
- **Serve over HTTPS.** Nothing in the app terminates TLS, so put it behind a
  reverse proxy that does.
- **The assistant sends no data anywhere.** It talks to Ollama on
  `localhost` over plain HTTP. Fine on your own machine; don't expose that
  port to a network you don't control.
