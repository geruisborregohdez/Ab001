"""
Shared tool functions — used by both the Claude agent and the MCP server.

All functions are async and receive a db session via dependency injection.
The tool registry at the bottom maps tool names → callables for the agent loop.
"""
import json
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ServiceStatus, InvoiceStatus
from app.db.repositories.customer_repo import CustomerRepository
from app.db.repositories.service_repo import ServiceRepository
from app.db.repositories.invoice_repo import InvoiceRepository
from app.integrations.quickbooks import get_quickbooks_client
from app.schemas.customer import CustomerRead
from app.schemas.service import ServiceRead
from app.schemas.invoice import InvoiceRead


def _serialize(obj) -> dict:
    """Convert SQLAlchemy model to JSON-serializable dict via Pydantic."""
    if isinstance(obj, list):
        return [_serialize(o) for o in obj]
    return json.loads(obj.model_dump_json()) if hasattr(obj, "model_dump_json") else obj


# ── Customer tools ──────────────────────────────────────────────────────────

async def tool_create_customer(db: AsyncSession, name: str, email: str,
                                phone: str, address_street: str, address_city: str,
                                address_state: str, address_zip: str) -> dict:
    repo = CustomerRepository(db)
    customer = await repo.create(
        name=name, email=email, phone=phone,
        address_street=address_street, address_city=address_city,
        address_state=address_state, address_zip=address_zip,
    )
    return _serialize(CustomerRead.model_validate(customer))


async def tool_list_customers(db: AsyncSession, search: str | None = None, limit: int = 50) -> list:
    repo = CustomerRepository(db)
    customers = await repo.list(search=search, limit=limit)
    return _serialize([CustomerRead.model_validate(c) for c in customers])


async def tool_get_customer(db: AsyncSession, customer_id: int) -> dict | str:
    repo = CustomerRepository(db)
    customer = await repo.get(customer_id)
    if not customer:
        return f"Customer {customer_id} not found."
    return _serialize(CustomerRead.model_validate(customer))


async def tool_update_customer(db: AsyncSession, customer_id: int, **fields) -> dict | str:
    repo = CustomerRepository(db)
    customer = await repo.update(customer_id, **fields)
    if not customer:
        return f"Customer {customer_id} not found."
    return _serialize(CustomerRead.model_validate(customer))


# ── Service tools ────────────────────────────────────────────────────────────

async def tool_create_service(db: AsyncSession, customer_id: int, name: str,
                               cost: float, price: float, description: str | None = None,
                               service_date: str | None = None) -> dict | str:
    repo = ServiceRepository(db)
    parsed_date = datetime.fromisoformat(service_date) if service_date else None
    service = await repo.create(
        customer_id=customer_id, name=name, description=description,
        cost=cost, price=price, service_date=parsed_date,
    )
    return _serialize(ServiceRead.model_validate(service))


async def tool_list_services(db: AsyncSession, customer_id: int | None = None,
                              status: str | None = None, limit: int = 100) -> list:
    repo = ServiceRepository(db)
    svc_status = ServiceStatus(status) if status else None
    services = await repo.list(customer_id=customer_id, status=svc_status, limit=limit)
    return _serialize([ServiceRead.model_validate(s) for s in services])


async def tool_complete_service(db: AsyncSession, service_id: int) -> dict | str:
    repo = ServiceRepository(db)
    service = await repo.complete(service_id)
    if not service:
        return f"Service {service_id} not found."
    return _serialize(ServiceRead.model_validate(service))


async def tool_update_service(db: AsyncSession, service_id: int, **fields) -> dict | str:
    repo = ServiceRepository(db)
    service = await repo.update(service_id, **fields)
    if not service:
        return f"Service {service_id} not found."
    return _serialize(ServiceRead.model_validate(service))


# ── Invoice tools ────────────────────────────────────────────────────────────

async def tool_create_invoice(db: AsyncSession, customer_id: int, service_ids: list[int]) -> dict:
    repo = InvoiceRepository(db)
    invoice = await repo.create_from_services(customer_id, service_ids)
    return _serialize(InvoiceRead.model_validate(invoice))


async def tool_list_invoices(db: AsyncSession, customer_id: int | None = None,
                              status: str | None = None, limit: int = 100) -> list:
    repo = InvoiceRepository(db)
    inv_status = InvoiceStatus(status) if status else None
    invoices = await repo.list(customer_id=customer_id, status=inv_status, limit=limit)
    return _serialize([InvoiceRead.model_validate(i) for i in invoices])


async def tool_send_invoice_to_quickbooks(db: AsyncSession, invoice_id: int) -> dict | str:
    repo = InvoiceRepository(db)
    invoice = await repo.get(invoice_id)
    if not invoice:
        return f"Invoice {invoice_id} not found."
    if invoice.quickbooks_invoice_id:
        return f"Invoice {invoice_id} was already sent to QuickBooks (QB ID: {invoice.quickbooks_invoice_id})."
    qb_client = get_quickbooks_client()
    result = await qb_client.create_invoice(invoice)
    updated = await repo.set_quickbooks_id(invoice_id, result["qb_invoice_id"])
    return {
        "message": f"Invoice sent to QuickBooks successfully.",
        "qb_invoice_id": result["qb_invoice_id"],
        "invoice": _serialize(InvoiceRead.model_validate(updated)),
    }


