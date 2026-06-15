import pytest
from fastapi.testclient import TestClient
from main import app, MOCK_TRANSACTIONS

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_list_transactions_unauthorized():
    # Calling without authorization header should fail
    response = client.get("/api/v1/transactions")
    assert response.status_code == 403  # HTTPBearer returns 403 when header is missing

def test_list_transactions_authorized():
    # Calling with dummy bearer token (which skips validation in mock mode)
    headers = {"Authorization": "Bearer mock_token"}
    response = client.get("/api/v1/transactions", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_create_transaction():
    headers = {"Authorization": "Bearer mock_token"}
    new_tx = {
        "description": "Office Rent",
        "amount": 2500.0,
        "category": "Rent",
        "type": "expense"
    }
    response = client.post("/api/v1/transactions", json=new_tx, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["description"] == "Office Rent"
    assert data["amount"] == 2500.0
    assert data["type"] == "expense"
    assert "id" in data
