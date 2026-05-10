from __future__ import annotations

import os
from datetime import date, timedelta

from dateutil.parser import isoparse
from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    jsonify,
    request,
    send_from_directory,
)
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Assignment, Employee, Schedule, log_activity
from ..routes.auth import admin_required
from ..services.pdf_service import build_schedule_pdf
from ..services.schedule_service import (
    add_employee,
    apply_status,
    get_or_create_schedule,
    remove_employee,
    substitute_employee,
    swap_employees,
    swap_managers,
)


api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.get("/events")
@login_required
def events():
    start = isoparse(request.args.get("start")).date()
    end = isoparse(request.args.get("end")).date()

    days = (end - start).days
    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        diurno = get_or_create_schedule(d, "diurno")
        noturno = get_or_create_schedule(d, "noturno")
        out.append(_event_for(diurno))
        out.append(_event_for(noturno))

    return jsonify(out)


def _event_for(s: Schedule) -> dict:
    color = "#2B7CFF" if s.shift == "diurno" else "#1E40AF"
    title = f"{s.display_shift}: {s.manager.name}"
    return {
        "id": f"{s.day.isoformat()}|{s.shift}",
        "title": title,
        "start": s.day.isoformat(),
        "allDay": True,
        "color": color,
        "extendedProps": {"shift": s.shift},
    }


@api_bp.get("/schedule")
@login_required
def schedule_detail():
    day_str = request.args.get("date") or date.today().isoformat()
    shift = request.args.get("shift") or "diurno"
    d = isoparse(day_str).date()
    s = get_or_create_schedule(d, shift)

    assigns = list(s.assignments or [])
    assigns.sort(key=lambda a: (0 if a.status == "titular" else 1, a.employee.name))

    return jsonify(
        {
            "id": s.id,
            "day": s.day.isoformat(),
            "shift": s.shift,
            "manager": _emp_payload(s.manager),
            "players": [
                {"employee": _emp_payload(a.employee), "status": a.status}
                for a in assigns
            ],
        }
    )


@api_bp.get("/employees")
@login_required
def employees():
    role = (request.args.get("role") or "").strip()
    query = db.session.query(Employee)
    if role:
        query = query.filter(Employee.role == role)
    emps = query.order_by(Employee.role.asc(), Employee.name.asc()).all()
    return jsonify([_emp_payload(e) for e in emps])


@api_bp.post("/schedule/manager")
@admin_required
def set_schedule_manager():
    payload = request.get_json(force=True)
    schedule_id = int(payload["scheduleId"])
    manager_id = int(payload["managerId"])

    schedule = db.session.get(Schedule, schedule_id)
    if not schedule:
        abort(404, "Escala não encontrada.")

    manager = db.session.get(Employee, manager_id)
    if not manager or manager.role != "encarregado":
        abort(400, "Encarregado inválido.")

    schedule.manager_id = manager.id
    db.session.commit()
    try:
        log_activity(
            actor_user_id=current_user.id,
            actor_username=current_user.username,
            action="update",
            entity="schedule",
            entity_id=str(schedule.id),
            ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            detail=f"set_manager={manager.id}",
        )
    except Exception:
        db.session.rollback()
    return jsonify({"ok": True})


@api_bp.post("/schedule/swap-managers")
@admin_required
def swap_schedule_managers():
    payload = request.get_json(force=True)
    schedule_id_a = int(payload["scheduleIdA"])
    schedule_id_b = int(payload["scheduleIdB"])
    try:
        swap_managers(schedule_id_a, schedule_id_b)
    except ValueError as e:
        abort(400, str(e))
    try:
        log_activity(
            actor_user_id=current_user.id,
            actor_username=current_user.username,
            action="update",
            entity="schedule",
            entity_id=f"{schedule_id_a}<->{schedule_id_b}",
            ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            detail="swap_managers",
        )
    except Exception:
        db.session.rollback()
    return jsonify({"ok": True})


def _emp_payload(e: Employee) -> dict:
    photo_url = None
    if e.photo_blob:
        photo_url = f"/api/employees/{e.id}/photo"
    elif e.photo_path:
        photo_url = f"/api/uploads/{e.photo_path}"
    return {
        "id": e.id,
        "name": e.name,
        "role": e.role,
        "squad": e.squad,
        "is_extra": e.is_extra,
        "photoUrl": photo_url,
    }


@api_bp.post("/assignment/status")
@admin_required
def set_assignment_status():
    payload = request.get_json(force=True)
    schedule_id = int(payload["scheduleId"])
    employee_id = int(payload["employeeId"])
    status = payload["status"]
    if status not in {"titular", "extra", "falta", "ferias"}:
        abort(400, "Status inválido.")

    apply_status(schedule_id, employee_id, status)
    try:
        log_activity(
            actor_user_id=current_user.id,
            actor_username=current_user.username,
            action="update",
            entity="assignment",
            entity_id=f"{schedule_id}:{employee_id}",
            ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            detail=f"status={status}",
        )
    except Exception:
        db.session.rollback()
    return jsonify({"ok": True})


