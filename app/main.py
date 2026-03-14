"""
Takaada Receivables Service
----------------------------
Integrates with an external accounting system, stores data locally,
and exposes credit-insight APIs.
"""
import logging

from fastapi import APIRouter, FastAPI
from contextlib import asynccontextmanager

from app.database import Base, engine
from app.api import sync, customers, invoices, insights, webhooks

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Takaada Receivables Service",
    description="Syncs with an external accounting system and provides "
                "credit insights, overdue tracking, and aging reports.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── All business routes live under /api/v1 ──
v1 = APIRouter(prefix="/api/v1")
v1.include_router(sync.router)
v1.include_router(customers.router)
v1.include_router(invoices.router)
v1.include_router(insights.router)
v1.include_router(webhooks.router)
app.include_router(v1)


@app.get("/health")
def health():
    return {"status": "ok"}
