"""
Takaada Receivables Service
----------------------------
Integrates with an external accounting system, stores data locally,
and exposes credit-insight APIs.
"""
import logging

from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.database import Base, engine
from app.api import sync, customers, invoices, insights

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Takaada Receivables Service",
    description="Syncs with an external accounting system and provides "
                "credit insights, overdue tracking, and aging reports.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(sync.router)
app.include_router(customers.router)
app.include_router(invoices.router)
app.include_router(insights.router)


@app.get("/health")
def health():
    return {"status": "ok"}
