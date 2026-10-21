import re
from functools import wraps
from flask import Blueprint, request, session, jsonify, current_app
from models import db, User

auth_bp = Blueprint("auth", __name__)
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def login_required(f):
    @wraps(f)
    def wrap(*a, **kw):
        if not session.get("user_id"):
            return jsonify(error="Authentication required"), 401
        return f(*a, **kw)
    return wrap

@auth_bp.post("/signup")
def signup():
    d = request.get_json(silent=True) or {}
    name, email, pw = (d.get("username") or "").strip(), (d.get("email") or "").strip().lower(), d.get("password") or ""
    if not name or not EMAIL.match(email) or len(pw) < 8:
        return jsonify(error="Enter a name, a valid email, and a password of 8+ characters."), 400
    if User.query.filter_by(email=email).first():
        return jsonify(error="An account with this email already exists."), 409
    u = User(username=name, email=email); u.set_password(pw)
    db.session.add(u); db.session.commit()
    session["user_id"] = u.id
    return jsonify(user=u.to_dict()), 201

@auth_bp.post("/login")
def login():
    d = request.get_json(silent=True) or {}
    u = User.query.filter_by(email=(d.get("email") or "").strip().lower()).first()
    if not u or not u.check_password(d.get("password") or ""):
        return jsonify(error="Incorrect email or password."), 401
    session["user_id"] = u.id
    return jsonify(user=u.to_dict())

@auth_bp.post("/google")
def google():
    """Receives the Google Identity Services ID token as {credential} and verifies it."""
    cid = current_app.config["GOOGLE_CLIENT_ID"]
    cred = (request.get_json(silent=True) or {}).get("credential")
    if not cid:
        return jsonify(error="Google sign-in is not configured. Set GOOGLE_CLIENT_ID."), 503
    if not cred:
        return jsonify(error="Missing Google credential."), 400
    from google.oauth2 import id_token
    from google.auth.transport import requests as grequests
    try:
        info = id_token.verify_oauth2_token(cred, grequests.Request(), cid)
    except ValueError:
        return jsonify(error="Google sign-in could not be verified."), 401
    if not info.get("email_verified"):
        return jsonify(error="Google email is not verified."), 401
    email = info["email"].lower()
    u = User.query.filter_by(email=email).first()
    if not u:
        u = User(username=info.get("name") or email.split("@")[0], email=email)
        db.session.add(u); db.session.commit()
    session["user_id"] = u.id
    return jsonify(user=u.to_dict())

@auth_bp.post("/logout")
def logout():
    session.clear()
    return jsonify(ok=True)

@auth_bp.get("/me")
@login_required
def me():
    u = db.session.get(User, session["user_id"])
    if not u:
        session.clear()
        return jsonify(error="Authentication required"), 401
    return jsonify(user=u.to_dict())
