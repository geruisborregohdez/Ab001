import re
import pytest
from unittest.mock import AsyncMock, patch

from app.agent.tools import (
    tool_create_customer,
    tool_list_customers,
    tool_get_customer,
    tool_update_customer,
    tool_create_service,
    tool_list_services,
    tool_complete_service,
    tool_update_service,
    tool_create_invoice,
    tool_list_invoices,
    tool_send_invoice_to_quickbooks,
)


CUSTOMER_FIELDS = {
    "name": "Tool Test Co",
    "email": "tools@example.com",
    "phone": "555-0200",
    "address_street": "200 Elm St",
    "address_city": "Shelbyville",
    "address_state": "IL",
    "address_zip": "62565",
}


async def test_tool_create_customer(db_session):
    result = await tool_create_customer(db=db_session, **CUSTOMER_FIELDS)
    assert result["name"] == "Tool Test Co"
    assert "id" in result


async def test_tool_list_customers(db_session):
    await tool_create_customer(db=db_session, **CUSTOMER_FIELDS)
    results = await tool_list_customers(db=db_session)
    assert isinstance(results, list)
    assert len(results) >= 1


async def test_tool_list_customers_search(db_session):
    await tool_create_customer(db=db_session, **CUSTOMER_FIELDS)
    results = await tool_list_customers(db=db_session, search="Tool Test")
    assert any(c["name"] == "Tool Test Co" for c in results)


async def test_tool_get_customer(db_session):
    created = await tool_create_customer(db=db_session, **CUSTOMER_FIELDS)
    result = await tool_get_customer(db=db_session, customer_id=created["id"])
    assert result["id"] == created["id"]


async def test_tool_get_customer_not_found(db_session):
    result = await tool_get_customer(db=db_session, customer_id=99999)
    assert "not found" in result


async def test_tool_update_customer(db_session):
    created = await tool_create_customer(db=db_session, **CUSTOMER_FIELDS)
    result = await tool_update_customer(db=db_session, customer_id=created["id"], phone="555-9999")
    assert result["phone"] == "555-9999"


async def test_tool_create_service(db_session):
    customer = await tool_create_customer(db=db_session, **CUSTOMER_FIELDS)
    result = await tool_create_service(
        db=db_session,
        customer_id=customer["id"],
        name="Electrical Work",
        cost=60.0,
        price=130.0,
    )
    assert result["name"] == "Electrical Work"
    assert result["status"] == "pending"


async def test_tool_list_services(db_session):
    customer = await tool_create_customer(db=db_session, **CUSTOMER_FIELDS)
    await tool_create_service(
        db=db_session, customer_id=customer["id"], name="Svc1", cost=10.0, price=20.0
    )
    results = await tool_list_services(db=db_session, customer_id=customer["id"])
    assert len(results) >= 1
    assert all(s["customer_id"] == customer["id"] for s in results)


async def test_tool_complete_service(db_session):
    customer = await tool_create_customer(db=db_session, **CUSTOMER_FIELDS)
    service = await tool_create_service(
        db=db_session, customer_id=customer["id"], name="Svc2", cost=10.0, price=20.0
    )
    result = await tool_complete_service(db=db_session, service_id=service["id"])
    assert result["status"] == "completed"
    assert result["completed_date"] is not None


async def test_tool_complete_service_not_found(db_session):
    result = await tool_complete_service(db=db_session, service_id=99999)
    assert "not found" in result


async def test_tool_update_service(db_session):
    customer = await tool_create_customer(db=db_session, **CUSTOMER_FIELDS)
    service = await tool_create_service(
        db=db_session, customer_id=customer["id"], name="Svc3", cost=10.0, price=20.0
    )
    result = await tool_update_service(
        db=db_session, service_id=service["id"], description="Now with description"
    )
    assert result["description"] == "Now with description"


async def test_tool_create_invoice(db_session):
    customer = await tool_create_customer(db=db_session, **CUSTOMER_FIELDS)
    service = await tool_create_service(
        db=db_session, customer_id=customer["id"], name="Svc4", cost=30.0, price=90.0
    )
    await tool_complete_service(db=db_session, service_id=service["id"])
    result = await tool_create_invoice(
        db=db_session, customer_id=customer["id"], service_ids=[service["id"]]
    )
    assert re.match(r"INV-\d+", result["invoice_number"])
    assert float(result["total_amount"]) == 90.0


async def test_tool_list_invoices(db_session):
    customer = await tool_create_customer(db=db_session, **CUSTOMER_FIELDS)
    service = await tool_create_service(
        db=db_session, customer_id=customer["id"], name="Svc5", cost=30.0, price=90.0
    )
    await tool_complete_service(db=db_session, service_id=service["id"])
    await tool_create_invoice(
        db=db_session, customer_id=customer["id"], service_ids=[service["id"]]
    )
    results = await tool_list_invoices(db=db_session)
    assert len(results) >= 1


async def test_tool_send_invoice_to_quickbooks(db_session):
    customer = await tool_create_customer(db=db_session, **CUSTOMER_FIELDS)
    service = await tool_create_service(
        db=db_session, customer_id=customer["id"], name="Svc6", cost=30.0, price=90.0
    )
    await tool_complete_service(db=db_session, service_id=service["id"])
    invoice = await tool_create_invoice(
        db=db_session, customer_id=customer["id"], service_ids=[service["id"]]
    )

    mock_qb = AsyncMock()
    mock_qb.create_invoice.return_value = {
        "qb_invoice_id": "QB-TOOL0001",
        "status": "created",
        "invoice_number": invoice["invoice_number"],
    }
    with patch("app.agent.tools.get_quickbooks_client", return_value=mock_qb):
        result = await tool_send_invoice_to_quickbooks(db=db_session, invoice_id=invoice["id"])

    assert result["qb_invoice_id"] == "QB-TOOL0001"
    assert "invoice" in result
    mock_qb.create_invoice.assert_called_once()
