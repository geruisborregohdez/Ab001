from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Service, ServiceStatus


class ServiceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Service:
        service = Service(**fields)
        self.db.add(service)
        await self.db.commit()
        await self.db.refresh(service)
        return service

    async def get(self, service_id: int) -> Service | None:
        result = await self.db.execute(select(Service).where(Service.id == service_id))
        return result.scalar_one_or_none()

    async def list(
        self, customer_id: int | None = None, status: ServiceStatus | None = None, limit: int = 100
    ) -> list[Service]:
        query = select(Service).limit(limit).order_by(Service.created_at.desc())
        if customer_id:
            query = query.where(Service.customer_id == customer_id)
        if status:
            query = query.where(Service.status == status)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(self, service_id: int, **fields) -> Service | None:
        service = await self.get(service_id)
        if not service:
            return None
        for key, value in fields.items():
            if hasattr(service, key) and value is not None:
                setattr(service, key, value)
        await self.db.commit()
        await self.db.refresh(service)
        return service

    async def complete(self, service_id: int) -> Service | None:
        service = await self.get(service_id)
        if not service:
            return None
        service.status = ServiceStatus.completed
        service.completed_date = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(service)
        return service
