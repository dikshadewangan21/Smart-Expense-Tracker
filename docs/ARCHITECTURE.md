# Smart Expense Tracker: Architecture

Tagline: Track less. Understand more. Save smarter.

## 1. System architecture

```
 Browser (React + TS + Vite)            Vercel
        |  HTTPS, JSON, httpOnly cookies
        v
 FastAPI app (routers -> services -> repositories)     Render/Railway
        |                |                 |
        v                v                 v
  PostgreSQL        Provider adapters   Object storage
  (SQLAlchemy,      - AIProvider        (receipts; local disk
   Alembic)         - OCRProvider        in dev, S3-compatible
                    - BankDataProvider   in prod)
```

Layering rules:
- **routers**: HTTP only; validate with Pydantic; no business logic.
- **services**: all financial calculations. Deterministic, pure where possible, unit-tested.
- **repositories/queries**: every query takes `user_id`; there is no unscoped query helper.
- **providers**: AI, OCR and bank-data adapters behind interfaces, selected by env vars.
- The LLM never computes or invents numbers. It receives pre-computed results and explains them.

## 2. Folder structure

```
smart-expense-tracker/
  docs/                 ARCHITECTURE.md, API.md, ER diagram
  backend/
    app/
      main.py
      core/             config, security (hashing, JWT), rate_limit, errors
      db/               session, base, migrations (alembic/)
      models/           SQLAlchemy models, one file per aggregate
      schemas/          Pydantic request/response models
      routers/          auth, dashboard, transactions, budgets, ...
      services/         dashboard, budgets, health_score, recurring, forecast,
                        safe_to_spend, what_changed, alerts, nl_search
      providers/
        ai/             base.py, anthropic.py, openai.py, gemini.py
        ocr/            base.py, vision.py
        bank/           base.py, csv_provider.py, manual_provider.py, aa_provider.py (documented stub)
      seed/             demo data (Demo Mode only)
    tests/
    alembic.ini
    requirements.txt
  frontend/
    src/
      components/ui/    shadcn/ui
      components/       charts, layout, forms
      pages/            one per route
      lib/              api client, formatters (en-IN), auth
      hooks/
    tests/
  .env.example
  README.md
```

## 3. Database schema (normalized; all tables have `id`, `created_at`, `updated_at`)

Core: `users`, `accounts`, `categories`, `tags`, `transactions` (+ `transaction_tags`).
Planning: `budgets`, `budget_categories`, `recurring_transactions`, `subscriptions`, `bills`.
Goals/debt: `goals`, `goal_contributions`, `debts`, `debt_payments`.
Sharing: `shared_groups`, `group_members`, `group_expenses` (+ per-member split rows).
Capture: `receipts`, `receipt_items`, `imports`.
System: `notifications`, `ai_conversations`, `ai_messages`, `audit_logs`, `refresh_tokens`, `category_rules` (merchant -> category, learned from corrections).

Key decisions:
- Money stored as `NUMERIC(14,2)`, never float. Currency column on transactions.
- `transactions.is_demo` plus a user-level `demo_mode` flag; demo rows live only in a separate demo user, so they can never mix with real data.
- Indexes: `(user_id, date)`, `(user_id, category_id)`, `(user_id, merchant)`, `(user_id, payment_method)`.
- Every user-owned table has `user_id` with FK `ON DELETE CASCADE` (account deletion).
- Import dedupe: unique `(user_id, import_hash)` on transactions.

## 4. API plan

Prefix `/api` (implemented; versioning can be added later). Auth: `POST /auth/register|login|refresh|logout`, `GET /auth/me`.
Resources (CRUD, paginated lists with `page`, `page_size` capped at 100): `/transactions`, `/budgets`, `/subscriptions`, `/bills`, `/goals`, `/debts`, `/accounts`, `/categories`, `/groups`. Implemented so far: transactions, budgets, accounts, categories, recurring, subscriptions, bills (Phase 3 details in section 8).
Computed (read-only): `/dashboard`, `/analytics`, `/cash-flow`, `/net-worth`, `/what-changed`, `/safe-to-spend`, `/timeline`, `/health-score`.
Capture: `POST /receipts/scan`, `POST /imports/csv`, `POST /transactions/parse` (quick add).
AI: `POST /ai/chat`, `POST /ai/categorize`, `POST /search/natural`.
Privacy: `GET /privacy/summary`, `GET /privacy/export`, `DELETE /privacy/account`.
OpenAPI served at `/docs`; every endpoint has summary, response model and error responses.

