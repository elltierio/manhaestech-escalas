from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from flask_login import current_user

from ..models import Assignment, Employee, Schedule, log_activity
from ..routes.auth import admin_required
from ..services.photo_service import save_employee_photo


employees_bp = Blueprint("employees", __name__, url_prefix="/employees")


@employees_bp.get("")
@login_required
def list_employees():
    q = (request.args.get("q") or "").strip()
    query = db.session.query(Employee)
    if q:
        query = query.filter(Employee.name.ilike(f"%{q}%"))
    employees = query.order_by(Employee.role.asc(), Employee.name.asc()).all()
    return render_template("employees.html", employees=employees, q=q)


@employees_bp.get("/new")
@admin_required
def new_employee():
    employee = Employee(name="", role="porteiro", squad="", is_extra=False, photo_path=None)
    return render_template("employee_edit.html", employee=employee)


@employees_bp.post("/new")
@admin_required
def new_employee_post():
    name = (request.form.get("name") or "").strip()
    role = request.form.get("role") or "porteiro"
    squad = (request.form.get("squad") or "").strip()
    is_extra = (request.form.get("is_extra") == "on")

    if not name:
        flash("Informe o nome.", "danger")
        return redirect(url_for("employees.new_employee"))

    employee = Employee(name=name, role=role, squad=squad, is_extra=is_extra)

    file = request.files.get("photo")
    if file and file.filename:
        try:
            employee.photo_path = save_employee_photo(file)
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for("employees.new_employee"))

    db.session.add(employee)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Já existe um funcionário com esse nome.", "danger")
        return redirect(url_for("employees.new_employee"))

    flash("Funcionário cadastrado.", "success")
    try:
        log_activity(
            actor_user_id=current_user.id,
            actor_username=current_user.username,
            action="create",
            entity="employee",
            entity_id=str(employee.id),
            ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            detail=f"name={employee.name};role={employee.role};squad={employee.squad};is_extra={employee.is_extra}",
        )
    except Exception:
        db.session.rollback()
    return redirect(url_for("employees.edit_employee", employee_id=employee.id))


@employees_bp.get("/<int:employee_id>")
@admin_required
def edit_employee(employee_id: int):
    employee = db.session.get(Employee, employee_id)
    if not employee:
        flash("Funcionário não encontrado.", "danger")
        return redirect(url_for("employees.list_employees"))
    return render_template("employee_edit.html", employee=employee)


@employees_bp.post("/<int:employee_id>")
@admin_required
def edit_employee_post(employee_id: int):
    employee = db.session.get(Employee, employee_id)
    if not employee:
        flash("Funcionário não encontrado.", "danger")
        return redirect(url_for("employees.list_employees"))

    employee.name = (request.form.get("name") or employee.name).strip()
    employee.role = request.form.get("role") or employee.role
    employee.squad = (request.form.get("squad") or employee.squad).strip()
    employee.is_extra = (request.form.get("is_extra") == "on")

    file = request.files.get("photo")
    if file and file.filename:
        try:
            employee.photo_path = save_employee_photo(file)
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for("employees.edit_employee", employee_id=employee_id))

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Já existe um funcionário com esse nome.", "danger")
        return redirect(url_for("employees.edit_employee", employee_id=employee_id))

    flash("Funcionário atualizado.", "success")
    try:
        log_activity(
            actor_user_id=current_user.id,
            actor_username=current_user.username,
            action="update",
            entity="employee",
            entity_id=str(employee.id),
            ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            detail=f"name={employee.name};role={employee.role};squad={employee.squad};is_extra={employee.is_extra}",
        )
    except Exception:
        db.session.rollback()
    return redirect(url_for("employees.edit_employee", employee_id=employee_id))


@employees_bp.post("/<int:employee_id>/delete")
@admin_required
def delete_employee_post(employee_id: int):
    employee = db.session.get(Employee, employee_id)
    if not employee:
        flash("Funcionário não encontrado.", "danger")
        return redirect(url_for("employees.list_employees"))

    schedules_using = (
        db.session.query(Schedule.id).filter(Schedule.manager_id == employee.id).first()
    )
    if schedules_using:
        flash(
            "Não é possível excluir este encarregado porque ele já está vinculado a escalas. Troque o encarregado nas escalas antes de excluir.",
            "danger",
        )
        return redirect(url_for("employees.edit_employee", employee_id=employee_id))

    db.session.query(Assignment).filter(Assignment.employee_id == employee.id).delete(
        synchronize_session=False
    )
    db.session.delete(employee)
    db.session.commit()
    flash("Funcionário excluído.", "success")
    try:
        log_activity(
            actor_user_id=current_user.id,
            actor_username=current_user.username,
            action="delete",
            entity="employee",
            entity_id=str(employee_id),
            ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            detail=None,
        )
    except Exception:
        db.session.rollback()
    return redirect(url_for("employees.list_employees"))
