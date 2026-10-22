import pytest
from app import create_app
from config import TestConfig
from models import db, User, Task, ActivityLog

@pytest.fixture
def app():
    """Create and configure a fresh Flask application instance for tests using in-memory SQLite."""
    test_app = create_app(TestConfig)

    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        try:
            db.session.execute(db.text("PRAGMA foreign_keys = OFF"))
        except Exception:
            pass
        db.drop_all()

@pytest.fixture
def client(app):
    """Test client for issuing requests."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """CLI runner for testing commands if needed."""
    return app.test_cli_runner()

@pytest.fixture
def auth_user(client):
    """Register and authenticate a default user (which is an admin as the first registered user)."""
    payload = {
        "name": "Alex Morgan",
        "email": "alex@example.com",
        "password": "Password123!"
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 201
    return {
        "user": res.get_json()["user"],
        "client": client,
        "credentials": payload
    }

@pytest.fixture
def second_user(app, auth_user):
    """Create a second distinct authenticated client and non-admin user."""
    second_client = app.test_client()
    payload = {
        "name": "Jordan Lee",
        "email": "jordan@example.com",
        "password": "Password456!"
    }
    res = second_client.post("/api/auth/register", json=payload)
    assert res.status_code == 201
    user_data = res.get_json()["user"]
    assert user_data["is_admin"] is False
    return {
        "user": user_data,
        "client": second_client,
        "credentials": payload
    }
