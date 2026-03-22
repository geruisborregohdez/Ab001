import re
import pytest
from unittest.mock import AsyncMock, patch


async def test_create_invoice_returns_201(client, sample_invoice):
    assert sample_invoice is not None
    assert re.match(r"INV-\d+", sample_invoice["invoice_number"])
    assert "id" in sample_invoice
    assert "total_amount" in sample_invoice


async def test_create_invoice_total_matches_service_price(client, sample_invoice, completed_service):
    assert float(sample_invoice["total_amount"]) == float(completed_service["price"])


async def test_create_invoice_includes_line_items(client, sample_invoice):
    assert len(sample_invoice["line_items"]) == 1
    item = sample_invoice["line_items"][0]
    assert "description" in item
    assert "unit_price" in item
    assert "amount" in item


async def test_list_invoices(client, sample_invoice):
    resp = await client.get("/api/invoices")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    ids = [i["id"] for i in data]
    assert sample_invoice["id"] in ids


async def test_list_invoices_filter_by_status(client, sample_invoice):
    resp = await client.get("/api/invoices", params={"status": "draft"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(i["status"] == "draft" for i in data)


async def test_get_invoice_by_id(client, sample_invoice):
    resp = await client.get(f"/api/invoices/{sample_invoice['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == sample_invoice["id"]
    assert "line_items" in data


async def test_get_invoice_not_found(client):
    resp = await client.get("/api/invoices/99999")
    assert resp.status_code == 404


async def test_update_invoice_status(client, sample_invoice):
    resp = await client.patch(
        f"/api/invoices/{sample_invoice['id']}/status",
        json={"status": "paid"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "paid"


async def test_send_invoice_to_quickbooks(client, sample_invoice):
    mock_qb = AsyncMock()
    mock_qb.create_invoice.return_value = {
        "qb_invoice_id": "QB-TESTID01",
        "status": "created",
        "invoice_number": sample_invoice["invoice_number"],
    }
    with patch("app.api.invoices.get_quickbooks_client", return_value=mock_qb):
        resp = await client.post(f"/api/invoices/{sample_invoice['id']}/send-to-quickbooks")

    assert resp.status_code == 200
    data = resp.json()
    assert data["quickbooks_invoice_id"] == "QB-TESTID01"
    mock_qb.create_invoice.assert_called_once()


async def test_send_invoice_to_quickbooks_not_found(client):
    resp = await client.post("/api/invoices/99999/send-to-quickbooks")
    assert resp.status_code == 404


async def test_send_invoice_to_quickbooks_duplicate_returns_409(client, sample_invoice):
    mock_qb = AsyncMock()
    mock_qb.create_invoice.return_value = {
        "qb_invoice_id": "QB-TESTID02",
        "status": "created",
        "invoice_number": sample_invoice["invoice_number"],
    }
    with patch("app.api.invoices.get_quickbooks_client", return_value=mock_qb):
        await client.post(f"/api/invoices/{sample_invoice['id']}/send-to-quickbooks")
        resp = await client.post(f"/api/invoices/{sample_invoice['id']}/send-to-quickbooks")

    assert resp.status_code == 409
    assert "already sent" in resp.json()["detail"].lower()


async def test_update_invoice_status_not_found(client):
    resp = await client.patch("/api/invoices/99999/status", json={"status": "paid"})
    assert resp.status_code == 404
