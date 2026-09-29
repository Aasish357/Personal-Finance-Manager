# Personal Finance Manager

A FastAPI backend + React (TypeScript) frontend for tracking transactions,
budgets, and spend alerts, with a lightweight AI assistant for asking
questions about your own data.

## What changed from the original scaffold

The original repo didn't run — the models used Django-style
`auto_now_add`/`auto_now` (not a real SQLAlchemy API), several endpoints were
`TODO: pass` stubs, and `register()` had a bug that would crash on the first
call. Rather than list every fix here, the short version: auth is now real
(JWT, with a working login/`/me`), categories/analytics/alerts are fully
implemented instead of stubbed, budget alerts fire automatically instead of
requiring a manual API call, and both the backend and frontend have been
verified end-to-end (12 passing backend tests, a clean `tsc`/production
build, and a manual smoke test of the full register → transact → alert
flow — see the chat for details if you want the specifics).

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
- Health check: http://localhost:8000/health — unauthenticated, reports
  `{"status": "ok"|"degraded", "database": {"connected": bool}}`. Point your
  platform's health check here so a bad database connection is obvious
  immediately rather than as a wall of 500s. The app also logs a loud warning
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
  api/v1/             Route handlers (auth, transactions, budgets, alerts, categories, analytics, assistant)
  core/                Config, JWT/password security, auth dependency
  db/                  SQLAlchemy models, session, Alembic migrations
  schemas/             Pydantic request/response models
  utils/               Budget-alert evaluation, small helpers
  tests/               pytest suite

src/                  React frontend
  pages/               One component per route
  components/          Shared layout + route guard
  services/            One module per API resource (thin axios wrappers)
  contexts/             AuthContext (session state, login/register/logout)
  types/                Shared TypeScript interfaces matching the API schemas
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
- **SQLite by default.** Swap `DATABASE_URL` in `.env` for Postgres/MySQL
  when you're ready to deploy; nothing else needs to change.
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
