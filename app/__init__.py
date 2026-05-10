from flask import Flask

from .config import Config
from .extensions import db, login_manager
from .services.backup_service import ensure_backup_job
from .services.seed_service import seed_if_needed
import os
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy import inspect, text


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
        _ensure_employee_photo_schema()

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


def _ensure_employee_photo_schema() -> None:
    dialect = db.engine.dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        return

    insp = inspect(db.engine)
    if "employees" not in set(insp.get_table_names()):
        return

    cols = {c["name"] for c in insp.get_columns("employees")}
    statements: list[str] = []
    if "photo_blob" not in cols:
        blob_type = "BLOB" if dialect == "sqlite" else "BYTEA"
        statements.append(f"ALTER TABLE employees ADD COLUMN photo_blob {blob_type}")
    if "photo_mime" not in cols:
        mime_type = "TEXT" if dialect == "sqlite" else "VARCHAR(40)"
        statements.append(f"ALTER TABLE employees ADD COLUMN photo_mime {mime_type}")

    if not statements:
        return

    for stmt in statements:
        try:
            db.session.execute(text(stmt))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            msg = str(e).lower()
            if "duplicate column" in msg or "already exists" in msg or "duplicate" in msg:
                continue
            raise