## 5. UI page structure

Desktop: collapsible sidebar. Mobile: bottom nav (Dashboard, Transactions, Add, Coach, More).
Routes: `/`, `/login`, `/register`, `/onboarding`, `/dashboard`, `/transactions`, `/add-expense`, `/add-income`, `/budgets`, `/recurring`, `/bills`, `/goals`, `/debts`, `/analytics`, `/net-worth`, `/shared`, `/receipts`, `/coach`, `/import`, `/notifications`, `/settings`, `/profile`, `/privacy`.
Every data view has loading skeleton, empty state and error state. Dark mode via CSS variables, persisted in localStorage (preference only, no financial data).

## 6. AI architecture

```
question -> intent classifier (LLM, constrained JSON schema, no data)
         -> intent maps to a whitelisted service function + validated params
         -> service queries DB (parameterized, user-scoped) -> numbers
         -> LLM receives ONLY: question + computed result object
         -> explanation text; response includes the result object as "source"
```

- Intents are a closed enum (spend_by_category, top_merchants, afford_check, subscriptions, trend, ...). Unknown intent -> "I can't answer that from your data."
- NL search: LLM emits a filter JSON validated against a Pydantic model; the backend builds the query with SQLAlchemy. No SQL from the model, ever.
- Post-check: numbers in the LLM reply must appear in the computed result; otherwise return the deterministic template answer instead.
- Providers selected by `AI_PROVIDER` (anthropic|openai|gemini) and keys from env. If unconfigured, AI endpoints return a clear 503 "AI not configured"; deterministic features still work. No fake responses.
- Destructive actions require an explicit confirm step.

## 7. Security architecture

- Passwords: argon2id. Access JWT 15 min; refresh token 7 days, stored hashed in DB, rotated on use, delivered as httpOnly, Secure, SameSite=Lax cookie. CSRF: SameSite plus a double-submit header on state-changing cookie-authenticated routes.
- Authorization: every query scoped by `user_id` from the token; cross-user access tests are mandatory in CI.
- Rate limiting: per-IP and per-user (stricter on `/auth/*` and AI/OCR endpoints).
- Uploads: size cap, MIME sniffing by content (not extension), re-encoding of images, randomized storage names, private bucket with short-lived signed URLs.
- Input validation via Pydantic; CORS restricted to the configured frontend origin.
- Audit log: login, password change, export, deletion, import, integration changes.
- Privacy: data export (JSON/CSV), account deletion with cascade, AI usage log visible to the user, only aggregated/computed data sent to LLMs.
- Secrets only via environment; `.env.example` contains no real values.


## 8. Phase 3: analytics, recurring payments and bills

All numbers here are computed in SQL/Python from stored rows; no LLM is involved. Services: `periods`, `schedule`, `analytics`, `recurring`, `bills`; routers: `analytics`, `recurring`, `bills`.

### 8.1 Periods and comparison rules
`period` = `this_month | last_month | last_3_months | last_6_months | this_year | custom` (+ `date_from`, `date_to` for custom, max range and ordering validated, 422 otherwise). "Today" is the user's timezone date (`core/clock.user_today`).
- Every period carries a like-for-like previous period. A partial current period (e.g. 1-5 Oct) is compared with the same number of days earlier (1-5 Sep), not the whole previous month.
- Transfers are excluded everywhere. Only the user's currency is summed; other-currency rows are counted in `excluded_other_currency`.
- Future-dated transactions are excluded from current periods. Average daily spending divides by days elapsed, not days in the period.

