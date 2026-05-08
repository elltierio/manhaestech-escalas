from __future__ import annotations

from datetime import date

from dateutil.parser import isoparse
from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from ..services.schedule_service import get_or_create_schedule


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
def root():
    return redirect(url_for("dashboard.dashboard"))


@dashboard_bp.get("/dashboard")
@login_required
def dashboard():
    day_str = request.args.get("date") or date.today().isoformat()
    day = isoparse(day_str).date()

    diurno = get_or_create_schedule(day, "diurno")
    noturno = get_or_create_schedule(day, "noturno")

    return render_template("dashboard.html", day=day, diurno=diurno, noturno=noturno)
