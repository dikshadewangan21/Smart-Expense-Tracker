# Smart Expense Tracker

*Track less. Understand more. Save smarter.*

An AI-assisted personal finance app for Indian users. Design rule: **all financial numbers are computed deterministically in the backend from stored transactions; AI only explains.**

## Status (read this first)

Phases 1 to 4 of the 9-phase plan are built and tested. Everything under "Not built yet" does **not exist**, and the UI does not pretend otherwise (the sidebar lists only real pages).

**Built**
- **Auth:** register, login, logout; argon2id; 15-min access JWT held in memory; rotating 7-day refresh token in an httpOnly cookie with reuse detection (the client sends one refresh at a time); in-process rate limiting; `PATCH /api/auth/me` for name and timezone
- **Schema:** the spec's tables plus `refresh_tokens`, `category_rules`, `transaction_tags`; Alembic migrations (initial, user timezone, Phase 3 bills and recurring, Phase 4 goals/debts/net worth), upgrade/downgrade tested on PostgreSQL 16 and SQLite
- **Dashboard** (`GET /api/dashboard`): every figure computed from stored data in the user's timezone; transparent health score; grouped upcoming payments, recurring summary, analytics summary and What Changed
- **Transactions, categories, budgets, accounts:** as in Phase 2. Transactions also filter by `uncategorized` and `merchant_exact` (used by chart drill-downs)
- **Analytics** (`/analytics`): this month, last month, last 3 months, last 6 months, this year, custom range; totals, savings rate, average daily spending, category / merchant / payment-method breakdowns, income vs expenses, 6-month trend, month-over-month and week-over-week, largest transactions, essential vs discretionary, budget performance. Clicking a category, merchant, pie slice or payment method opens the matching transactions
- **What Changed?** (`/api/what-changed`, also on Dashboard and Analytics): like-for-like comparison with the previous period; sentences are templates filled from computed numbers, no LLM
- **Recurring detection and Subscriptions** (`/subscriptions`): detected from transactions, nothing counts until you confirm; edit, pause, delete, ignore and restore, manual add, sorting, monthly and annual cost
- **Bills** (`/bills`): CRUD, statuses (overdue, due today, upcoming, paid, inactive), pay with optional "also record as expense", repeat advances one cycle
- **Upcoming payments and bill calendar** (`/calendar`): bills plus confirmed subscriptions plus income; month grid on desktop, list on phones; large-payment flag
- **Settings** (`/settings`): name and timezone
- **Demo mode:** `python -m app.seed.demo` creates one reserved demo account; sign-in is blocked unless `ENABLE_DEMO=true`; a banner shows whenever a demo account is signed in; demo data is never mixed with real accounts
- **Goals** (`/goals`): create/edit/delete; saved amount changes only through dated contributions (add or withdraw) so history explains it; required monthly, current pace, estimated completion, on-track verdict
- **Debts** (`/debts`): owed (personal, education, credit card, borrowed) and lent; payments split into principal and interest, overpay rejected; month-by-month payoff simulation (says so when EMI does not cover interest); debt-to-income; paying a linked bill records the debt payment
- **Net worth** (`/net-worth`): assets minus liabilities from account balances, dated valuations (investments, property), and debts; month-end trend; account add/edit/archive; transfers between accounts (`/add-transfer`)
- **Tests:** 230 backend tests, passing on SQLite and on PostgreSQL 16

**Not built yet** (phases 5-9): goals / debt / net-worth pages and CRUD, onboarding, import center, receipt OCR, AI Money Coach, quick-add text parsing, NL search, alert and notification generation (bill reminder days are stored, nothing sends them), Safe to Spend, Money Timeline beyond the calendar, shared finances, exports/PDF, privacy dashboard, frontend automated tests. Budget rollover is stored but not applied. There is no UI for categories (API only).

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