# ── Tool registry and schema definitions ─────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "create_customer",
        "description": (
            "Create a new customer. "
            "ONLY call this tool when the user has explicitly stated ALL of the following values "
            "in this conversation: name, email, phone, address_street, address_city, address_state, "
            "address_zip. If ANY value is missing or unclear, ask the user for it — do NOT invent, "
            "guess, or use placeholder values."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name":           {"type": "string", "description": "Customer full name — must be stated by the user"},
                "email":          {"type": "string", "description": "Email address — must be stated by the user"},
                "phone":          {"type": "string", "description": "Phone number — must be stated by the user"},
                "address_street": {"type": "string", "description": "Street address — must be stated by the user"},
                "address_city":   {"type": "string", "description": "City — must be stated by the user"},
                "address_state":  {"type": "string", "description": "State — must be stated by the user"},
                "address_zip":    {"type": "string", "description": "ZIP code — must be stated by the user"},
            },
            "required": ["name", "email", "phone", "address_street", "address_city", "address_state", "address_zip"],
        },
    },
    {
        "name": "list_customers",
        "description": "List customers, optionally filtered by a search term (name, email, or phone).",
        "input_schema": {
            "type": "object",
            "properties": {
                "search": {"type": "string", "description": "Search term"},
                "limit": {"type": "integer", "default": 50},
            },
        },
    },
    {
        "name": "get_customer",
        "description": "Get a specific customer by ID.",
        "input_schema": {
            "type": "object",
            "properties": {"customer_id": {"type": "integer"}},
            "required": ["customer_id"],
        },
    },
    {
        "name": "update_customer",
        "description": "Update customer details.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer"},
                "name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "address_street": {"type": "string"},
                "address_city": {"type": "string"},
                "address_state": {"type": "string"},
                "address_zip": {"type": "string"},
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "create_service",
        "description": (
            "Create a service for a customer. cost = what the company pays, price = what the customer is charged. "
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer"},
                "name": {"type": "string", "description": "Service name / type"},
                "description": {"type": "string"},
                "cost": {"type": "number", "description": "Internal cost (what we pay)"},
                "price": {"type": "number", "description": "Price charged to customer"},
                "service_date": {"type": "string", "description": "ISO 8601 date string, e.g. 2026-03-15"},
            },
            "required": ["customer_id", "name", "cost", "price"],
        },
    },
    {
        "name": "list_services",
        "description": "List services, optionally filtered by customer and/or status (pending, in_progress, completed).",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer"},
                "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]},
                "limit": {"type": "integer", "default": 100},
            },
        },
    },
    {
        "name": "complete_service",
        "description": (
            "Mark a service as completed. Sets completed_date to now. "
            "IMPORTANT: After calling this tool, you MUST immediately call create_invoice "
            "for the same customer using this service_id, without waiting to be asked."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"service_id": {"type": "integer"}},
            "required": ["service_id"],
        },
    },
    {
        "name": "update_service",
        "description": "Update service details such as name, description, cost, price, or status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {"type": "integer"},
                "name": {"type": "string"},
                "description": {"type": "string"},
                "cost": {"type": "number"},
                "price": {"type": "number"},
                "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]},
            },
            "required": ["service_id"],
        },
    },
    {
        "name": "create_invoice",
        "description": "Create an invoice for a customer from a list of service IDs. The invoice total is calculated from service prices.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer"},
                "service_ids": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["customer_id", "service_ids"],
        },
    },
    {
        "name": "list_invoices",
        "description": "List invoices, optionally filtered by customer and/or status (draft, sent, paid).",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer"},
                "status": {"type": "string", "enum": ["draft", "sent", "paid"]},
                "limit": {"type": "integer", "default": 100},
            },
        },
    },
    {
        "name": "send_invoice_to_quickbooks",
        "description": "Send an invoice to QuickBooks and record the QuickBooks invoice ID.",
        "input_schema": {
            "type": "object",
            "properties": {"invoice_id": {"type": "integer"}},
            "required": ["invoice_id"],
        },
    },
]

# Maps tool name → async callable (receives db as first arg, then kwargs from Claude)
TOOL_HANDLERS: dict[str, callable] = {
    "create_customer": tool_create_customer,
    "list_customers": tool_list_customers,
    "get_customer": tool_get_customer,
    "update_customer": tool_update_customer,
    "create_service": tool_create_service,
    "list_services": tool_list_services,
    "complete_service": tool_complete_service,
    "update_service": tool_update_service,
    "create_invoice": tool_create_invoice,
    "list_invoices": tool_list_invoices,
    "send_invoice_to_quickbooks": tool_send_invoice_to_quickbooks,
}
