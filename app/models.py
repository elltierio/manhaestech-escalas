from __future__ import annotations

from datetime import date, datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class User(db.Model, UserMixin, TimestampMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=True, nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return db.session.get(User, int(user_id))


class Setting(db.Model):
    __tablename__ = "settings"

    key = db.Column(db.String(120), primary_key=True)
    value = db.Column(db.Text, nullable=False)


class Employee(db.Model, TimestampMixin):
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False)  # "encarregado" | "porteiro"
    squad = db.Column(db.String(80), nullable=False)  # name of encarregado squad/team
    is_extra = db.Column(db.Boolean, default=False, nullable=False)
    photo_path = db.Column(db.String(255), nullable=True)
    photo_blob = db.Column(db.LargeBinary, nullable=True)
    photo_mime = db.Column(db.String(40), nullable=True)

    def display_role(self) -> str:
        return "Encarregado" if self.role == "encarregado" else "Porteiro"


class Schedule(db.Model, TimestampMixin):
    __tablename__ = "schedules"

    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.Date, nullable=False, index=True)
    shift = db.Column(db.String(10), nullable=False)  # "diurno" | "noturno"
    manager_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    notes = db.Column(db.Text, nullable=True)

    manager = db.relationship("Employee", foreign_keys=[manager_id])
    assignments = db.relationship(
        "Assignment", back_populates="schedule", cascade="all, delete-orphan"
    )

    __table_args__ = (db.UniqueConstraint("day", "shift", name="uq_schedule_day_shift"),)

    @property
    def display_shift(self) -> str:
        return "Diurno" if self.shift == "diurno" else "Noturno"


class Assignment(db.Model, TimestampMixin):
    __tablename__ = "assignments"

    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey("schedules.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    status = db.Column(
        db.String(10), nullable=False, default="titular"
    )  # "titular" | "extra" | "falta"

    schedule = db.relationship("Schedule", back_populates="assignments")
    employee = db.relationship("Employee", foreign_keys=[employee_id])

    __table_args__ = (
        db.UniqueConstraint(
            "schedule_id", "employee_id", name="uq_assignment_schedule_employee"
        ),
    )


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    actor_username = db.Column(db.String(80), nullable=True)
    action = db.Column(db.String(60), nullable=False)
    entity = db.Column(db.String(60), nullable=False)
    entity_id = db.Column(db.String(60), nullable=True)
    ip = db.Column(db.String(80), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    detail = db.Column(db.Text, nullable=True)


def log_activity(
    *,
    actor_user_id: int | None,
    actor_username: str | None,
    action: str,
    entity: str,
    entity_id: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    detail: str | None = None,
) -> None:
    db.session.add(
        ActivityLog(
            actor_user_id=actor_user_id,
            actor_username=actor_username,
            action=action,
            entity=entity,
            entity_id=entity_id,
            ip=ip,
            user_agent=user_agent,
            detail=detail,
        )
    )
    db.session.commit()


def get_setting(key: str, default: str | None = None) -> str | None:
    row = db.session.get(Setting, key)
    return row.value if row else default


def set_setting(key: str, value: str) -> None:
    row = db.session.get(Setting, key)
    if not row:
        row = Setting(key=key, value=value)
        db.session.add(row)
    else:
        row.value = value
