# 💰 Smart Expense Tracker

<div align="center">

*Track less. Understand more. Save smarter.*

An intelligent, full-stack personal finance application built specifically for modern financial workflows.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.14-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![React](https://img.shields.io/badge/React-19.2+-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-6.0+-3178C6?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-v4-06B6D4?style=flat&logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-D71F00?style=flat&logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org)
[![Alembic](https://img.shields.io/badge/Alembic-1.14+-red?style=flat)](https://alembic.sqlalchemy.org)
[![Tests](https://img.shields.io/badge/Tests-238%20Passed-success?style=flat&logo=pytest&logoColor=white)](https://docs.pytest.org)
[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=flat)](LICENSE)

[Features](#-key-features) •
[Architecture](#-architecture) •
[Tech Stack](#-tech-stack) •
[Quick Start](#-quick-start) •
[Demo Mode](#-demo-mode) •
[Testing](#-testing) •
[API Reference](#-api-overview)

</div>

---

## 💡 Philosophy & Core Design Rule

Most financial apps either drown you in manual data entry or use LLMs that invent made-up calculations. **Smart Expense Tracker is built on a fundamental design rule:**

> **All financial calculations and arithmetic are computed 100% deterministically in the backend from verified database records.**
> **AI and LLMs only explain and contextualize pre-computed figures—they never calculate, extrapolate, or hallucinate numbers.**

- **Precision First:** All monetary values are handled using fixed-point `Decimal` (`NUMERIC(14,2)` in SQL). Floating-point math is strictly forbidden.
- **Privacy by Default:** Zero tracking, full data takeout in JSON, one-click CSV exports, and complete GDPR account erasure.
- **Indian Number Grouping Support:** Native support for Indian Lakhs/Crores digit grouping (`₹1,23,456.50`) alongside international standards.

---

## 🚀 Key Features (Phases 1–9 Complete)

### 📊 1. Intelligent Dashboard & Financial Health Score
- **Live Cash Flow & Balance:** Real-time visibility into total liquid balance, monthly income, monthly expenses, and net savings.
- **5-Pillar Financial Health Score (0–100):** Transparent scoring evaluated across savings rate (30 pts), budget adherence (25 pts), recurring commitment burden (15 pts), debt load (15 pts), and emergency fund status (15 pts). Every point is accompanied by a plain-English explanation.
- **"What Changed?" Engine:** Automated like-for-like period comparison highlighting the exact spending drivers without relying on LLM summaries.

### ⚡ 2. Smart Input & Transactions
- **Quick-Add Natural Language Input:** Type freeform sentences like `spent 450 at Swiggy yesterday via upi` or `received 50000 salary today` to automatically extract merchant, amount, category, date, and payment method.
- **Natural Language Search:** Search your finances conversationally (`uber over 500 last month`, `swiggy upi this month`).
- **Comprehensive Filtering:** Filter by date range, merchant, category, account, payment method, tags, or unclassified items.
- **Transfer Handling:** Account-to-account transfers adjust balances without distorting income/expense metrics.

### 🤖 3. AI Money Coach
- **Grounded Financial Assistant:** Conversational AI coach with access to real calculated metrics (budget headroom, savings rate, pending bills, liabilities).
- **Extensible Provider Architecture:** Plug-and-play support for local deterministic explanations, OpenAI, Anthropic, or Google Gemini.
- **Conversation History:** Multi-session chats with suggested follow-up prompts and context summaries.

### 📥 4. Import Center & Receipt OCR Scanner
- **CSV Bank & Card Statement Ingestion:** Smart header recognition supporting HDFC, ICICI, SBI, Axis, AMEX, and custom CSV layouts.
- **Cryptographic Deduplication:** Uses `sha256(user_id:date:amount:merchant:type:account_id)` to prevent duplicate entries even if the same file is uploaded multiple times.
- **Receipt OCR Engine:** Upload photo receipts or invoices to extract merchant, invoice date, taxes, line items, and total amount with one-click conversion into expense records.

### 🔔 5. Proactive Notifications & Alert Center
- **Bill Reminders:** Automatic notifications triggered according to customized bill reminder schedules (e.g. 7 days, 3 days, 1 day, or day of due date).
- **Overdue Bill Warnings:** High-priority alerts for unpaid bills past their due date.
- **Budget Threshold Alerts:** Real-time warnings when reaching 80% or exceeding 100% of category or monthly budgets.
- **Notification Center UI:** Header bell icon with real-time unread badge, dropdown list, and one-click "Mark all read".

### 🛡️ 6. Safe to Spend & Money Timeline
- **Safe-to-Spend Calculator:** Dynamically computes daily and weekly spending allowances by subtracting upcoming bills and savings targets from current liquid accounts.
- **60-Day Cashflow Curve:** Forward-looking interactive projection curve that charts expected balance trajectories based on salary schedules, recurring charges, and average daily burn rates.

### 👥 7. Shared Finances & Split Expenses
- **Shared Groups:** Create groups for roommates, vacations, couples, or events.
- **Equal & Custom Splits:** Add group expenses split evenly or with custom allocations.
- **Minimal Debt Settlement Algorithm:** Automatically calculates net balances and generates the fewest payment steps to settle all debts.

### 🏷️ 8. Categories & Learned Categorization Rules
- **Full Category Management:** Create, rename, customize, and delete expense and income categories.
- **Essential vs. Discretionary:** Flag essential categories (rent, groceries, healthcare) for automatic budget split analysis.
- **Merchant Rule Engine:** Learns merchant-to-category associations as you edit transactions to automate future classification.

### 🎯 9. Savings Goals, Debts & Net Worth
- **Savings Goals:** Multi-pot goal tracking with dated contribution histories, monthly savings pace, and estimated completion dates.
- **Debt Payoff Simulator:** Amortization simulation tracking principal vs. interest splits, EMI commitments, and debt-to-income ratios.
- **Net Worth Tracking:** Real-time assets vs. liabilities tracking with manual valuations for investments and properties.

### 🔒 10. Privacy & Data Takeout
- **CSV Spreadsheet Export:** Export your entire transaction history to Excel/Google Sheets.
- **Full GDPR Data Dump:** Complete JSON takeout of all profile data, accounts, transactions, bills, goals, and debts.
- **Security Audit Logs:** Transparent audit trail recording logins, profile edits, deletions, and payments.
- **Account Deletion:** Password-confirmed permanent erasure of all user data and cascading records.

---

## 🏗️ Architecture

The project follows a clean, decoupled architecture:

```
[ Frontend: React 19 + TypeScript + Vite + Tailwind CSS v4 ]
                          │
                   HTTPS / JSON API
                          │
     ┌────────────────────▼────────────────────┐
     │           FastAPI Application           │
     │  - HTTP routing & Pydantic validation   │
     │  - JWT Auth + Rotating Refresh Cookies  │
     │  - Rate Limiting & Security Middlewares │
     └────────────────────┬────────────────────┘
                          │
     ┌────────────────────▼────────────────────┐
     │         Business Logic Services         │
     │  - Deterministic Math & Financial SQL   │
     │  - Safe-to-Spend & Timeline Calculators │
     │  - Bill Scheduling & Notification Engine│
     │  - Split Expense Settlement Solver      │
     └────────────────────┬────────────────────┘
                          │
     ┌────────────────────▼────────────────────┐
     │        SQLAlchemy 2.0 ORM Layer         │
     │  - Multi-tenant Scoping (user_id FK)    │
     │  - Strict Numeric(14,2) for Money       │
     │  - Alembic Versioned Migrations         │
     └────────────────────┬────────────────────┘
                          │
         ┌────────────────┴────────────────┐
         ▼                                 ▼
   SQLite (Dev/Test)             PostgreSQL 16 (Prod)
```

### Directory Structure

```
smart-expense-tracker/
├── backend/
│   ├── alembic/              # Database migration versions
│   ├── app/
│   │   ├── core/             # Config, security, JWT, rate limit, clock, money utilities
│   │   ├── db/               # Database engine and session factory
│   │   ├── models/           # SQLAlchemy 2.0 declarative database models
│   │   ├── providers/        # OCR and AI Money Coach provider interfaces
│   │   │   ├── ai/           # Deterministic, OpenAI, Gemini, Anthropic providers
│   │   │   └── ocr/          # Heuristic receipt parser & OCR extractor
│   │   ├── routers/          # FastAPI routers (auth, transactions, coach, imports, etc.)
│   │   ├── schemas/          # Pydantic v2 validation models
│   │   ├── seed/             # Deterministic demo data seeder
│   │   ├── services/         # Deterministic financial calculators and business logic
│   │   └── main.py           # Application entrypoint & CORS configuration
│   ├── tests/                # 238 Pytest unit & integration test cases
│   └── requirements.txt      # Python dependencies
│
├── frontend/
│   ├── src/
│   │   ├── components/       # Shared UI (Layout, Modal, Stat, ErrorBox, etc.)
│   │   ├── lib/              # API client, Auth context, formatters, types
│   │   ├── pages/            # Feature pages (Dashboard, Coach, Imports, Shared, etc.)
│   │   └── __tests__/        # Vitest frontend automated tests
│   ├── package.json          # Node dependencies
│   └── vite.config.ts        # Vite configuration with API proxy
└── docs/
    └── ARCHITECTURE.md       # In-depth architectural & financial specs
```

---

## 🛠️ Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend Framework** | **FastAPI** 0.115+ (Python 3.10–3.14) |
| **ORM & Database** | **SQLAlchemy 2.0**, **Alembic**, PostgreSQL 16 / SQLite |
| **Auth & Security** | **Argon2id** (`argon2-cffi`), **PyJWT** (HS256), rotating httpOnly Cookies |
| **Data Validation** | **Pydantic v2** & `pydantic-settings` |
| **Frontend Framework** | **React 19**, **TypeScript 6**, **Vite 8** |
| **Styling & Icons** | **Tailwind CSS v4**, **Lucide React** |
| **Data Visualization** | **Recharts 3.x** |
| **Testing** | **Pytest** (Backend - 238 tests), **Vitest** (Frontend) |

---

## ⚡ Quick Start

### Prerequisites
- Python 3.10 or higher
- Node.js 18 or higher & npm
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/dikshadewangan21/Smart-Expense-Tracker.git
cd Smart-Expense-Tracker
```

### 2. Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp ../.env.example .env
# Edit .env to set your JWT_SECRET (e.g. generate with: openssl rand -hex 32)
# For local dev, ensure COOKIE_SECURE=false

# Run migrations
alembic upgrade head

# Start backend server
uvicorn app.main:app --reload
```
The backend API will be available at `http://localhost:8000`. Interactive OpenAPI documentation is accessible at `http://localhost:8000/docs`.

### 3. Frontend Setup
Open a new terminal window:
```bash
cd frontend

# Install dependencies
npm install

# Start Vite dev server
npm run dev
```
The frontend application will be running at `http://localhost:5173`. The Vite proxy automatically routes all `/api` requests to the FastAPI backend.

---

## 🎭 Demo Mode

The application includes a deterministic demo seeder containing ~7 months of realistic financial transactions, recurring subscriptions, EMIs, and bills ending on the current date:

```bash
cd backend

# Seed demo user (demo@example.com)
.venv/bin/python -m app.seed.demo seed

# Check demo status
.venv/bin/python -m app.seed.demo status

# Reset or delete demo data
.venv/bin/python -m app.seed.demo reset
.venv/bin/python -m app.seed.demo delete
```

> **Security Note:** Demo user sign-in is strictly disabled in production. To allow signing into the demo account, run the backend with `ENABLE_DEMO=true`.

---

## 🧪 Testing

### Backend Test Suite
The backend contains 238 automated tests covering financial math, transaction scoping, authentication security, and all phase services:

```bash
cd backend

# Run with SQLite (in-memory)
.venv/bin/pytest

# Run with PostgreSQL (optional)
TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/test_db .venv/bin/pytest
```

### Frontend Test Suite
```bash
cd frontend

# Run Vitest unit tests
npm test

# Production build check
npm run build
```

---

## 📡 API Overview

All endpoints are mounted under the `/api` prefix:

| Group | Endpoints | Description |
| :--- | :--- | :--- |
| **Auth** | `POST /api/auth/register`<br>`POST /api/auth/login`<br>`POST /api/auth/logout`<br>`GET /api/auth/me`<br>`POST /api/auth/onboarding` | Authentication, token rotation, and onboarding |
| **Dashboard** | `GET /api/dashboard` | Computed financial summaries, health score, and insights |
| **Transactions** | `GET /api/transactions`<br>`POST /api/transactions`<br>`PUT /api/transactions/{id}`<br>`DELETE /api/transactions/{id}`<br>`POST /api/transactions/{id}/duplicate` | CRUD transactions, pagination, and multi-filters |
| **AI Coach** | `POST /api/coach/chat`<br>`GET /api/coach/conversations`<br>`POST /api/coach/quick-add`<br>`GET /api/coach/nl-search` | AI Money Coach and natural language input |
| **Imports & OCR** | `POST /api/imports/preview`<br>`POST /api/imports/execute`<br>`POST /api/receipts/upload`<br>`POST /api/receipts/{id}/confirm` | CSV statement ingestion and receipt scanner |
| **Planning** | `GET /api/budgets`<br>`POST /api/budgets`<br>`GET /api/categories`<br>`GET /api/planning/safe-to-spend`<br>`GET /api/planning/timeline` | Budgets, categories, safe-to-spend & 60-day cashflow |
| **Shared** | `GET /api/shared/groups`<br>`POST /api/shared/groups`<br>`POST /api/shared/groups/{id}/expenses` | Shared finance groups, splits, and settlement calculation |
| **Notifications** | `GET /api/notifications`<br>`POST /api/notifications/evaluate`<br>`POST /api/notifications/read-all` | Proactive alerts for bills and budgets |
| **Bills & Recurring** | `GET /api/bills`<br>`POST /api/bills/{id}/pay`<br>`GET /api/recurring`<br>`GET /api/calendar` | Bill management, recurring detection, and calendar |
| **Goals & Debts** | `GET /api/goals`<br>`POST /api/goals/{id}/contributions`<br>`GET /api/debts`<br>`POST /api/debts/{id}/payments` | Savings targets and loan repayment simulations |
| **Privacy** | `GET /api/privacy/export/csv`<br>`GET /api/privacy/export/json`<br>`GET /api/privacy/audit-logs`<br>`POST /api/privacy/delete-account` | Data takeout, spreadsheet export, and account deletion |

Interactive documentation is available at `http://localhost:8000/docs`.

---

## 🔒 Security & Privacy Architecture

- **Argon2id Password Hashing:** State-of-the-art password derivation resistant to GPU/ASIC attacks.
- **Short-Lived Access Tokens:** 15-minute JWT tokens stored exclusively in client memory (never in `localStorage`).
- **Rotating Refresh Tokens:** 7-day refresh tokens stored in `httpOnly`, `SameSite=Lax`, `Secure` cookies with cryptographic family revocation upon reuse detection.
- **Multi-Tenant Data Isolation:** Every database query is explicitly scoped by authenticated `user_id`. Cross-user data leakage is strictly prevented.
- **Rate Limiting:** Sliding-window rate limiters prevent brute-force attacks on authentication endpoints.
- **Audit Logging:** Sensitive actions (profile updates, account deletion, bill payments) are logged to the `audit_logs` table.

---

## 📄 License

This project is open-source software licensed under the **[MIT License](LICENSE)**.
