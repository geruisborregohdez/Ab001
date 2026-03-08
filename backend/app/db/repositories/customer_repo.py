from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Customer


class CustomerRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Customer:
        customer = Customer(**fields)
        self.db.add(customer)
        await self.db.commit()
        await self.db.refresh(customer)
        return customer

    async def get(self, customer_id: int) -> Customer | None:
        result = await self.db.execute(select(Customer).where(Customer.id == customer_id))
        return result.scalar_one_or_none()

    async def list(self, search: str | None = None, limit: int = 50) -> list[Customer]:
        query = select(Customer).limit(limit).order_by(Customer.created_at.desc())
        if search:
            query = query.where(
                or_(
                    Customer.name.ilike(f"%{search}%"),
                    Customer.email.ilike(f"%{search}%"),
                    Customer.phone.ilike(f"%{search}%"),
                )
            )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(self, customer_id: int, **fields) -> Customer | None:
        customer = await self.get(customer_id)
        if not customer:
            return None
        for key, value in fields.items():
            if hasattr(customer, key) and value is not None:
                setattr(customer, key, value)
        await self.db.commit()
        await self.db.refresh(customer)
        return customer

    async def delete(self, customer_id: int) -> bool:
        customer = await self.get(customer_id)
        if not customer:
            return False
        await self.db.delete(customer)
        await self.db.commit()
        return True
