"""
QuickBooks integration.

POC: StubQuickBooksClient returns mock responses.
Production: Set QB_MODE=real and fill in QB_* env vars. RealQuickBooksClient uses
  intuitlib (OAuth2 token refresh) + python-quickbooks (QB API).

Required env vars when QB_MODE=real:
  QB_CLIENT_ID, QB_CLIENT_SECRET, QB_REFRESH_TOKEN, QB_REALM_ID
Optional:
  QB_ACCESS_TOKEN   — pre-seeded access token (auto-refreshed if expired)
  QB_DEFAULT_ITEM_REF — QB Item ID for line items (default: "1" = Services)
  QB_ENVIRONMENT    — "sandbox" or "production" (default: "sandbox")
"""
import asyncio
import logging
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

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


class RealQuickBooksClient(QuickBooksClient):
    """
    Real QuickBooks integration via intuitlib + python-quickbooks.

    Tokens are read from env vars at construction time. The access token is
    auto-refreshed (using the refresh token) whenever it is expired or about
    to expire. All synchronous python-quickbooks calls are offloaded to a
    thread executor to avoid blocking the async event loop.
    """

    def __init__(self):
        from intuitlib.client import AuthClient

        self._client_id = os.environ["QB_CLIENT_ID"]
        self._client_secret = os.environ["QB_CLIENT_SECRET"]
        self._realm_id = os.environ["QB_REALM_ID"]
        self._default_item_ref = os.getenv("QB_DEFAULT_ITEM_REF", "1")
        environment = os.getenv("QB_ENVIRONMENT", "sandbox")

        self._auth_client = AuthClient(
            client_id=self._client_id,
            client_secret=self._client_secret,
            redirect_uri="http://localhost",  # required by intuitlib; unused here
            environment=environment,
            access_token=os.getenv("QB_ACCESS_TOKEN", ""),
            refresh_token=os.environ["QB_REFRESH_TOKEN"],
        )
        # Track when the access token expires (None = unknown, refresh on first use)
        self._token_expiry: datetime | None = None

    async def _ensure_valid_token(self) -> None:
        """Refresh the access token if it has expired or is about to expire."""
        now = datetime.now(timezone.utc)
        if self._token_expiry is None or now >= self._token_expiry:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._auth_client.refresh)
            # QB access tokens live 3600s; use 55 min to stay safe
            self._token_expiry = datetime.now(timezone.utc) + timedelta(minutes=55)
            logger.info("[QB] Access token refreshed; next refresh in ~55 min")

    def _get_qb_session(self):
        """Return a configured python-quickbooks QuickBooks session."""
        from quickbooks import QuickBooks

        return QuickBooks(
            auth_client=self._auth_client,
            # Always read from auth_client to pick up any rotated refresh token
            refresh_token=self._auth_client.refresh_token,
            company_id=self._realm_id,
        )

    async def sync_customer(self, customer) -> dict:
        """
        Create or update a customer in QuickBooks.
        Looks up by DisplayName first; creates if not found.
        Returns {"qb_customer_id": str, "status": "synced"|"created"}.
        """
        from quickbooks.objects.customer import Customer as QBCustomer

        await self._ensure_valid_token()
        loop = asyncio.get_event_loop()

        def _sync():
            qb = self._get_qb_session()

            # Look up existing customer by DisplayName
            existing = QBCustomer.filter(DisplayName=customer.name, qb=qb)
            if existing:
                logger.info("[QB] sync_customer | found existing | DisplayName=%s | Id=%s", customer.name, existing[0].Id)
                return {"qb_customer_id": str(existing[0].Id), "status": "synced"}

            # Create new QB customer
            qb_customer = QBCustomer()
            qb_customer.DisplayName = customer.name

            if customer.email:
                from quickbooks.objects.base import EmailAddress
                email = EmailAddress()
                email.Address = customer.email
                qb_customer.PrimaryEmailAddr = email

            if customer.phone:
                from quickbooks.objects.base import PhoneNumber
                phone = PhoneNumber()
                phone.FreeFormNumber = customer.phone
                qb_customer.PrimaryPhone = phone

            if any([customer.address_street, customer.address_city, customer.address_state, customer.address_zip]):
                from quickbooks.objects.base import Address
                addr = Address()
                addr.Line1 = customer.address_street or ""
                addr.City = customer.address_city or ""
                addr.CountrySubDivisionCode = customer.address_state or ""
                addr.PostalCode = customer.address_zip or ""
                qb_customer.BillAddr = addr

            qb_customer.save(qb=qb)
            logger.info("[QB] sync_customer | created | DisplayName=%s | Id=%s", customer.name, qb_customer.Id)
            return {"qb_customer_id": str(qb_customer.Id), "status": "created"}

        return await loop.run_in_executor(None, _sync)

    async def create_invoice(self, invoice) -> dict:
        """
        Push an invoice to QuickBooks.
        Auto-syncs the customer to QB if not already there.
        Returns {"qb_invoice_id": str, "status": "created", "invoice_number": str}.
        """
        from quickbooks.objects.invoice import Invoice as QBInvoice
        from quickbooks.objects.detailline import SalesItemLine, SalesItemLineDetail
        from quickbooks.objects.item import Item

        await self._ensure_valid_token()

        # Auto-sync the customer; use the returned QB customer ID for this invoice
        customer_result = await self.sync_customer(invoice.customer)
        qb_customer_id = customer_result["qb_customer_id"]

        loop = asyncio.get_event_loop()

        def _create():
            qb = self._get_qb_session()

            qb_invoice = QBInvoice()
            qb_invoice.DocNumber = invoice.invoice_number
            qb_invoice.CustomerRef = {"value": qb_customer_id}

            lines = []
            for item in invoice.line_items:
                line = SalesItemLine()
                line.Amount = float(item.amount)
                line.Description = item.description

                detail = SalesItemLineDetail()
                detail.UnitPrice = float(item.unit_price)
                detail.ItemRef = {"value": self._default_item_ref}
                line.SalesItemLineDetail = detail

                lines.append(line)

            qb_invoice.Line = lines
            qb_invoice.save(qb=qb)

            logger.info(
                "[QB] create_invoice | invoice_number=%s | qb_id=%s | customer_qb_id=%s",
                invoice.invoice_number,
                qb_invoice.Id,
                qb_customer_id,
            )
            return {
                "qb_invoice_id": str(qb_invoice.Id),
                "status": "created",
                "invoice_number": invoice.invoice_number,
            }

        return await loop.run_in_executor(None, _create)

    async def update_invoice(self, qb_invoice_id: str, invoice) -> dict:
        """
        Update an existing QB invoice with fresh line items and amounts.
        Returns {"qb_invoice_id": str, "status": "updated"}.
        """
        from quickbooks.objects.invoice import Invoice as QBInvoice
        from quickbooks.objects.detailline import SalesItemLine, SalesItemLineDetail

        await self._ensure_valid_token()
        loop = asyncio.get_event_loop()

        def _update():
            qb = self._get_qb_session()

            qb_invoice = QBInvoice.get(int(qb_invoice_id), qb=qb)

            lines = []
            for item in invoice.line_items:
                line = SalesItemLine()
                line.Amount = float(item.amount)
                line.Description = item.description

                detail = SalesItemLineDetail()
                detail.UnitPrice = float(item.unit_price)
                detail.ItemRef = {"value": self._default_item_ref}
                line.SalesItemLineDetail = detail

                lines.append(line)

            qb_invoice.Line = lines
            qb_invoice.save(qb=qb)

            logger.info("[QB] update_invoice | qb_id=%s", qb_invoice_id)
            return {"qb_invoice_id": qb_invoice_id, "status": "updated"}

        return await loop.run_in_executor(None, _update)


def get_quickbooks_client() -> QuickBooksClient:
    mode = os.getenv("QB_MODE", "stub").lower()
    if mode == "real":
        return RealQuickBooksClient()
    return StubQuickBooksClient()
