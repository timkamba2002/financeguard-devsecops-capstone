"""
Integration tests run against a live deployed environment.
Set API_URL env var before running:
  API_URL=http://<alb-hostname> pytest tests/integration/ -v
"""

import os
import time
import requests
import pytest

BASE = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
# In dev/staging the backend runs with SKIP_AUTH_VERIFICATION=true so any
# Bearer token is accepted. Use a fixed demo token here so these tests
# also work against environments where auth is enforced via a real token.
AUTH_TOKEN = os.environ.get("INTEGRATION_TOKEN", "demo-token")
HEADERS = {"Authorization": f"Bearer {AUTH_TOKEN}"}


@pytest.fixture(scope="session", autouse=True)
def wait_for_service():
    """Wait up to 2 minutes for the service to become available."""
    deadline = time.time() + 120
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE}/health", timeout=5)
            if r.status_code == 200:
                return
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(5)
    pytest.fail(f"Service at {BASE} did not become healthy within 120s")


class TestHealth:
    def test_health_returns_200(self):
        r = requests.get(f"{BASE}/health", timeout=10)
        assert r.status_code == 200

    def test_health_body(self):
        r = requests.get(f"{BASE}/health", timeout=10)
        data = r.json()
        assert "status" in data


class TestTransactionsAPI:
    def test_get_transactions_returns_200(self):
        r = requests.get(f"{BASE}/api/v1/transactions", headers=HEADERS, timeout=10)
        assert r.status_code == 200

    def test_get_transactions_returns_list(self):
        r = requests.get(f"{BASE}/api/v1/transactions", headers=HEADERS, timeout=10)
        assert isinstance(r.json(), list)

    def test_create_transaction(self):
        payload = {
            "description": "CI integration test",
            "amount": 42.00,
            "category": "Test",
            "type": "income",
        }
        r = requests.post(
            f"{BASE}/api/v1/transactions", json=payload, headers=HEADERS, timeout=10
        )
        assert r.status_code == 201
        data = r.json()
        assert data["description"] == payload["description"]
        assert data["amount"] == payload["amount"]
        assert "id" in data

    def test_created_transaction_appears_in_list(self):
        payload = {
            "description": "CI list-verify test",
            "amount": -10.50,
            "category": "Test",
            "type": "expense",
        }
        create = requests.post(
            f"{BASE}/api/v1/transactions", json=payload, headers=HEADERS, timeout=10
        )
        assert create.status_code == 201
        created_id = create.json()["id"]

        listing = requests.get(
            f"{BASE}/api/v1/transactions", headers=HEADERS, timeout=10
        )
        ids = [t["id"] for t in listing.json()]
        assert created_id in ids, f"Transaction {created_id} not found in listing"

    def test_invalid_payload_returns_422(self):
        r = requests.post(
            f"{BASE}/api/v1/transactions",
            json={"description": "missing required fields"},
            headers=HEADERS,
            timeout=10,
        )
        assert r.status_code == 422
