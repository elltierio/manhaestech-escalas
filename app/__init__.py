from flask import Flask

from .config import Config
from .extensions import db, login_manager
from .services.backup_service import ensure_backup_job
from .services.seed_service import seed_if_needed
import os
from werkzeug.middleware.proxy_fix import ProxyFix


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config())

    db.init_app(app)
    login_manager.init_app(app)

    if not app.debug:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    with app.app_context():
        os.makedirs(app.config["INSTANCE_DIR"], exist_ok=True)

        web_concurrency = os.environ.get("WEB_CONCURRENCY", "1")
        should_run_setup = os.environ.get("RUN_SETUP_ON_BOOT", "1") == "1" and web_concurrency == "1"
        if should_run_setup:
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
