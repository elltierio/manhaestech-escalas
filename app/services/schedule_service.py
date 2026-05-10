from __future__ import annotations

from datetime import date, datetime

from dateutil.parser import isoparse

from ..extensions import db
from ..models import Assignment, Employee, Schedule, get_setting


def get_or_create_schedule(day: date, shift: str) -> Schedule:
    schedule = (
        db.session.query(Schedule)
        .filter(Schedule.day == day, Schedule.shift == shift)
        .first()
    )
    if schedule:
        return schedule

    manager = _pick_manager(day, shift)
    schedule = Schedule(day=day, shift=shift, manager_id=manager.id)
    db.session.add(schedule)
    db.session.flush()

    staff_count = int(get_setting("schedule.staff_count", "7") or "7")
    staff = _pick_staff(manager_squad=manager.name, desired_count=staff_count)
    for emp in staff:
        status = "extra" if emp.is_extra else "titular"
        db.session.add(
            Assignment(schedule_id=schedule.id, employee_id=emp.id, status=status)
        )

    db.session.commit()
    return schedule


def _pick_manager(day: date, shift: str) -> Employee:
    base_date_str = get_setting("schedule.base_date")
    base_date = isoparse(base_date_str).date() if base_date_str else date.today()

    order_key = "schedule.diurno_order" if shift == "diurno" else "schedule.noturno_order"
    order_raw = get_setting(order_key, "") or ""
    order = [p.strip() for p in order_raw.split("|") if p.strip()]
    if not order:
        order = ["Felipe Manhães"] if shift == "diurno" else ["Allan Garcia"]

    idx = (day - base_date).days % len(order)
    manager_name = order[idx]

    manager = (
        db.session.query(Employee)
        .filter(Employee.role == "encarregado", Employee.name == manager_name)
        .first()
    )
    if not manager:
        manager = Employee(name=manager_name, role="encarregado", squad=manager_name)
        db.session.add(manager)
        db.session.flush()
    return manager


def _pick_staff(manager_squad: str, desired_count: int) -> list[Employee]:
    fixed = (
        db.session.query(Employee)
        .filter(
            Employee.role == "porteiro",
            Employee.squad == manager_squad,
            Employee.is_extra.is_(False),
        )
        .order_by(Employee.name.asc())
        .all()
    )

    staff: list[Employee] = fixed[:desired_count]
    if len(staff) >= desired_count:
        return staff[:desired_count]

    extras = (
        db.session.query(Employee)
        .filter(
            Employee.role == "porteiro",
            (Employee.is_extra.is_(True)) | (Employee.squad == "Banco de Extras"),
        )
        .order_by(Employee.is_extra.desc(), Employee.name.asc())
        .all()
    )
    used_ids = {e.id for e in staff}
    for emp in extras:
        if len(staff) >= desired_count:
            break
        if emp.id in used_ids:
            continue
        staff.append(emp)
        used_ids.add(emp.id)

    return staff[:desired_count]


def apply_status(schedule_id: int, employee_id: int, status: str) -> None:
    assignment = (
        db.session.query(Assignment)
        .filter(
            Assignment.schedule_id == schedule_id,
            Assignment.employee_id == employee_id,
        )
        .first()
    )
    if not assignment:
        db.session.add(
            Assignment(
                schedule_id=schedule_id,
                employee_id=employee_id,
                status=status,
            )
        )
    else:
        assignment.status = status
    db.session.commit()


def substitute_employee(
    schedule_id: int, absent_employee_id: int, substitute_employee_id: int
) -> None:
    apply_status(schedule_id, absent_employee_id, "falta")
    if absent_employee_id == substitute_employee_id:
        return

    schedule = db.session.get(Schedule, schedule_id)
    manager_squad = None
    if schedule:
        manager = db.session.get(Employee, schedule.manager_id)
        manager_squad = manager.name if manager else None

    sub = db.session.get(Employee, substitute_employee_id)
    status = "titular"
    if sub:
        if sub.role == "encarregado":
            status = "extra"
        elif sub.is_extra or sub.squad == "Banco de Extras":
            status = "extra"
        elif manager_squad and sub.squad != manager_squad:
            status = "extra"
    apply_status(schedule_id, substitute_employee_id, status)


def remove_employee(schedule_id: int, employee_id: int) -> None:
    assignment = (
        db.session.query(Assignment)
        .filter(
            Assignment.schedule_id == schedule_id,
            Assignment.employee_id == employee_id,
        )
        .first()
    )
    if assignment:
        db.session.delete(assignment)
        db.session.commit()


def add_employee(schedule_id: int, employee_id: int, status: str | None = None) -> None:
    existing = (
        db.session.query(Assignment.id)
        .filter(
            Assignment.schedule_id == schedule_id,
            Assignment.employee_id == employee_id,
        )
        .first()
    )
    if existing:
        return

    emp = db.session.get(Employee, employee_id)
    if not emp or emp.role not in {"porteiro", "encarregado"}:
        raise ValueError("Funcionário inválido.")

    st = status
    if not st:
        schedule = db.session.get(Schedule, schedule_id)
        manager_squad = None
        if schedule:
            manager = db.session.get(Employee, schedule.manager_id)
            manager_squad = manager.name if manager else None

        if emp.role == "encarregado":
            st = "extra"
        elif emp.is_extra or emp.squad == "Banco de Extras":
            st = "extra"
        elif manager_squad and emp.squad != manager_squad:
            st = "extra"
        else:
            st = "titular"
    elif emp.role == "encarregado":
        st = "extra"
    if st not in {"titular", "extra", "falta", "ferias"}:
        raise ValueError("Status inválido.")

    db.session.add(
        Assignment(
            schedule_id=schedule_id,
            employee_id=employee_id,
            status=st,
        )
    )
    db.session.commit()


def swap_employees(
    schedule_id_a: int,
    employee_id_a: int,
    schedule_id_b: int,
    employee_id_b: int,
) -> None:
    if schedule_id_a == schedule_id_b and employee_id_a == employee_id_b:
        return

    a = (
        db.session.query(Assignment)
        .filter(
            Assignment.schedule_id == schedule_id_a,
            Assignment.employee_id == employee_id_a,
        )
        .first()
    )
    b = (
        db.session.query(Assignment)
        .filter(
            Assignment.schedule_id == schedule_id_b,
            Assignment.employee_id == employee_id_b,
        )
        .first()
    )
    if not a or not b:
        raise ValueError("Troca inválida: funcionário não encontrado na escala.")

    status_a = a.status
    status_b = b.status

    db.session.delete(a)
    db.session.delete(b)
    db.session.flush()

    db.session.add(
        Assignment(
            schedule_id=schedule_id_a,
            employee_id=employee_id_b,
            status=status_a,
        )
    )
    db.session.add(
        Assignment(
            schedule_id=schedule_id_b,
            employee_id=employee_id_a,
            status=status_b,
        )
    )
    db.session.commit()


def swap_managers(schedule_id_a: int, schedule_id_b: int) -> None:
    if schedule_id_a == schedule_id_b:
        return

    a = db.session.get(Schedule, schedule_id_a)
    b = db.session.get(Schedule, schedule_id_b)
    if not a or not b:
        raise ValueError("Troca inválida: escala não encontrada.")

    a.manager_id, b.manager_id = b.manager_id, a.manager_id
    db.session.commit()
