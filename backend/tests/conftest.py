import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import get_db
from app.db.models import Base


TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def engine():
    eng = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_customer(client):
    resp = await client.post("/api/customers", json={
        "name": "Test Co",
        "email": "test@example.com",
        "phone": "555-1234",
        "address_street": "1 Main St",
        "address_city": "Springfield",
        "address_state": "IL",
        "address_zip": "62701",
    })
    assert resp.status_code == 201
    return resp.json()


@pytest_asyncio.fixture
async def sample_service(client, sample_customer):
    resp = await client.post("/api/services", json={
        "customer_id": sample_customer["id"],
        "name": "HVAC Repair",
        "description": "Annual check",
        "cost": "80.00",
        "price": "150.00",
    })
    assert resp.status_code == 201
    return resp.json()


@pytest_asyncio.fixture
async def completed_service(client, sample_service):
    resp = await client.post(f"/api/services/{sample_service['id']}/complete", json={})
    assert resp.status_code == 200
    return resp.json()


@pytest_asyncio.fixture
async def sample_invoice(client, sample_customer, completed_service):
    resp = await client.post("/api/invoices", json={
        "customer_id": sample_customer["id"],
        "service_ids": [completed_service["id"]],
    })
    assert resp.status_code == 201
    return resp.json()
