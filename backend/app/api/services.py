from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import ServiceStatus
from app.db.repositories.service_repo import ServiceRepository
from app.schemas.service import ServiceCreate, ServiceUpdate, ServiceRead

router = APIRouter(prefix="/services", tags=["services"])


@router.post("", response_model=ServiceRead, status_code=201)
async def create_service(body: ServiceCreate, db: AsyncSession = Depends(get_db)):
    repo = ServiceRepository(db)
    return await repo.create(**body.model_dump())


@router.get("", response_model=list[ServiceRead])
async def list_services(
    customer_id: int | None = None,
    status: ServiceStatus | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    repo = ServiceRepository(db)
    return await repo.list(customer_id=customer_id, status=status, limit=limit)


@router.get("/{service_id}", response_model=ServiceRead)
async def get_service(service_id: int, db: AsyncSession = Depends(get_db)):
    repo = ServiceRepository(db)
    service = await repo.get(service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.patch("/{service_id}", response_model=ServiceRead)
async def update_service(service_id: int, body: ServiceUpdate, db: AsyncSession = Depends(get_db)):
    repo = ServiceRepository(db)
    service = await repo.update(service_id, **body.model_dump(exclude_none=True))
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.post("/{service_id}/complete", response_model=ServiceRead)
async def complete_service(service_id: int, db: AsyncSession = Depends(get_db)):
    repo = ServiceRepository(db)
    service = await repo.complete(service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service
