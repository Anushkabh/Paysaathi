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

# 5. Trigger initial data sync (full pull)
curl -X POST "http://localhost:8000/api/v1/sync/?strategy=full"

# 6. Explore the interactive API docs
open http://localhost:8000/docs
```



## API Reference

All business endpoints are under `/api/v1/`.

### Sync

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/sync/?strategy=full` | Pull all data from external system |
| POST | `/api/v1/sync/?strategy=incremental` | Pull only changes since last successful sync |

### Webhooks

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/webhooks/accounting` | Receive push events from external system |

**Required header:** `X-Webhook-Secret: <secret>`

**Payload example:**
```json
{
  "event": "payment.received",
  "entity_type": "payment",
  "entity_id": "PAY-007",
  "timestamp": "2025-06-01T12:00:00Z"
}
```

### Insights

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/insights/balances` | Outstanding balance per customer |
| GET | `/api/v1/insights/overdue` | All overdue invoices (sorted by severity) |
| GET | `/api/v1/insights/aging` | AR aging buckets (0-30, 31-60, 61-90, 90+ days) |
| GET | `/api/v1/insights/credit-report/{customer_id}` | Full credit risk report for a customer |

### Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/customers/` | List all customers |
| GET | `/api/v1/customers/{id}` | Get one customer |
| GET | `/api/v1/invoices/?customer_id=&status=` | List invoices (filterable) |

### Other

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check (not versioned) |

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
│   │   ├── sync.py           # POST /api/v1/sync
│   │   ├── webhooks.py       # POST /api/v1/webhooks/accounting
│   │   ├── customers.py      # GET  /api/v1/customers
│   │   ├── invoices.py       # GET  /api/v1/invoices
│   │   └── insights.py       # GET  /api/v1/insights/*
│   ├── external/
│   │   └── accounting_client.py  # HTTP client with retry + backoff
│   ├── models/               # SQLAlchemy ORM models
│   │   ├── customer.py
│   │   ├── invoice.py
│   │   ├── payment.py
│   │   └── sync_log.py       # Audit log for sync runs
│   ├── schemas/              # Pydantic request/response schemas
│   │   ├── schemas.py
│   │   └── webhook.py
│   ├── services/
│   │   ├── sync_service.py    # Sync orchestration (full/incremental/targeted)
│   │   └── insights_service.py  # Financial insight computations
│   ├── config.py
│   ├── database.py
│   └── main.py
├── mock_server/              # Simulated external accounting API
│   └── server.py
├── tests/
│   ├── conftest.py
│   ├── test_sync.py
│   ├── test_insights.py
│   └── test_webhooks.py
```

### Layered Architecture

```
API Routes  →  Services  →  Models / External Client
   (thin)       (logic)       (data access)
```

- **API layer** is thin — validates input, calls a service, returns the response.
- **Service layer** holds all business logic (sync orchestration, insight calculations, risk scoring).
- **External client** isolates all HTTP calls behind a clean interface with retry + exponential backoff.

### Database Schema

```
customers
  ├── id (PK, string)         — matches external system ID
  ├── name, email, phone
  ├── credit_limit
  ├── created_at, updated_at
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

sync_logs                      — audit trail for every sync run
  ├── id (PK, auto)
  ├── trigger (manual | webhook:* | scheduled)
  ├── status (success | partial | failed)
  ├── customers/invoices/payments_synced
  ├── errors, duration_ms
  └── started_at, completed_at
