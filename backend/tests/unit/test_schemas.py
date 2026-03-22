import pytest
from decimal import Decimal
from pydantic import ValidationError

from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.schemas.service import ServiceCreate, ServiceUpdate
from app.schemas.invoice import InvoiceCreate, InvoiceStatusUpdate
from app.db.models import InvoiceStatus


VALID_CUSTOMER = {
    "name": "Acme Corp",
    "email": "acme@example.com",
    "phone": "555-0100",
    "address_street": "100 Oak Ave",
    "address_city": "Chicago",
    "address_state": "IL",
    "address_zip": "60601",
}


class TestCustomerCreate:
    def test_valid_payload_parses(self):
        c = CustomerCreate(**VALID_CUSTOMER)
        assert c.name == "Acme Corp"
        assert c.email == "acme@example.com"

    def test_missing_name_raises(self):
        data = {k: v for k, v in VALID_CUSTOMER.items() if k != "name"}
        with pytest.raises(ValidationError):
            CustomerCreate(**data)

    def test_missing_email_raises(self):
        data = {k: v for k, v in VALID_CUSTOMER.items() if k != "email"}
        with pytest.raises(ValidationError):
            CustomerCreate(**data)

    def test_missing_address_raises(self):
        data = {k: v for k, v in VALID_CUSTOMER.items() if k != "address_zip"}
        with pytest.raises(ValidationError):
            CustomerCreate(**data)


class TestCustomerUpdate:
    def test_empty_dict_is_valid(self):
        u = CustomerUpdate()
        assert u.name is None
        assert u.email is None

    def test_partial_update_is_valid(self):
        u = CustomerUpdate(name="New Name")
        assert u.name == "New Name"
        assert u.phone is None


class TestServiceCreate:
    def test_decimal_fields_accept_string(self):
        s = ServiceCreate(customer_id=1, name="Painting", cost="80.00", price="150.00")
        assert s.cost == Decimal("80.00")
        assert s.price == Decimal("150.00")

    def test_customer_id_must_be_int(self):
        with pytest.raises(ValidationError):
            ServiceCreate(customer_id="not-an-int", name="Painting", cost="80.00", price="150.00")

    def test_description_is_optional(self):
        s = ServiceCreate(customer_id=1, name="Painting", cost="80.00", price="150.00")
        assert s.description is None

    def test_missing_price_raises(self):
        with pytest.raises(ValidationError):
            ServiceCreate(customer_id=1, name="Painting", cost="80.00")


class TestServiceUpdate:
    def test_all_fields_optional(self):
        u = ServiceUpdate()
        assert u.name is None
        assert u.cost is None
        assert u.status is None

    def test_partial_update_valid(self):
        u = ServiceUpdate(name="Updated Name", cost=Decimal("95.00"))
        assert u.name == "Updated Name"
        assert u.cost == Decimal("95.00")


class TestInvoiceCreate:
    def test_valid_payload(self):
        inv = InvoiceCreate(customer_id=1, service_ids=[1, 2])
        assert inv.customer_id == 1
        assert inv.service_ids == [1, 2]

    def test_missing_customer_id_raises(self):
        with pytest.raises(ValidationError):
            InvoiceCreate(service_ids=[1])

    def test_missing_service_ids_raises(self):
        with pytest.raises(ValidationError):
            InvoiceCreate(customer_id=1)

    def test_notes_optional(self):
        inv = InvoiceCreate(customer_id=1, service_ids=[1])
        assert inv.notes is None


class TestInvoiceStatusUpdate:
    def test_valid_status_values(self):
        for status in ("draft", "sent", "paid"):
            u = InvoiceStatusUpdate(status=status)
            assert u.status == InvoiceStatus(status)

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            InvoiceStatusUpdate(status="cancelled")
