"""Automated tests for FastAPI endpoints and run ledger."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app.models import RunModel

# In-memory SQLite for fast, isolated API unit tests
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    """Create fresh database with required seed for every test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Seed the required initial run sbx-seeddemo1
    with TestingSessionLocal() as db:
        seed = RunModel(
            run_id="run-seed-001",
            sandbox_name="sbx-seeddemo1",
            problem_id="problem-seed-eval",
            state="succeeded",
            execution_target="celesto_sandbox",
        )
        db.add(seed)
        db.commit()

    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    """GET /health returns HTTP 200 and {'status': 'ok'}."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_runs_includes_seed(client):
    """GET /api/runs returns stored runs including seeded sbx-seeddemo1."""
    response = client.get("/api/runs")
    assert response.status_code == 200
    runs = response.json()
    assert isinstance(runs, list)
    assert len(runs) >= 1
    seed_run = next((r for r in runs if r["sandbox_name"] == "sbx-seeddemo1"), None)
    assert seed_run is not None
    assert seed_run["execution_target"] == "celesto_sandbox"
    assert seed_run["state"] == "succeeded"


def test_create_run_valid(client):
    """POST /api/runs with valid data returns HTTP 201."""
    payload = {
        "run_id": "run-test-101",
        "sandbox_name": "sbx-valid1234",
        "problem_id": "problem-audit-test",
        "state": "created",
        "execution_target": "celesto_sandbox",
    }
    response = client.post("/api/runs", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["run_id"] == "run-test-101"
    assert data["sandbox_name"] == "sbx-valid1234"
    assert data["state"] == "created"
    assert data["execution_target"] == "celesto_sandbox"


def test_create_run_invalid_execution_target(client):
    """POST /api/runs rejects any execution_target other than celesto_sandbox with HTTP 400."""
    payload = {
        "run_id": "run-test-102",
        "sandbox_name": "sbx-valid1234",
        "problem_id": "problem-audit-test",
        "state": "created",
        "execution_target": "docker_host",  # Invalid
    }
    response = client.post("/api/runs", json=payload)
    assert response.status_code == 400


def test_create_run_invalid_state(client):
    """POST /api/runs rejects invalid state values with HTTP 400."""
    payload = {
        "run_id": "run-test-103",
        "sandbox_name": "sbx-valid1234",
        "problem_id": "problem-audit-test",
        "state": "unknown_state",  # Invalid
        "execution_target": "celesto_sandbox",
    }
    response = client.post("/api/runs", json=payload)
    assert response.status_code == 400


def test_create_run_invalid_sandbox_name(client):
    """POST /api/runs rejects sandbox names not matching sbx-[a-z0-9]{8,} with HTTP 400."""
    invalid_names = [
        "short",             # No sbx- prefix
        "sbx-short",         # Under 8 chars
        "sbx-UPPERCASE123",  # Uppercase not allowed
        "sbx-invalid_dash",  # Underscore not allowed
    ]
    for bad_name in invalid_names:
        payload = {
            "run_id": f"run-bad-{bad_name}",
            "sandbox_name": bad_name,
            "problem_id": "problem-audit-test",
            "state": "created",
            "execution_target": "celesto_sandbox",
        }
        response = client.post("/api/runs", json=payload)
        assert response.status_code == 400, f"Expected 400 for sandbox_name: {bad_name}"


def test_create_run_duplicate_id_handled(client):
    """POST /api/runs rejects duplicate run_id cleanly with HTTP 400."""
    payload = {
        "run_id": "run-dup-test",
        "sandbox_name": "sbx-duplicate01",
        "problem_id": "problem-audit-test",
        "state": "created",
        "execution_target": "celesto_sandbox",
    }
    res1 = client.post("/api/runs", json=payload)
    assert res1.status_code == 201

    # Second insert with same run_id
    res2 = client.post("/api/runs", json=payload)
    assert res2.status_code == 400
