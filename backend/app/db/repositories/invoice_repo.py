from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Invoice, InvoiceLineItem, InvoiceStatus, Service


class InvoiceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _next_invoice_number(self) -> str:
        ts = datetime.now(timezone.utc)
        return f"INV-{ts.year}{ts.month:02d}-{ts.strftime('%H%M%S%f')[:8]}"

    async def create_from_services(self, customer_id: int, service_ids: list[int]) -> Invoice:
        result = await self.db.execute(
            select(Service).where(Service.id.in_(service_ids), Service.customer_id == customer_id)
        )
        services = list(result.scalars().all())

        total = Decimal("0")
        line_items = []
        for svc in services:
            line_items.append(
                InvoiceLineItem(
                    service_id=svc.id,
                    description=svc.name,
                    unit_price=svc.price,
                    amount=svc.price,
                )
            )
            total += svc.price

        invoice = Invoice(
            customer_id=customer_id,
            invoice_number=self._next_invoice_number(),
            total_amount=total,
            line_items=line_items,
        )
        self.db.add(invoice)
        await self.db.commit()
        await self.db.refresh(invoice)
        return invoice

    async def get(self, invoice_id: int) -> Invoice | None:
        result = await self.db.execute(
            select(Invoice)
            .options(selectinload(Invoice.line_items))
            .where(Invoice.id == invoice_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self, customer_id: int | None = None, status: InvoiceStatus | None = None, limit: int = 100
    ) -> list[Invoice]:
        query = (
            select(Invoice)
            .options(selectinload(Invoice.line_items))
            .limit(limit)
            .order_by(Invoice.created_at.desc())
        )
        if customer_id:
            query = query.where(Invoice.customer_id == customer_id)
        if status:
            query = query.where(Invoice.status == status)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_status(self, invoice_id: int, status: InvoiceStatus) -> Invoice | None:
        invoice = await self.get(invoice_id)
        if not invoice:
            return None
        invoice.status = status
        await self.db.commit()
        await self.db.refresh(invoice)
        return invoice

    async def set_quickbooks_id(self, invoice_id: int, qb_id: str) -> Invoice | None:
        invoice = await self.get(invoice_id)
        if not invoice:
            return None
        invoice.quickbooks_invoice_id = qb_id
        invoice.status = InvoiceStatus.sent
        await self.db.commit()
        await self.db.refresh(invoice)
        return invoice
