import re
import os
import pytest
from unittest.mock import MagicMock

from app.integrations.quickbooks import StubQuickBooksClient, get_quickbooks_client


class TestStubQuickBooksClient:
    @pytest.fixture
    def client(self):
        return StubQuickBooksClient()

    @pytest.fixture
    def mock_invoice(self):
        inv = MagicMock()
        inv.invoice_number = "INV-0001"
        inv.total_amount = "150.00"
        return inv

    @pytest.fixture
    def mock_customer(self):
        cust = MagicMock()
        cust.name = "Test Co"
        return cust

    async def test_create_invoice_returns_qb_invoice_id(self, client, mock_invoice):
        result = await client.create_invoice(mock_invoice)
        assert "qb_invoice_id" in result
        assert re.match(r"QB-[A-F0-9]{8}", result["qb_invoice_id"])

    async def test_create_invoice_status_is_created(self, client, mock_invoice):
        result = await client.create_invoice(mock_invoice)
        assert result["status"] == "created"

    async def test_create_invoice_includes_invoice_number(self, client, mock_invoice):
        result = await client.create_invoice(mock_invoice)
        assert result["invoice_number"] == "INV-0001"

    async def test_sync_customer_returns_qb_customer_id(self, client, mock_customer):
        result = await client.sync_customer(mock_customer)
        assert "qb_customer_id" in result
        assert re.match(r"QB-CUST-[A-F0-9]{6}", result["qb_customer_id"])

    async def test_sync_customer_status_is_synced(self, client, mock_customer):
        result = await client.sync_customer(mock_customer)
        assert result["status"] == "synced"

    async def test_each_call_returns_unique_id(self, client, mock_invoice):
        r1 = await client.create_invoice(mock_invoice)
        r2 = await client.create_invoice(mock_invoice)
        assert r1["qb_invoice_id"] != r2["qb_invoice_id"]


class TestGetQuickBooksClient:
    def test_returns_stub_when_no_env(self, monkeypatch):
        monkeypatch.delenv("QB_MODE", raising=False)
        c = get_quickbooks_client()
        assert isinstance(c, StubQuickBooksClient)

    def test_returns_stub_when_stub_mode(self, monkeypatch):
        monkeypatch.setenv("QB_MODE", "stub")
        c = get_quickbooks_client()
        assert isinstance(c, StubQuickBooksClient)

    def test_returns_real_client_when_real_mode(self, monkeypatch):
        from unittest.mock import patch
        from app.integrations.quickbooks import RealQuickBooksClient
        monkeypatch.setenv("QB_MODE", "real")
        with patch.object(RealQuickBooksClient, "__init__", return_value=None):
            c = get_quickbooks_client()
        assert isinstance(c, RealQuickBooksClient)
