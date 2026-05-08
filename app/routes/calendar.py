from __future__ import annotations

from flask import Blueprint, render_template
from flask_login import login_required


calendar_bp = Blueprint("calendar", __name__, url_prefix="/calendar")


@calendar_bp.get("")
@login_required
def calendar_view():
    return render_template("calendar.html")
