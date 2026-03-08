"""
QuickBooks integration.

POC: StubQuickBooksClient returns mock responses.
Production: Set QB_MODE=real and implement RealQuickBooksClient using
  the intuit-oauth + python-quickbooks packages, then wire it below.
"""
import logging
import os
import uuid
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class QuickBooksClient(ABC):
    @abstractmethod
    async def create_invoice(self, invoice) -> dict:
        """Push an invoice to QuickBooks. Returns dict with 'qb_invoice_id'."""

    @abstractmethod
    async def update_invoice(self, qb_invoice_id: str, invoice) -> dict:
        """Update an existing QB invoice."""

    @abstractmethod
    async def sync_customer(self, customer) -> dict:
        """Create or update a customer in QuickBooks."""


class StubQuickBooksClient(QuickBooksClient):
    """Logs calls and returns mock QuickBooks responses. Replace with RealQuickBooksClient."""

    async def create_invoice(self, invoice) -> dict:
        mock_id = f"QB-{uuid.uuid4().hex[:8].upper()}"
        logger.info(
            "[QB STUB] create_invoice | invoice_number=%s | total=%s | mock_qb_id=%s",
            invoice.invoice_number,
            invoice.total_amount,
            mock_id,
        )
        return {
            "qb_invoice_id": mock_id,
            "status": "created",
            "invoice_number": invoice.invoice_number,
        }

    async def update_invoice(self, qb_invoice_id: str, invoice) -> dict:
        logger.info("[QB STUB] update_invoice | qb_id=%s", qb_invoice_id)
        return {"qb_invoice_id": qb_invoice_id, "status": "updated"}

    async def sync_customer(self, customer) -> dict:
        mock_id = f"QB-CUST-{uuid.uuid4().hex[:6].upper()}"
        logger.info("[QB STUB] sync_customer | name=%s | mock_qb_id=%s", customer.name, mock_id)
        return {"qb_customer_id": mock_id, "status": "synced"}


# --- Swap here when going to production ---
# class RealQuickBooksClient(QuickBooksClient):
#     def __init__(self, client_id: str, client_secret: str, refresh_token: str, realm_id: str):
#         ...
#
#     async def create_invoice(self, invoice) -> dict:
#         # Use python-quickbooks to push invoice
#         ...


def get_quickbooks_client() -> QuickBooksClient:
    mode = os.getenv("QB_MODE", "stub").lower()
    if mode == "real":
        raise NotImplementedError("RealQuickBooksClient not yet implemented. Set QB_MODE=stub.")
    return StubQuickBooksClient()
