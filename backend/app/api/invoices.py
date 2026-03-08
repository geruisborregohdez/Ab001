from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import InvoiceStatus
from app.db.repositories.invoice_repo import InvoiceRepository
from app.integrations.quickbooks import get_quickbooks_client
from app.schemas.invoice import InvoiceCreate, InvoiceRead, InvoiceStatusUpdate

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.post("", response_model=InvoiceRead, status_code=201)
async def create_invoice(body: InvoiceCreate, db: AsyncSession = Depends(get_db)):
    repo = InvoiceRepository(db)
    return await repo.create_from_services(body.customer_id, body.service_ids)


@router.get("", response_model=list[InvoiceRead])
async def list_invoices(
    customer_id: int | None = None,
    status: InvoiceStatus | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    repo = InvoiceRepository(db)
    return await repo.list(customer_id=customer_id, status=status, limit=limit)


@router.get("/{invoice_id}", response_model=InvoiceRead)
async def get_invoice(invoice_id: int, db: AsyncSession = Depends(get_db)):
    repo = InvoiceRepository(db)
    invoice = await repo.get(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.patch("/{invoice_id}/status", response_model=InvoiceRead)
async def update_invoice_status(invoice_id: int, body: InvoiceStatusUpdate, db: AsyncSession = Depends(get_db)):
    repo = InvoiceRepository(db)
    invoice = await repo.update_status(invoice_id, body.status)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.post("/{invoice_id}/send-to-quickbooks", response_model=InvoiceRead)
async def send_to_quickbooks(invoice_id: int, db: AsyncSession = Depends(get_db)):
    repo = InvoiceRepository(db)
    invoice = await repo.get(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    qb_client = get_quickbooks_client()
    result = await qb_client.create_invoice(invoice)

    updated = await repo.set_quickbooks_id(invoice_id, result["qb_invoice_id"])
    return updated
