import re
from functools import wraps
from flask import Blueprint, request, session, jsonify, current_app
from models import db, User, Team
from utils.validation import parse_optional_id

auth_bp = Blueprint("auth", __name__)
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

def login_required(f):
    """Decorator to require session authentication for protected routes."""
    @wraps(f)
    def wrap(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return jsonify(error="Authentication required"), 401
        user = db.session.get(User, user_id)
        if not user:
            session.clear()
            return jsonify(error="Authentication required"), 401
        return f(*args, **kwargs)
    return wrap

from utils.auth_decorators import role_required

def register_user():
    """Shared logic for registration endpoints (/register and /signup)."""
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify(error="Invalid request payload. Expected JSON object."), 400
    name = (data.get("name") or data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = data.get("role")
    team_id = data.get("team_id")

    if not name:
        return jsonify(error="Name is required."), 400

    if not email or not EMAIL_REGEX.match(email):
        return jsonify(error="A valid email address is required."), 400

    if not isinstance(password, str) or len(password) < 8:
        return jsonify(error="Password must be at least 8 characters long."), 400

    if User.query.filter_by(email=email).first():
        return jsonify(error="An account with this email already exists."), 409

    # First user in the system automatically gets admin privileges
    is_first = User.query.count() == 0
    raw_role = (data.get("role") or "").strip()
    if raw_role in ("Lead", "Team Lead"):
        assigned_role = "Lead"
    elif raw_role in ("Employee", "Member"):
        assigned_role = raw_role
    elif raw_role == "Admin":
        assigned_role = "Admin"
    elif is_first:
        assigned_role = "Admin"
    else:
        assigned_role = "Member"

    is_admin = is_first or assigned_role == "Admin"
    team_id_val, error = parse_optional_id(team_id, "Team ID")
    if error:
        return jsonify(error=error), 400
    if team_id_val and not db.session.get(Team, team_id_val):
        return jsonify(error="Team not found."), 404

    user = User(name=name[:80], email=email, is_admin=is_admin, role=assigned_role, team_id=team_id_val)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    # If user registered as Team Lead for a designated squad, set squad lead_id
    if assigned_role == "Lead" and team_id_val:
        team = db.session.get(Team, team_id_val)
        if team:
            team.lead_id = user.id
            db.session.commit()

    session["user_id"] = user.id
    session["role"] = user.role
    session["user_role"] = user.role
    session["team_id"] = user.team_id
    return jsonify(user=user.to_dict(), message="Account created successfully."), 201

@auth_bp.post("/register")
def register():
    return register_user()

@auth_bp.post("/signup")
def signup():
    return register_user()

@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify(error="Email and password are required."), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify(error="Incorrect email or password."), 401

    session["user_id"] = user.id
    session["role"] = user.role
    session["user_role"] = user.role
    session["team_id"] = user.team_id
    return jsonify(user=user.to_dict(), message="Login successful."), 200

@auth_bp.post("/logout")
def logout():
    session.clear()
    return jsonify(ok=True, message="Successfully logged out."), 200

@auth_bp.get("/me")
@login_required
def me():
    user = db.session.get(User, session["user_id"])
    if not user:
        session.clear()
        return jsonify(error="Authentication required"), 401
    return jsonify(user=user.to_dict()), 200

@auth_bp.put("/profile")
@login_required
def update_profile():
    """Update profile details (name, theme preference)."""
    user = db.session.get(User, session["user_id"])
    data = request.get_json(silent=True) or {}

    name = (data.get("name") or data.get("username") or "").strip()
    if name:
        user.name = name[:80]

    theme = (data.get("theme_preference") or "").strip().lower()
    if theme in ("light", "dark"):
        user.theme_preference = theme

    db.session.commit()
    return jsonify(user=user.to_dict(), message="Profile updated successfully."), 200

@auth_bp.put("/password")
@login_required
def change_password():
    """Change account password with verification of existing password."""
    user = db.session.get(User, session["user_id"])
    data = request.get_json(silent=True) or {}

    current_pw = data.get("current_password") or ""
    new_pw = data.get("new_password") or ""

    if not user.check_password(current_pw):
        return jsonify(error="Current password does not match."), 400

    if not isinstance(new_pw, str) or len(new_pw) < 8:
        return jsonify(error="New password must be at least 8 characters long."), 400

    user.set_password(new_pw)
    db.session.commit()
    return jsonify(ok=True, message="Password updated successfully."), 200

@auth_bp.post("/google")
def google():
    """Receives the Google Identity Services ID token as {credential} and verifies it."""
    client_id = current_app.config.get("GOOGLE_CLIENT_ID")
    credential = (request.get_json(silent=True) or {}).get("credential")

    if not client_id:
        return jsonify(error="Google sign-in is not configured. Set GOOGLE_CLIENT_ID."), 503
    if not credential:
        return jsonify(error="Missing Google credential."), 400

    from google.oauth2 import id_token
    from google.auth.transport import requests as grequests

    try:
        id_info = id_token.verify_oauth2_token(credential, grequests.Request(), client_id)
    except ValueError:
        return jsonify(error="Google sign-in could not be verified."), 401

    if not id_info.get("email_verified"):
        return jsonify(error="Google email is not verified."), 401

    email = id_info["email"].lower()
    user = User.query.filter_by(email=email).first()
    if not user:
        name = id_info.get("name") or email.split("@")[0]
        is_first = User.query.count() == 0
        user = User(name=name, email=email, is_admin=is_first)
        db.session.add(user)
        db.session.commit()

    session["user_id"] = user.id
    return jsonify(user=user.to_dict()), 200
