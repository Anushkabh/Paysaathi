# Takaada Receivables Service

A backend service that integrates with an external accounting system, syncs customer/invoice/payment data locally, and exposes credit-insight APIs for receivables management.

## Quick Start

```bash
# 1. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the mock external accounting API (Terminal 1)
uvicorn mock_server.server:app --port 8001

# 4. Start the main service (Terminal 2)
uvicorn app.main:app --reload --port 8000

# 5. Trigger initial data sync
curl -X POST http://localhost:8000/sync/

# 6. Explore the interactive API docs
open http://localhost:8000/docs
```

## Running Tests

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

---

## Architecture & Design Decisions

### Tech Stack

| Choice | Why |
|---|---|
| **Python + FastAPI** | Async-ready, auto-generated OpenAPI docs, clean dependency injection — ideal for an integration service |
| **SQLAlchemy ORM** | Mature ORM with relationship support; makes it easy to swap SQLite for Postgres later without changing business logic |
| **SQLite** | Zero-config for local dev/review — the `DATABASE_URL` env var makes it trivial to point at Postgres in production |
| **httpx** | Modern HTTP client with timeout/retry support; drop-in replacement for `requests` with async capability |

### Project Structure

```
├── app/
│   ├── api/                  # Route handlers (thin controllers)
│   │   ├── sync.py           # POST /sync — trigger data pull
│   │   ├── customers.py      # GET /customers
│   │   ├── invoices.py       # GET /invoices
│   │   └── insights.py       # GET /insights/*
│   ├── external/
│   │   └── accounting_client.py  # HTTP client for the external API
│   ├── models/               # SQLAlchemy ORM models
│   ├── schemas/               # Pydantic request/response schemas
│   ├── services/
│   │   ├── sync_service.py    # Fetches + upserts external data
│   │   └── insights_service.py  # Computes financial insights
│   ├── config.py
│   ├── database.py
│   └── main.py
├── mock_server/              # Simulated external accounting API
│   └── server.py
├── tests/
│   ├── conftest.py           # Fixtures (in-memory DB, test client)
│   ├── test_sync.py
│   └── test_insights.py
```

### Layered Architecture

```
API Routes  →  Services  →  Models / External Client
   (thin)       (logic)       (data access)
```

- **API layer** is thin — validates input, calls a service, returns the response.
- **Service layer** holds all business logic (sync orchestration, insight calculations, risk scoring).
- **External client** isolates all HTTP calls to the third-party system behind a clean interface, making it easy to mock in tests.

### Database Schema

```
customers
  ├── id (PK, string)         — matches external system ID
  ├── name, email, phone
  ├── credit_limit
  └── synced_at               — tracks last sync time

invoices
  ├── id (PK, string)
  ├── customer_id (FK → customers)
  ├── amount, due_date, issued_date
  ├── status (enum: pending | partially_paid | paid | overdue)
  └── synced_at

payments
  ├── id (PK, string)
  ├── invoice_id (FK → invoices)
  ├── amount, payment_date
  ├── method, reference
  └── synced_at
```

**Key decisions:**
- **External IDs as primary keys** — avoids a separate mapping table and makes upsert logic straightforward.
- **`synced_at` on every table** — enables incremental sync and debugging stale data.
- **Status recomputed after sync** — the service recalculates invoice statuses from actual payment totals, so we don't blindly trust the external system's status field.

### Sync Strategy

The sync is **full-pull + upsert**:
1. Fetch all customers, invoices, and payments from the external API.
2. For each record: if it exists locally, update it; otherwise, insert it.
3. After syncing payments, **recompute invoice statuses** from actual payment data.

This approach is idempotent and safe to run repeatedly. The sync can be triggered manually via `POST /sync/` or scheduled via cron/APScheduler.

### Insight APIs

| Endpoint | What it returns |
|---|---|
| `GET /insights/balances` | Outstanding balance per customer (invoiced vs paid) with credit utilization % |
| `GET /insights/overdue` | All overdue invoices, sorted by days overdue, with partial payment info |
| `GET /insights/aging` | Accounts receivable aging report (0-30, 31-60, 61-90, 90+ day buckets) |
| `GET /insights/credit-report/{id}` | Full credit report for one customer: balance, overdue count, avg days-to-pay, aging breakdown, and **risk level** (LOW/MEDIUM/HIGH) |

### Risk Scoring

A simple point-based system:
- Credit utilization > 80% → +2 pts; > 50% → +1 pt
- 3+ overdue invoices → +2 pts; 1+ → +1 pt
- Average days to pay > 60 → +1 pt

Score ≥ 3 = **HIGH**, ≥ 2 = **MEDIUM**, else **LOW**.

### Edge Cases Handled

- **Timezone-naive datetimes** — SQLite strips timezone info; the service normalises all datetimes to UTC before comparison.
- **Partial payments** — balances are computed from actual payment sums, not just invoice status.
- **External API failures** — sync continues for other entities and reports errors in the response.
- **Idempotent sync** — running sync multiple times doesn't create duplicates.
- **Missing customers** — overdue report gracefully shows "Unknown" if a customer record is missing.

### What I'd Add With More Time

- **Pagination** on list endpoints.
- **Incremental sync** using `synced_at` timestamps to fetch only changed records.
- **Webhook receiver** to get push notifications from the external system instead of polling.
- **PostgreSQL** for production with proper migrations (Alembic).
- **Authentication** (API key or JWT) on the insight endpoints.
- **Rate limiting** on outbound API calls to the external system.
