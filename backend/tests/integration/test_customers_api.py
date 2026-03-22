import pytest

VALID_PAYLOAD = {
    "name": "Acme Corp",
    "email": "acme@example.com",
    "phone": "555-0100",
    "address_street": "100 Oak Ave",
    "address_city": "Chicago",
    "address_state": "IL",
    "address_zip": "60601",
}


async def test_create_customer_returns_201(client):
    resp = await client.post("/api/customers", json=VALID_PAYLOAD)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Acme Corp"
    assert data["email"] == "acme@example.com"
    assert "id" in data
    assert "created_at" in data


async def test_create_customer_missing_fields_returns_422(client):
    resp = await client.post("/api/customers", json={"name": "Incomplete"})
    assert resp.status_code == 422


async def test_list_customers_returns_200(client, sample_customer):
    resp = await client.get("/api/customers")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    ids = [c["id"] for c in data]
    assert sample_customer["id"] in ids


async def test_list_customers_search_filter(client, sample_customer):
    resp = await client.get("/api/customers", params={"search": "Test Co"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert any(c["name"] == "Test Co" for c in data)


async def test_get_customer_by_id(client, sample_customer):
    resp = await client.get(f"/api/customers/{sample_customer['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == sample_customer["id"]


async def test_get_customer_not_found(client):
    resp = await client.get("/api/customers/99999")
    assert resp.status_code == 404


async def test_update_customer_partial(client, sample_customer):
    resp = await client.patch(
        f"/api/customers/{sample_customer['id']}",
        json={"phone": "555-9999"},
    )
    assert resp.status_code == 200
    assert resp.json()["phone"] == "555-9999"
    assert resp.json()["name"] == sample_customer["name"]


async def test_delete_customer(client, sample_customer):
    resp = await client.delete(f"/api/customers/{sample_customer['id']}")
    assert resp.status_code == 204
    # Confirm it's gone
    resp2 = await client.get(f"/api/customers/{sample_customer['id']}")
    assert resp2.status_code == 404


async def test_delete_customer_not_found(client):
    resp = await client.delete("/api/customers/99999")
    assert resp.status_code == 404


async def test_update_customer_not_found(client):
    resp = await client.patch("/api/customers/99999", json={"phone": "555-0000"})
    assert resp.status_code == 404
