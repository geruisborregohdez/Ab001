from datetime import datetime
from pydantic import BaseModel, EmailStr


class CustomerCreate(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None
    address_street: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    address_street: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip: str | None = None


class CustomerRead(BaseModel):
    id: int
    name: str
    email: str | None
    phone: str | None
    address_street: str | None
    address_city: str | None
    address_state: str | None
    address_zip: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
