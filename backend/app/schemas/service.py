from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel

from app.db.models import ServiceStatus


class ServiceCreate(BaseModel):
    customer_id: int
    name: str
    description: str | None = None
    cost: Decimal
    price: Decimal
    service_date: datetime | None = None


class ServiceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    cost: Decimal | None = None
    price: Decimal | None = None
    service_date: datetime | None = None
    status: ServiceStatus | None = None


class ServiceRead(BaseModel):
    id: int
    customer_id: int
    name: str
    description: str | None
    status: ServiceStatus
    cost: Decimal
    price: Decimal
    service_date: datetime | None
    completed_date: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
