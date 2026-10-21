import os
from flask import Flask, render_template, session, redirect, url_for, jsonify
from config import Config
from models import db, bcrypt, User
from models.migrate import apply_migrations

def create_app(config_class=Config):
    """Application factory for TaskFlow Pro Flask backend."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)

    # Register API blueprints
    from routes.auth import auth_bp
    from routes.tasks import tasks_bp
    from routes.dashboard import dashboard_bp
    from routes.admin import admin_bp
    from routes.activity import activity_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(activity_bp, url_prefix="/api/activity")

    # Frontend Page Routes
    @app.route("/")
    def landing():
        if session.get("user_id"):
            return redirect(url_for("dashboard"))
        return render_template("index.html", google_client_id=app.config.get("GOOGLE_CLIENT_ID", ""))

    @app.route("/dashboard")
    def dashboard():
        if not session.get("user_id"):
            return redirect(url_for("landing"))
        return render_template("dashboard.html", google_client_id=app.config.get("GOOGLE_CLIENT_ID", ""))

    # Generic JSON error handlers
    @app.errorhandler(400)
    def bad_request(err):
        return jsonify(error="Bad request."), 400

    @app.errorhandler(403)
    def forbidden(err):
        return jsonify(error="Forbidden. Administrative privileges required."), 403

    @app.errorhandler(404)
    def not_found(err):
        return jsonify(error="Resource not found."), 404

    @app.errorhandler(405)
    def method_not_allowed(err):
        return jsonify(error="Method not allowed."), 405

    @app.errorhandler(500)
    def internal_error(err):
        return jsonify(error="An internal server error occurred."), 500

    # Ensure tables exist and apply non-destructive SQLite column additions
    with app.app_context():
        # Apply SQLite migrations if connecting to a real file
        db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        if "sqlite:///" in db_uri and not db_uri.endswith(":memory:"):
            db_file = db_uri.replace("sqlite:///", "")
            apply_migrations(db_file)
        db.create_all()

        # Bootstrap: If no admin exists in the system, promote first user to admin
        if not app.config.get("TESTING"):
            first_user = User.query.first()
            if first_user and not User.query.filter_by(is_admin=True).first():
                first_user.is_admin = True
                db.session.commit()

    return app

if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
