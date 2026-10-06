# Smart Expense Tracker

*Track less. Understand more. Save smarter.*

An AI-assisted personal finance app for Indian users. Design rule: **all financial numbers are computed deterministically in the backend from stored transactions; AI only explains.**

## Status

**Phases 1 to 9 are fully implemented and tested!**

**Built**
- **Auth & Onboarding:** register, login, logout, 3-step onboarding wizard; argon2id; 15-min access JWT held in memory; rotating 7-day refresh token in an httpOnly cookie with reuse detection; in-process rate limiting; `PATCH /api/auth/me` and `POST /api/auth/onboarding`
- **Dashboard** (`GET /api/dashboard`): computed from stored data in user's timezone; health score; grouped upcoming payments, recurring summary, analytics summary, What Changed, and Safe to Spend metric
- **Transactions & Smart Input:** filterable paginated transactions; Quick-Add natural language text parsing (`spent 250 on lunch yesterday at Swiggy`); natural language search (`uber over 500 last month`)
- **Import Center & Receipt OCR** (`/imports`): CSV statement ingestion with preview, column mapping, automatic duplicate detection (`sha256`); Receipt OCR extraction (merchant, date, total, tax, itemized lines) with one-click conversion to expense transaction
- **AI Money Coach** (`/coach`): grounded, deterministic conversational assistant explaining budget performance, health score components, savings rate, and bill schedules without LLM calculation hallucinations
- **Notifications & Proactive Alerts** (`/notifications`): notification center bell icon with unread badge counter; automatic evaluation of bill due dates, overdue bills, and 80%/100% budget threshold breaches
- **Safe to Spend & Money Timeline:** daily and weekly safe-to-spend allowance computed from liquid balance minus upcoming bills and savings target; 60-day cashflow balance projection curve (`/calendar`)
- **Shared Finances & Split Expenses** (`/shared`): create groups, add members by email, split expenses equally or with custom amounts, view net balances and automated debt settlement instructions
- **Categories & Rules Management** (`/categories`): full UI for expense and income categories, essential tag toggles, and learned merchant categorization rules
- **Privacy Dashboard & Exports** (`/privacy`): full CSV transaction export, complete JSON data takeout (GDPR dump), security audit log inspector, and permanent account deletion
- **Goals, Debts, Net Worth & Subscriptions:** full tracking, simulations, and payoff timelines as designed in Phases 3-4
- **Automated Tests:** 238 backend pytest tests passing; frontend automated test suite with Vitest passing (`npm test`)

## Architecture
See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for layering, schema, API plan, AI pipeline and security design.

## Local setup
```bash
# Backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp ../.env.example .env        # set JWT_SECRET; use COOKIE_SECURE=false for http://localhost
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload     # API docs at http://localhost:8000/docs

# Frontend
cd frontend && npm install && npm run dev   # http://localhost:5173
```
All API routes live under `/api`. The Vite dev server proxies `/api` to the backend, so the refresh cookie is same-origin and browser page URLs like `/transactions` are never confused with API calls.

## Demo data
```bash
cd backend
.venv/bin/python -m app.seed.demo seed     # creates demo@example.com with ~7 months of data, prints a random password
.venv/bin/python -m app.seed.demo status | reset | delete
ENABLE_DEMO=true .venv/bin/uvicorn app.main:app   # demo sign-in only works with this set
```
The seed is deterministic, shifts to today's date, and refuses to touch a non-demo account that holds the same email. Optional `--password`.

## Tests
```bash
cd backend && .venv/bin/python -m pytest -q                    # SQLite, in memory
# PostgreSQL: create a database, `alembic upgrade head` against it, then
TEST_DATABASE_URL=postgresql+psycopg://user:pw@localhost:5432/dbname .venv/bin/python -m pytest -q
```
The PostgreSQL run truncates every table between tests: use a throwaway database.
Frontend: `cd frontend && npx tsc -b && npm run build`. There are no automated frontend tests yet.

## API reference (Phases 3-4)
Full details, algorithms and examples: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#8-phase-3-analytics-recurring-payments-and-bills) and [section 9](docs/ARCHITECTURE.md#9-phase-4-goals-debts-and-net-worth). Interactive docs at `/docs`.

## Design decisions and known limitations
- **Money is `NUMERIC(14,2)` in the database.** Endpoints that return computed dicts (dashboard, analytics, upcoming, calendar) emit JSON numbers; endpoints with Pydantic `Decimal` models (bills, recurring, candidates) emit strings. The client normalises with `num()`. Do not do arithmetic on API values in the client.
- **Total balance** = sum of opening balances + all income − all expenses. Transfers are ignored in that total.
- **Net worth** counts only transactions attached to an account; unassigned transactions are reported, not counted. The trend is rebuilt from current opening balances, valuations and transactions (no snapshots), so it is only as right as those inputs.
- **Debts:** interest in a default payment split is a one-month estimate (balance x rate / 1200), not a lender statement. Undoing a debt payment restores the debt but keeps the expense it created. A credit-card debt plus a credit-card account double counts in net worth (the UI warns).
- **Goals** are not part of net worth; contributions are not transactions.
- **Health score** weights (savings 30, budget 25, recurring load 15, debt burden 15, emergency fund 15) are my own choices, documented in `services/dashboard.py`. Components lacking data are skipped and the total rescales. It is a heuristic, not financial advice. "Cash-flow stability" from the spec is not yet included.
- **Rate limiter is per-process memory.** With more than one worker or instance, limits are per instance; use Redis.
- **Deployment:** `frontend/vercel.json` rewrites `/api/*` to the backend so the cookie stays same-origin. Replace `YOUR-BACKEND-HOST` with your Render/Railway host. Not deployed or tested by me.
- **UI kit:** shadcn/ui from the spec is not installed yet; components are hand-written with Tailwind tokens for now.
- **Migrations** are verified up/down/up on PostgreSQL 16 and SQLite, and the full suite passes on both.
- Account Aggregator / direct bank or UPI access will never be implied; imports will be CSV/manual only.
- **Timezone:** each user has a timezone (default Asia/Kolkata) used for "today"; change it in Settings. A stored invalid zone falls back to Asia/Kolkata.
- **Currency:** analytics, recurring and calendar sum only the user's own currency; other-currency transactions are counted and reported ("excluded"), not converted. The Phase 1 dashboard cards are not currency-filtered.
- **Credit-card bills:** paying a credit-card bill with "also record as expense" counts card purchases twice (purchase and payment). The pay dialog warns; untick the box to avoid it.
- **Overdue by several cycles:** each payment clears one cycle.
- **Recurring detection** is heuristic (see architecture doc); one record per merchant per direction.
- **Rate limiter vs. dev:** 30 refreshes per 5 minutes per IP; a test that reloads the page dozens of times will hit it.
