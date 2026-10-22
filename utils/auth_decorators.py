from functools import wraps
from flask import session, jsonify
from models import db, User

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

def role_required(*allowed_roles):
    """
    Role-Based Access Control decorator.
    Allows access if current user's role is in allowed_roles, or if user is an Admin.
    Supports both @role_required('Admin', 'Lead') and @role_required(['Admin', 'Lead']).
    """
    flat_roles = []
    for r in allowed_roles:
        if isinstance(r, (list, tuple, set)):
            flat_roles.extend(r)
        else:
            flat_roles.append(r)

    # Normalize aliases
    normalized_allowed = set()
    for r in flat_roles:
        r_str = str(r).strip()
        if r_str == "Team Lead":
            normalized_allowed.add("Lead")
        elif r_str in ("Employee", "Member"):
            normalized_allowed.add("Employee")
            normalized_allowed.add("Member")
        else:
            normalized_allowed.add(r_str)

    def decorator(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id:
                return jsonify(error="Authentication required"), 401
            user = db.session.get(User, user_id)
            if not user:
                session.clear()
                return jsonify(error="Authentication required"), 401

            # Keep session roles in sync
            session["role"] = user.role
            session["team_id"] = user.team_id

            # Admins always pass role authorization
            if user.role == "Admin" or user.is_admin:
                return f(*args, **kwargs)

            user_role = user.role or "Member"
            if user_role == "Team Lead":
                user_role = "Lead"

            if user_role not in normalized_allowed and not (user_role in ("Employee", "Member") and any(x in normalized_allowed for x in ("Employee", "Member"))):
                return jsonify(error=f"Forbidden. Action requires role: {', '.join(flat_roles)}."), 403
            return f(*args, **kwargs)
        return wrap
    return decorator
