import pytest

def test_successful_registration(client):
    """Test user registration via /api/auth/register and /api/auth/signup."""
    res = client.post("/api/auth/register", json={
        "name": "Jane Doe",
        "email": "jane@example.com",
        "password": "SecurePassword123"
    })
    assert res.status_code == 201
    data = res.get_json()
    assert "user" in data
    assert data["user"]["name"] == "Jane Doe"
    assert data["user"]["email"] == "jane@example.com"
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]

    # Test /signup alias as well
    res_signup = client.post("/api/auth/signup", json={
        "name": "John Doe",
        "email": "john@example.com",
        "password": "SecurePassword123"
    })
    assert res_signup.status_code == 201

def test_duplicate_email_registration(client):
    """Prevent duplicate email registrations with HTTP 409 Conflict."""
    payload = {
        "name": "First User",
        "email": "duplicate@example.com",
        "password": "Password123"
    }
    first_res = client.post("/api/auth/register", json=payload)
    assert first_res.status_code == 201

    dup_res = client.post("/api/auth/register", json=payload)
    assert dup_res.status_code == 409
    assert "already exists" in dup_res.get_json()["error"]

def test_registration_validation_errors(client):
    """Validate required fields, email format, and password length."""
    # Missing name
    res = client.post("/api/auth/register", json={"email": "test@example.com", "password": "Password123"})
    assert res.status_code == 400
    assert "Name is required" in res.get_json()["error"]

    # Invalid email format
    res = client.post("/api/auth/register", json={"name": "Test", "email": "invalid-email", "password": "Password123"})
    assert res.status_code == 400
    assert "valid email" in res.get_json()["error"]

    # Short password (<8 characters)
    res = client.post("/api/auth/register", json={"name": "Test", "email": "test@example.com", "password": "short"})
    assert res.status_code == 400
    assert "8 characters" in res.get_json()["error"]

def test_registration_rejects_invalid_team_id(client):
    payload = {
        "name": "Test User",
        "email": "team-id@example.com",
        "password": "Password123",
        "team_id": "not-an-id"
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 400
    assert res.get_json()["error"] == "Team ID must be a positive integer."

    payload["team_id"] = 999999
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 404
    assert res.get_json()["error"] == "Team not found."

def test_successful_login(client):
    """Test login with correct credentials."""
    client.post("/api/auth/register", json={
        "name": "Login User",
        "email": "login@example.com",
        "password": "Password123"
    })
    # Clear session by logging out or fresh client
    client.post("/api/auth/logout")

    res = client.post("/api/auth/login", json={
        "email": "login@example.com",
        "password": "Password123"
    })
    assert res.status_code == 200
    assert res.get_json()["user"]["email"] == "login@example.com"

def test_login_incorrect_password(client):
    """Test login rejection when password does not match."""
    client.post("/api/auth/register", json={
        "name": "Login User",
        "email": "user@example.com",
        "password": "Password123"
    })
    res = client.post("/api/auth/login", json={
        "email": "user@example.com",
        "password": "WrongPassword999"
    })
    assert res.status_code == 401
    assert "Incorrect email or password" in res.get_json()["error"]

def test_login_nonexistent_user(client):
    """Test login rejection for unknown email."""
    res = client.post("/api/auth/login", json={
        "email": "ghost@example.com",
        "password": "Password123"
    })
    assert res.status_code == 401
    assert "Incorrect email or password" in res.get_json()["error"]

def test_login_missing_fields(client):
    """Test login validation for missing email or password."""
    res = client.post("/api/auth/login", json={"email": "only@example.com"})
    assert res.status_code == 400

def test_protected_me_endpoint_without_auth(client):
    """Accessing /api/auth/me without an active session returns 401."""
    res = client.get("/api/auth/me")
    assert res.status_code == 401
    assert "Authentication required" in res.get_json()["error"]

def test_protected_me_endpoint_with_auth(auth_user):
    """Accessing /api/auth/me with an active session returns profile info."""
    client = auth_user["client"]
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    data = res.get_json()
    assert data["user"]["email"] == auth_user["credentials"]["email"]
    assert data["user"]["name"] == auth_user["credentials"]["name"]

def test_logout(auth_user):
    """Test that logout terminates session and prevents subsequent protected access."""
    client = auth_user["client"]
    logout_res = client.post("/api/auth/logout")
    assert logout_res.status_code == 200

    # Protected me endpoint should now fail
    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 401

def test_update_profile(auth_user):
    """Test updating user profile name and theme preference."""
    client = auth_user["client"]
    res = client.put("/api/auth/profile", json={
        "name": "Alexander Morgan",
        "theme_preference": "dark"
    })
    assert res.status_code == 200
    user = res.get_json()["user"]
    assert user["name"] == "Alexander Morgan"
    assert user["theme_preference"] == "dark"

def test_change_password(auth_user):
    """Test changing user password with correct and incorrect current password."""
    client = auth_user["client"]

    # Wrong current password
    fail_res = client.put("/api/auth/password", json={
        "current_password": "WrongPassword123",
        "new_password": "NewSecretPassword99!"
    })
    assert fail_res.status_code == 400
    assert "Current password does not match" in fail_res.get_json()["error"]

    # Valid change
    success_res = client.put("/api/auth/password", json={
        "current_password": auth_user["credentials"]["password"],
        "new_password": "NewSecretPassword99!"
    })
    assert success_res.status_code == 200

    # Verify login with new password
    client.post("/api/auth/logout")
    login_res = client.post("/api/auth/login", json={
        "email": auth_user["credentials"]["email"],
        "password": "NewSecretPassword99!"
    })
    assert login_res.status_code == 200