### 8.2 Analytics API
| Endpoint | Purpose |
|---|---|
| `GET /api/analytics?period=...` | period, previous_period, totals (income, expenses, net_savings, savings_rate, average_daily_spending, transaction_count), previous_totals, changes, by_category, by_merchant (top 10 + other), by_payment_method, income_vs_expenses (day/week/month buckets), monthly_trend (6 months), month_over_month, week_over_week (Monday start), highest_category, highest_spending_day, largest_transactions, essential_vs_discretionary, budget_performance, excluded_other_currency |
| `GET /api/what-changed?period=...` | spending and income change, categories that went up / down (with new / stopped flags and share of the change), `headline` and `drivers_sentence` built from templates, `comparable=false` with an explanation when there is nothing to compare |

`savings_rate` is `null` (not 0) when income is zero. Drill-downs use `GET /api/transactions` with `category_id`, `uncategorized`, `merchant_exact`, `payment_method`, `type`, `date_from`, `date_to`.

### 8.3 Recurring detection
Computed on demand from transactions (lookback 1200 days); only confirm / ignore / manual create persist anything. One `recurring_transactions` row per `(user, type, merchant_key)`.
1. Group by normalised merchant key and type; collapse same-day entries.
2. Keep "core" amounts within +/-25% of the median; the rest are treated as one-offs.
3. Gaps between dates are matched to a frequency window: weekly 6-8 days, biweekly 12-16, monthly 27-34, quarterly 84-98, yearly 355-375.
4. A pattern is lapsed (dropped) if more than 1.75 periods have passed since the last payment.
5. `confidence = 0.45*regularity + 0.25*amount_consistency + 0.20*occurrence_score + 0.10*recency`. Fewer than 3 occurrences caps confidence at 0.69.
6. `>= 0.70` is suggested; `0.40-0.70` is returned only with `include_uncertain=true` as a "possible pattern". Merchants that match an active bill name are excluded (they are tracked as bills).
7. Next payment: `next_after(base, frequency, today, anchor_day)` returns the first scheduled date that is also more than half a period after the last payment (so an early payment doesn't produce a duplicate next date). Month-end anchoring keeps the 31st (Jan 31, Feb 28, Mar 31).

| Endpoint | Purpose |
|---|---|
| `GET /api/recurring/candidates?include_uncertain=` | detected, unconfirmed patterns with `reasons` |
| `POST /api/recurring/confirm` | `{merchant_key, type, frequency?, category_id?, amount?, merchant?}` |
| `POST /api/recurring/ignore` | hide a pattern; `GET /api/recurring/ignored` lists them; `DELETE /api/recurring/{id}` restores |
| `POST /api/recurring` | manual add `{merchant, amount, frequency, next_date, ...}` |
| `GET /api/recurring`, `PUT/DELETE /api/recurring/{id}` | confirmed items, edit (including `status: paused`), delete |
| `GET /api/subscriptions?sort=monthly\|cost\|renewal\|category&order=` | confirmed expenses with next date, monthly equivalent, annual cost, totals, `pending_review` |

### 8.4 Bills API
Bill kinds: rent, electricity, internet, phone, insurance, emi, credit_card, custom. Frequencies: once, weekly, monthly, quarterly, yearly. `due_date` is the next unpaid due date.
| Endpoint | Purpose |
|---|---|
| `GET /api/bills?status=&sort=due\|amount\|name` | default lists overdue, due today and upcoming; `status=paid\|inactive` for the rest; summary (overdue total, next 7 days, monthly commitment) |
| `POST /api/bills`, `GET/PUT/DELETE /api/bills/{id}` | CRUD |
| `POST /api/bills/{id}/pay` | `{paid_on?, amount?, create_transaction=true, account_id?, payment_method?}`; repeating bills advance exactly one period, once-bills become `paid`; optionally creates an expense (source `bill`, merchant = bill name) |
| `GET /api/upcoming?days=30` | bills + confirmed recurring, grouped overdue / today / tomorrow / this_week (2-7 days) / later; a confirmed recurring item with a bill's name appears once, as the bill |
| `GET /api/calendar?month=YYYY-MM` | per-day events (bill, recurring, income) with status paid / scheduled / due_today / overdue / received / expected; month summary; `large` flag = unpaid amount >= 25% of average monthly income over the last 3 completed months |

`reminder_days` (default 7, 3, 1, 0) is stored and validated; reminder notifications are not generated until Phase 7.

### 8.5 Demo seed
`python -m app.seed.demo seed|reset|delete|status [--password ...]`. One reserved account (`demo@example.com`, `users.is_demo`), deterministic (random seed 20261004), data shifted to today: ~370 transactions over 7 months, 3 accounts, budgets, 9 bills (one always overdue), 3 goals, 1 debt, 3 confirmed recurring items and 4 left as candidates. Sign-in requires `ENABLE_DEMO=true`; the UI shows a banner for demo accounts; the CLI refuses to modify a non-demo account holding the email.

### 8.6 Frontend (Phase 3)
Routes `/analytics`, `/subscriptions`, `/bills`, `/calendar`, `/settings`; Dashboard gained What Changed, recurring summary, analytics summary and grouped upcoming payments. Filters and period live in the URL so drill-downs are shareable. Phone nav shows four primary tabs plus a "More" menu.


## 9. Phase 4: goals, debts and net worth

Migration `8605b7acb86a`: `transactions.to_account_id`, `account_valuations`, `goal_contributions.note`, `debts.start_date`/`bill_id`, `debt_payments.principal_paid`/`transaction_id` (existing payments are backfilled as fully principal).

**Goals** (`services/goals.py`). `current_amount` is stored truth; contributions adjust it (negative = withdrawal, never below 0); deleting one reverses it. `months_left = max(1, ceil(days/30.4375))`; `required_monthly = remaining / months_left` rounded up to the paisa. Pace = net contributions in the last 1-3 months (capped by time since the first contribution) / window months. Estimated completion = today + ceil(remaining / pace) months; `on_track = estimate <= target_date`. Status: active, overdue, completed. A future target date is required on create; future-dated contributions are rejected; PUT cannot change the saved amount.

**Debts** (`services/debts.py`). Owed kinds: personal, education, credit_card, borrowed; receivable: lent. A payment has `amount` and `principal_paid`; default interest = remaining x rate / 1200, principal = amount - interest. Rejected: principal > remaining, or interest portion above the estimate + 0.01. Lent repayments never create a transaction; owed payments create an "EMI & Loans" expense by default. `simulate_payoff` runs month by month (interest = round(balance x rate/1200, 2)); if interest >= EMI it returns no date and says why; capped at 600 months. A debt may link to a bill: paying the bill records a clamped debt payment (never fails the bill payment) and the bill is excluded from the health score's recurring load so the EMI counts once.

**Net worth** (`services/networth.py`). Account balance on date D = latest valuation <= D (valued at end of that day), else opening balance, plus later transactions up to D (income +, expense -, transfers only when both accounts are set). Own currency only. Debt remaining at D = remaining + principal paid after D. Assets: cash, bank, investments, property, other, lent. Liabilities: loans, credit card (negative card accounts and card debts), other debt. Trend = last N month-ends plus today; `change` compares today with one calendar month earlier.

**APIs.** `GET/POST /goals`, `GET/PUT/DELETE /goals/{id}`, `POST /goals/{id}/contributions`, `DELETE /goals/{id}/contributions/{cid}`; `GET/POST /debts`, `GET/PUT/DELETE /debts/{id}`, `POST /debts/{id}/payments`, `DELETE /debts/{id}/payments/{pid}`; `GET /net-worth?months=1..60`, `PUT /accounts/{id}`, `GET/POST /accounts/{id}/valuations`, `DELETE /accounts/{id}/valuations/{vid}`; `GET /accounts?include_archived`. Transfers: `type=transfer` with `account_id` and `to_account_id` (different, no category).
