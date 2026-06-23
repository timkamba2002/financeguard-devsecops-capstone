import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app, Base, get_db, TransactionModel

# Use a temporary file-based SQLite database for running the tests
TEST_DB_FILE = "./test_temp.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Override get_db dependency to point to our test database
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def run_around_tests():
    # Setup: Create tables and pre-populate mock data before each test runs
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.add(
        TransactionModel(
            user_id="demo-user-123",
            description="Consulting Fee",
            amount=5000.0,
            category="Revenue",
            type="income",
        )
    )
    db.add(
        TransactionModel(
            user_id="demo-user-123",
            description="GitHub Enterprise",
            amount=-250.0,
            category="SaaS",
            type="expense",
        )
    )
    db.commit()
    db.close()

    yield

    # Teardown: Drop tables and remove the database file
    Base.metadata.drop_all(bind=engine)
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass


client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_list_transactions_unauthorized():
    # Calling without authorization header should fail with 401 Unauthorized
    response = client.get("/api/v1/transactions")
    assert response.status_code == 401


def test_list_transactions_authorized():
    headers = {"Authorization": "Bearer mock_token"}
    response = client.get("/api/v1/transactions", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2


def test_create_transaction():
    headers = {"Authorization": "Bearer mock_token"}
    new_tx = {
        "description": "Office Rent",
        "amount": 2500.0,
        "category": "Rent",
        "type": "expense",
    }
    response = client.post("/api/v1/transactions", json=new_tx, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["description"] == "Office Rent"
    assert data["amount"] == 2500.0
    assert data["type"] == "expense"
    assert "id" in data
