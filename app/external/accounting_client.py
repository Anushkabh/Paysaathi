"""
HTTP client for the external accounting system.

Centralises all outbound API calls so retry logic, auth headers, and
error handling live in one place.
"""
import httpx
import logging

from app.config import settings
from app.schemas.schemas import ExternalCustomer, ExternalInvoice, ExternalPayment

logger = logging.getLogger(__name__)

TIMEOUT = 10.0  # seconds


class AccountingAPIError(Exception):
    """Raised when the external API returns an unexpected response."""


class AccountingClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.EXTERNAL_API_BASE_URL).rstrip("/")

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        try:
            resp = httpx.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("API %s returned %s", url, exc.response.status_code)
            raise AccountingAPIError(
                f"{url} responded with {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            logger.error("Failed to reach %s: %s", url, exc)
            raise AccountingAPIError(f"Cannot reach {url}") from exc

    # ── Public methods ──

    def fetch_customers(self) -> list[ExternalCustomer]:
        data = self._get("/api/customers")
        return [ExternalCustomer(**c) for c in data["data"]]

    def fetch_invoices(self, customer_id: str | None = None) -> list[ExternalInvoice]:
        params = {"customer_id": customer_id} if customer_id else None
        data = self._get("/api/invoices", params=params)
        return [ExternalInvoice(**i) for i in data["data"]]

    def fetch_payments(self, invoice_id: str | None = None) -> list[ExternalPayment]:
        params = {"invoice_id": invoice_id} if invoice_id else None
        data = self._get("/api/payments", params=params)
        return [ExternalPayment(**p) for p in data["data"]]
