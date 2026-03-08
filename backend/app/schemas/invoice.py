from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel

from app.db.models import InvoiceStatus


class InvoiceCreate(BaseModel):
    customer_id: int
    service_ids: list[int]
    notes: str | None = None


class InvoiceLineItemRead(BaseModel):
    id: int
    service_id: int
    description: str
    unit_price: Decimal
    amount: Decimal

    model_config = {"from_attributes": True}


class InvoiceRead(BaseModel):
    id: int
    customer_id: int
    invoice_number: str
    status: InvoiceStatus
    total_amount: Decimal
    quickbooks_invoice_id: str | None
    notes: str | None
    line_items: list[InvoiceLineItemRead] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InvoiceStatusUpdate(BaseModel):
    status: InvoiceStatus