```

**Key decisions:**
- **External IDs as primary keys** — avoids a separate mapping table and makes upsert logic straightforward.
- **`synced_at` on every table** — enables incremental sync and debugging stale data.
- **`sync_logs` table** — provides an audit trail: who triggered it, what was synced, how long it took, and what failed.
- **Status recomputed after sync** — the service recalculates invoice statuses from actual payment totals, so we don't blindly trust the external system's status field.

---

## Sync Strategy (Production-Ready)

The service supports three sync modes:

### 1. Full Sync (`POST /api/v1/sync/?strategy=full`)
Fetches all customers, invoices, and payments from the external API and upserts them. Safe to run anytime — it's idempotent.

### 2. Incremental Sync (`POST /api/v1/sync/?strategy=incremental`)
Uses the `completed_at` timestamp from the last successful sync (stored in `sync_logs`) to request only records updated since then. Falls back to full sync if no prior sync exists.

### 3. Webhook-Triggered Sync (`POST /api/v1/webhooks/accounting`)
When the external system pushes an event (e.g. `payment.received`), the webhook receiver immediately re-syncs the affected entity type. This gives near-real-time data freshness without polling.

### Resilience Features

| Feature | How |
|---|---|
| **Retry with exponential backoff** | HTTP client retries 5xx/network errors up to 3 times (1s → 2s → 4s) |
| **No retry on 4xx** | Client errors are not retried — they won't fix themselves |
| **Partial failure handling** | If customers fail but invoices/payments succeed, the sync reports `partial` status and logs the error |
| **Webhook authentication** | `X-Webhook-Secret` header is validated before processing |
| **Audit logging** | Every sync run (manual, webhook, or scheduled) is logged with trigger source, counts, errors, and duration |
| **Idempotent upserts** | Running sync twice produces the same result — no duplicates |
| **Status recomputation** | Invoice statuses are derived from actual payment totals, not trusted from the external API |

### Recommended Production Setup

```
┌──────────────────────┐     webhook push      ┌──────────────────────┐
│  External Accounting │ ──────────────────────→│  Takaada Service     │
│  System              │                        │                      │
│                      │←── incremental pull ───│  Scheduled job runs  │
│                      │    (every 30 min)      │  incremental sync    │
└──────────────────────┘                        └──────────────────────┘
```

- **Primary**: Webhooks for real-time updates
- **Safety net**: Scheduled incremental sync every 30 minutes catches anything webhooks missed
- **Recovery**: Manual full sync available for first-time setup or disaster recovery

---

## Insight APIs

### Outstanding Balances (`GET /api/v1/insights/balances`)
Per-customer breakdown of total invoiced vs total paid, with credit utilization percentage.

### Overdue Invoices (`GET /api/v1/insights/overdue`)
All invoices past due date, sorted by days overdue. Shows partial payment info.

### Aging Report (`GET /api/v1/insights/aging`)
Accounts receivable aging in 4 buckets: 0-30, 31-60, 61-90, and 90+ days.

### Credit Report (`GET /api/v1/insights/credit-report/{customer_id}`)
Full credit profile for a single customer including:
- Outstanding balance and overdue amount
- Average days to pay (from payment history)
- Per-customer aging breakdown
- **Risk level** (LOW / MEDIUM / HIGH)

### Risk Scoring Logic

A point-based system:
- Credit utilization > 80% → +2 pts, > 50% → +1 pt
- 3+ overdue invoices → +2 pts, 1+ → +1 pt
- Average days to pay > 60 → +1 pt

Score ≥ 3 = **HIGH**, ≥ 2 = **MEDIUM**, else **LOW**.

---

## Assumptions

1. **External API returns all records in a single response** — no pagination needed on the outbound side. In production, I'd add cursor-based pagination to the client.
2. **External system IDs are globally unique and stable** — safe to use as primary keys. If they could change, I'd add a local surrogate key with a mapping table.
3. **Webhook events may be delivered out of order or duplicated** — the upsert logic and status recomputation make this safe (idempotent by design).
4. **Invoice amounts are immutable after creation** — partial payments reduce the balance, but the invoice `amount` stays the same. The external system doesn't modify invoice amounts after issuance.
5. **All monetary values are in a single currency** — no currency conversion logic. In a multi-currency system, I'd store currency codes alongside amounts.
6. **The external API is the source of truth** — on conflict, external data wins. Local data is a read-optimised mirror, not an independent ledger.
7. **SQLite is acceptable for this exercise** — in production, I'd use PostgreSQL. The `DATABASE_URL` env var makes swapping trivial.

---

## Edge Cases Handled

- **Timezone-naive datetimes** — SQLite strips timezone info; all datetimes normalised to UTC before comparison.
- **Partial payments** — balances computed from actual payment sums, not just invoice status.
- **External API failures** — sync continues for other entities and reports errors in response.
- **Idempotent sync** — running sync multiple times doesn't create duplicates.
- **Webhook replay safety** — upsert logic means replayed webhooks are harmless.
- **Missing customers** — overdue report gracefully shows "Unknown" if a customer record is missing.

## What I'd Add With More Time

- **Pagination** on list endpoints.
- **HMAC signature verification** for webhook payloads (currently uses shared secret header).
- **Background task queue** (Celery/ARQ) for webhook processing to avoid blocking the HTTP response.
- **PostgreSQL** with Alembic migrations for production.
- **Authentication** (API key or JWT) on the insight endpoints.
- **Rate limiting** on outbound API calls to the external system.
- **Metrics/observability** — Prometheus counters for sync success/failure rates.