@api_bp.post("/assignment/substitute")
@admin_required
def substitute():
    payload = request.get_json(force=True)
    schedule_id = int(payload["scheduleId"])
    absent_employee_id = int(payload["absentEmployeeId"])
    substitute_employee_id = int(payload["substituteEmployeeId"])
    substitute_employee(schedule_id, absent_employee_id, substitute_employee_id)
    try:
        log_activity(
            actor_user_id=current_user.id,
            actor_username=current_user.username,
            action="update",
            entity="schedule",
            entity_id=str(schedule_id),
            ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            detail=f"substitute absent={absent_employee_id} new={substitute_employee_id}",
        )
    except Exception:
        db.session.rollback()
    return jsonify({"ok": True})


@api_bp.post("/assignment/swap")
@admin_required
def swap_assignment():
    payload = request.get_json(force=True)
    schedule_id_a = int(payload["scheduleIdA"])
    employee_id_a = int(payload["employeeIdA"])
    schedule_id_b = int(payload["scheduleIdB"])
    employee_id_b = int(payload["employeeIdB"])
    try:
        swap_employees(schedule_id_a, employee_id_a, schedule_id_b, employee_id_b)
    except ValueError as e:
        abort(400, str(e))
    try:
        log_activity(
            actor_user_id=current_user.id,
            actor_username=current_user.username,
            action="update",
            entity="assignment",
            entity_id=f"{schedule_id_a}:{employee_id_a}<->{schedule_id_b}:{employee_id_b}",
            ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            detail="swap",
        )
    except Exception:
        db.session.rollback()
    return jsonify({"ok": True})


@api_bp.post("/assignment/remove")
@admin_required
def remove_assignment():
    payload = request.get_json(force=True)
    schedule_id = int(payload["scheduleId"])
    employee_id = int(payload["employeeId"])
    remove_employee(schedule_id, employee_id)
    try:
        log_activity(
            actor_user_id=current_user.id,
            actor_username=current_user.username,
            action="delete",
            entity="assignment",
            entity_id=f"{schedule_id}:{employee_id}",
            ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            detail="removed_from_schedule",
        )
    except Exception:
        db.session.rollback()
    return jsonify({"ok": True})


@api_bp.post("/assignment/add")
@admin_required
def add_assignment():
    payload = request.get_json(force=True)
    schedule_id = int(payload["scheduleId"])
    employee_id = int(payload["employeeId"])
    status = payload.get("status")

    schedule = db.session.get(Schedule, schedule_id)
    if not schedule:
        abort(404, "Escala não encontrada.")

    try:
        add_employee(schedule_id, employee_id, status=status)
    except ValueError as e:
        abort(400, str(e))

    try:
        log_activity(
            actor_user_id=current_user.id,
            actor_username=current_user.username,
            action="create",
            entity="assignment",
            entity_id=f"{schedule_id}:{employee_id}",
            ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            detail=f"added_to_schedule;status={status or ''}",
        )
    except Exception:
        db.session.rollback()

    return jsonify({"ok": True})


@api_bp.get("/pdf")
@login_required
def pdf():
    day_str = request.args.get("date") or date.today().isoformat()
    shift = request.args.get("shift") or "diurno"
    d = isoparse(day_str).date()
    s = get_or_create_schedule(d, shift)

    data = build_schedule_pdf(s)
    filename = f"Escala-{s.display_shift}-{s.day.strftime('%Y-%m-%d')}.pdf"
    return Response(
        data,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@api_bp.get("/uploads/<path:filename>")
@login_required
def uploads(filename: str):
    upload_dir = current_app.config["UPLOAD_DIR"]
    if not os.path.abspath(os.path.join(upload_dir, filename)).startswith(
        os.path.abspath(upload_dir)
    ):
        abort(400)
    return send_from_directory(upload_dir, filename)


@api_bp.get("/employees/<int:employee_id>/photo")
@login_required
def employee_photo(employee_id: int):
    emp = db.session.get(Employee, employee_id)
    if not emp:
        abort(404)

    if emp.photo_blob:
        raw = emp.photo_blob
        if isinstance(raw, memoryview):
            raw = raw.tobytes()
        return Response(raw, mimetype=emp.photo_mime or "image/jpeg")

    if emp.photo_path:
        upload_dir = current_app.config["UPLOAD_DIR"]
        if not os.path.abspath(os.path.join(upload_dir, emp.photo_path)).startswith(
            os.path.abspath(upload_dir)
        ):
            abort(400)
        return send_from_directory(upload_dir, emp.photo_path)

    abort(404)
