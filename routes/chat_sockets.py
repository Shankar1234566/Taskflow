from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, session
from flask_socketio import SocketIO, join_room, leave_room, emit
from models import db, User, Team, Task, ChatMessage
from utils.auth_decorators import login_required

chat_bp = Blueprint("chat", __name__)
socketio = SocketIO(cors_allowed_origins="*")

def get_current_user_from_session():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)

@chat_bp.get("/channels")
@login_required
def get_channels():
    """
    Returns available chat channels for current user:
    - Team General Channel
    - Tasks assigned to or in the user's squad that have discussions
    """
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    if not user:
        return jsonify(error="Authentication required."), 401

    team_id = user.team_id
    team_name = user.team.name if user.team else "General Channel"

    channels = [
        {
            "id": "team_general",
            "type": "team",
            "team_id": team_id,
            "task_id": None,
            "title": f"#{team_name}",
            "description": "Squad team-wide real-time discussion",
            "icon": "hash",
            "unread_count": 0
        }
    ]

    # Query tasks relevant to squad or user
    task_query = Task.query
    if user.role != "Admin" and not user.is_admin:
        if team_id:
            task_query = task_query.filter(db.or_(
                Task.team_id == team_id,
                Task.assigned_to_id == user.id,
                Task.user_id == user.id
            ))
        else:
            task_query = task_query.filter(db.or_(
                Task.assigned_to_id == user.id,
                Task.user_id == user.id
            ))

    tasks = task_query.order_by(Task.updated_at.desc(), Task.created_at.desc()).limit(20).all()

    for t in tasks:
        # Check message count for this task
        msg_count = ChatMessage.query.filter_by(task_id=t.id).count()
        channels.append({
            "id": f"task_{t.id}",
            "type": "task",
            "team_id": t.team_id or team_id,
            "task_id": t.id,
            "title": f"📌 {t.title}",
            "description": f"Status: {t.status} • Priority: {t.priority}",
            "icon": "bookmark",
            "unread_count": msg_count
        })

    return jsonify(channels=channels), 200

@chat_bp.get("/messages")
@login_required
def get_messages():
    """
    Fetches message history for a given team channel or task thread.
    GET /api/chat/messages?team_id=X&task_id=Y
    """
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    if not user:
        return jsonify(error="Authentication required."), 401

    args = request.args
    team_id = args.get("team_id", type=int) or user.team_id
    task_id_raw = args.get("task_id")
    task_id = int(task_id_raw) if task_id_raw and task_id_raw not in ("null", "undefined", "") else None

    query = ChatMessage.query

    if task_id:
        query = query.filter(ChatMessage.task_id == task_id)
    else:
        # Team general channel messages (where task_id is NULL)
        if team_id:
            query = query.filter(ChatMessage.team_id == team_id, ChatMessage.task_id.is_(None))
        else:
            query = query.filter(ChatMessage.task_id.is_(None))

    messages = query.order_by(ChatMessage.created_at.asc()).limit(150).all()

    return jsonify(messages=[m.to_dict() for m in messages]), 200

@chat_bp.post("/messages")
@login_required
def post_message():
    """
    REST API endpoint for sending a chat message.
    Also broadcasts to WebSocket subscribers via socketio.emit.
    """
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    if not user:
        return jsonify(error="Authentication required."), 401

    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify(error="Message content is required."), 400

    team_id = data.get("team_id") or user.team_id
    if not team_id:
        # Fallback to team 1 or user default
        first_team = Team.query.first()
        team_id = first_team.id if first_team else 1

    task_id_raw = data.get("task_id")
    task_id = int(task_id_raw) if task_id_raw and str(task_id_raw) not in ("null", "undefined", "") else None
    attachment_url = data.get("attachment_url")

    msg = ChatMessage(
        sender_id=user.id,
        team_id=team_id,
        task_id=task_id,
        content=content[:2000],
        attachment_url=attachment_url
    )
    db.session.add(msg)
    db.session.commit()

    msg_dict = msg.to_dict()

    # Broadcast via WebSocket
    room_name = f"task_{task_id}" if task_id else f"team_{team_id}"
    socketio.emit("new_message", msg_dict, to=room_name)

    return jsonify(message=msg_dict), 201

# ==============================================================================
# WEBSOCKET EVENT LISTENERS
# ==============================================================================

@socketio.on("join_room")
def handle_join_room(data):
    """
    Handles client joining room:
    room name is either `task_<task_id>` or `team_<team_id>`.
    """
    data = data or {}
    task_id = data.get("task_id")
    team_id = data.get("team_id")

    if task_id and str(task_id) not in ("null", "undefined", ""):
        room = f"task_{task_id}"
    elif team_id:
        room = f"team_{team_id}"
    else:
        user_id = session.get("user_id")
        user = db.session.get(User, user_id) if user_id else None
        room = f"team_{user.team_id}" if user and user.team_id else "team_1"

    join_room(room)
    emit("joined_room", {"room": room, "status": "connected"})

@socketio.on("leave_room")
def handle_leave_room(data):
    """Handles client leaving a room."""
    data = data or {}
    task_id = data.get("task_id")
    team_id = data.get("team_id")

    if task_id and str(task_id) not in ("null", "undefined", ""):
        room = f"task_{task_id}"
    elif team_id:
        room = f"team_{team_id}"
    else:
        return

    leave_room(room)
    emit("left_room", {"room": room})

@socketio.on("send_message")
def handle_send_message(data):
    """
    Receives message payload via WebSocket:
    Verifies authorization from session, saves to database, and broadcasts to room.
    """
    user_id = session.get("user_id")
    if not user_id:
        emit("error", {"error": "Authentication required."})
        return

    user = db.session.get(User, user_id)
    if not user:
        emit("error", {"error": "User not found."})
        return

    content = (data.get("content") or "").strip()
    if not content:
        emit("error", {"error": "Message content cannot be blank."})
        return

    team_id = data.get("team_id") or user.team_id or 1
    task_id_raw = data.get("task_id")
    task_id = int(task_id_raw) if task_id_raw and str(task_id_raw) not in ("null", "undefined", "") else None
    attachment_url = data.get("attachment_url")

    msg = ChatMessage(
        sender_id=user.id,
        team_id=team_id,
        task_id=task_id,
        content=content[:2000],
        attachment_url=attachment_url
    )
    db.session.add(msg)
    db.session.commit()

    msg_dict = msg.to_dict()
    room = f"task_{task_id}" if task_id else f"team_{team_id}"

    # Broadcast to all clients in the room (including sender)
    emit("new_message", msg_dict, to=room)
