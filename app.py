from flask import Flask, render_template, session, redirect, url_for, jsonify
from config import Config
from models import db, bcrypt, User

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    bcrypt.init_app(app)

    from routes.auth import auth_bp
    from routes.tasks import tasks_bp
    from routes.dashboard import dashboard_bp
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")

    @app.route("/")
    def landing():
        if session.get("user_id"):
            return redirect(url_for("dashboard"))
        return render_template("index.html", google_client_id=app.config["GOOGLE_CLIENT_ID"])

    @app.route("/dashboard")
    def dashboard():
        if not session.get("user_id"):
            return redirect(url_for("landing"))
        return render_template("dashboard.html", google_client_id=app.config["GOOGLE_CLIENT_ID"])

    @app.errorhandler(404)
    def nf(_):
        return jsonify(error="Not found"), 404

    with app.app_context():
        db.create_all()
    return app

if __name__ == "__main__":
    create_app().run(debug=True)
