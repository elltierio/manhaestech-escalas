from __future__ import annotations

import os
import shutil
import threading
from datetime import datetime

from flask import current_app


_backup_timer: threading.Timer | None = None


def ensure_backup_job() -> None:
    _ensure_instance_dirs()
    db_uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    using_sqlite = db_uri.startswith("sqlite:///")

    if not using_sqlite:
        return

    if current_app.debug or os.environ.get("BACKUP_ON_STARTUP", "0") == "1":
        _backup_now()

    if current_app.debug:
        return

    if os.environ.get("ENABLE_BACKUP_TIMER", "0") != "1":
        return

    if os.environ.get("WEB_CONCURRENCY", "1") != "1":
        return

    app = current_app._get_current_object()
    _schedule_next(app)


def _ensure_instance_dirs() -> None:
    instance_dir = current_app.config["INSTANCE_DIR"]
    upload_dir = current_app.config["UPLOAD_DIR"]
    backup_dir = current_app.config["BACKUP_DIR"]
    os.makedirs(instance_dir, exist_ok=True)
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(backup_dir, exist_ok=True)


def _backup_now() -> None:
    db_path = current_app.config["DB_PATH"]
    if not os.path.exists(db_path):
        return

    backup_dir = current_app.config["BACKUP_DIR"]
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = os.path.join(backup_dir, f"manhaestech_escalas-{ts}.sqlite")
    shutil.copy2(db_path, backup_path)


def _schedule_next(app) -> None:
    global _backup_timer
    if _backup_timer is not None:
        return

    def _run() -> None:
        global _backup_timer
        try:
            with app.app_context():
                _backup_now()
        finally:
            _backup_timer = None
            _schedule_next(app)

    _backup_timer = threading.Timer(12 * 60 * 60, _run)
    _backup_timer.daemon = True
    _backup_timer.start()
