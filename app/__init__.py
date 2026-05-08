from flask import Flask

from .config import Config
from .extensions import db, login_manager
from .services.backup_service import ensure_backup_job
from .services.seed_service import seed_if_needed
import os


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config())

    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        os.makedirs(app.config["INSTANCE_DIR"], exist_ok=True)
        db.create_all()
        seed_if_needed()
        ensure_backup_job()

    from .routes.auth import auth_bp
    from .routes.dashboard import dashboard_bp
    from .routes.employees import employees_bp
    from .routes.calendar import calendar_bp
    from .routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(api_bp)

    return app
