from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.repositories.customer_repo import CustomerRepository
from app.schemas.customer import CustomerCreate, CustomerUpdate, CustomerRead

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("", response_model=CustomerRead, status_code=201)
async def create_customer(body: CustomerCreate, db: AsyncSession = Depends(get_db)):
    repo = CustomerRepository(db)
    return await repo.create(**body.model_dump())


@router.get("", response_model=list[CustomerRead])
async def list_customers(search: str | None = None, limit: int = 50, db: AsyncSession = Depends(get_db)):
    repo = CustomerRepository(db)
    return await repo.list(search=search, limit=limit)


@router.get("/{customer_id}", response_model=CustomerRead)
async def get_customer(customer_id: int, db: AsyncSession = Depends(get_db)):
    repo = CustomerRepository(db)
    customer = await repo.get(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.patch("/{customer_id}", response_model=CustomerRead)
async def update_customer(customer_id: int, body: CustomerUpdate, db: AsyncSession = Depends(get_db)):
    repo = CustomerRepository(db)
    customer = await repo.update(customer_id, **body.model_dump(exclude_none=True))
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.delete("/{customer_id}", status_code=204)
async def delete_customer(customer_id: int, db: AsyncSession = Depends(get_db)):
    repo = CustomerRepository(db)
    deleted = await repo.delete(customer_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Customer not found")
