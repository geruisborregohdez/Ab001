import pytest


async def test_create_service_returns_201(client, sample_customer):
    resp = await client.post("/api/services", json={
        "customer_id": sample_customer["id"],
        "name": "Plumbing Fix",
        "cost": "50.00",
        "price": "120.00",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Plumbing Fix"
    assert data["status"] == "pending"
    assert "id" in data


async def test_create_service_status_defaults_to_pending(client, sample_customer):
    resp = await client.post("/api/services", json={
        "customer_id": sample_customer["id"],
        "name": "Electric Check",
        "cost": "40.00",
        "price": "100.00",
    })
    assert resp.json()["status"] == "pending"


async def test_list_services_by_customer(client, sample_service, sample_customer):
    resp = await client.get("/api/services", params={"customer_id": sample_customer["id"]})
    assert resp.status_code == 200
    data = resp.json()
    assert all(s["customer_id"] == sample_customer["id"] for s in data)


async def test_list_services_by_status(client, sample_service):
    resp = await client.get("/api/services", params={"status": "pending"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(s["status"] == "pending" for s in data)


async def test_get_service_by_id(client, sample_service):
    resp = await client.get(f"/api/services/{sample_service['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == sample_service["id"]


async def test_get_service_not_found(client):
    resp = await client.get("/api/services/99999")
    assert resp.status_code == 404


async def test_update_service_partial(client, sample_service):
    resp = await client.patch(
        f"/api/services/{sample_service['id']}",
        json={"description": "Updated description"},
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "Updated description"


async def test_complete_service(client, sample_service):
    resp = await client.post(f"/api/services/{sample_service['id']}/complete", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["completed_date"] is not None


async def test_complete_service_not_found(client):
    resp = await client.post("/api/services/99999/complete", json={})
    assert resp.status_code == 404


async def test_update_service_not_found(client):
    resp = await client.patch("/api/services/99999", json={"description": "ghost"})
    assert resp.status_code == 404
