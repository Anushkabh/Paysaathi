"""
HTTP client for the external accounting system.

Centralises all outbound API calls so retry logic, auth headers, and
error handling live in one place.
"""
import httpx
import logging
import time

from app.config import settings
from app.schemas.schemas import ExternalCustomer, ExternalInvoice, ExternalPayment

logger = logging.getLogger(__name__)

TIMEOUT = 10.0  # seconds


class AccountingAPIError(Exception):
    """Raised when the external API returns an unexpected response."""


class AccountingClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.EXTERNAL_API_BASE_URL).rstrip("/")
        self.max_retries = settings.MAX_RETRY_ATTEMPTS
        self.backoff = settings.RETRY_BACKOFF_SECONDS

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        last_exc = None

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = httpx.get(url, params=params, timeout=TIMEOUT)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                # Don't retry client errors (4xx) — they won't fix themselves
                if 400 <= status < 500:
                    logger.error("API %s returned %s (not retryable)", url, status)
                    raise AccountingAPIError(
                        f"{url} responded with {status}"
                    ) from exc
                logger.warning(
                    "API %s returned %s (attempt %d/%d)",
                    url, status, attempt, self.max_retries,
                )
                last_exc = exc
            except httpx.RequestError as exc:
                logger.warning(
                    "Failed to reach %s (attempt %d/%d): %s",
                    url, attempt, self.max_retries, exc,
                )
                last_exc = exc

            if attempt < self.max_retries:
                wait = self.backoff * (2 ** (attempt - 1))  # exponential backoff
                logger.info("Retrying in %.1fs...", wait)
                time.sleep(wait)

        raise AccountingAPIError(f"Failed after {self.max_retries} attempts: {url}") from last_exc

    # ── Public methods ──

    def fetch_customers(self, since: str | None = None) -> list[ExternalCustomer]:
        params = {"updated_since": since} if since else None
        data = self._get("/api/customers", params=params)
        return [ExternalCustomer(**c) for c in data["data"]]

    def fetch_invoices(self, customer_id: str | None = None,
                       since: str | None = None) -> list[ExternalInvoice]:
        params = {}
        if customer_id:
            params["customer_id"] = customer_id
        if since:
            params["updated_since"] = since
        data = self._get("/api/invoices", params=params or None)
        return [ExternalInvoice(**i) for i in data["data"]]

    def fetch_payments(self, invoice_id: str | None = None,
                       since: str | None = None) -> list[ExternalPayment]:
        params = {}
        if invoice_id:
            params["invoice_id"] = invoice_id
        if since:
            params["updated_since"] = since
        data = self._get("/api/payments", params=params or None)
        return [ExternalPayment(**p) for p in data["data"]]
