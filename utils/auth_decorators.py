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
    Checks session.get('user_role') or session.get('role') in allowed_roles.
    Admins are always authorized.
    """
    flat_roles = []
    for r in allowed_roles:
        if isinstance(r, (list, tuple, set)):
            flat_roles.extend(r)
        else:
            flat_roles.append(r)

    # Normalize roles (e.g. Employee -> Member)
    normalized = set()
    for r in flat_roles:
        r_str = str(r).strip()
        if r_str in ("Team Lead", "Lead"):
            normalized.add("Lead")
        elif r_str in ("Employee", "Member"):
            normalized.add("Member")
            normalized.add("Employee")
        else:
            normalized.add(r_str)

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

            # Sync session attributes
            current_role = user.role or ("Admin" if user.is_admin else "Member")
            session["user_role"] = current_role
            session["role"] = current_role
            session["team_id"] = user.team_id

            # Admins always pass
            if current_role == "Admin" or user.is_admin:
                return f(*args, **kwargs)

            # Check if role matches
            if current_role not in normalized:
                return jsonify(error=f"Forbidden. Action requires role: {', '.join(flat_roles)}."), 403

            return f(*args, **kwargs)
        return wrap
    return decorator
