import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    BASE_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    INSTANCE_DIR: str = os.path.join(BASE_DIR, "instance")
    DB_PATH: str = os.path.join(INSTANCE_DIR, "manhaestech_escalas.sqlite")
    SQLALCHEMY_DATABASE_URI: str = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    UPLOAD_DIR: str = os.path.join(INSTANCE_DIR, "uploads")
    BACKUP_DIR: str = os.path.join(INSTANCE_DIR, "backups")

    SCHEDULE_BASE_DATE: str = os.environ.get("SCHEDULE_BASE_DATE", "")
