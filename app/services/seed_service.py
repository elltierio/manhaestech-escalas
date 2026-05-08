from __future__ import annotations

import os
from datetime import date

from ..extensions import db
from ..models import Employee, User, get_setting, set_setting


def seed_if_needed() -> None:
    if db.session.query(User.id).first():
        return

    admin_user = User(username=os.environ.get("ADMIN_USERNAME", "admin"), is_admin=True)
    admin_user.set_password(os.environ.get("ADMIN_PASSWORD", "admin"))
    db.session.add(admin_user)

    if not get_setting("schedule.base_date"):
        set_setting("schedule.base_date", date.today().isoformat())
    if not get_setting("schedule.diurno_order"):
        set_setting(
            "schedule.diurno_order", "Felipe Manhães|Thiago Nascimento"
        )
    if not get_setting("schedule.noturno_order"):
        set_setting("schedule.noturno_order", "Allan Garcia|Joabe Alves")
    if not get_setting("schedule.staff_count"):
        set_setting("schedule.staff_count", "7")

    _seed_employees()

    db.session.commit()


def _seed_employees() -> None:
    employees: list[Employee] = []

    def add_employee(
        name: str,
        role: str,
        squad: str,
        is_extra: bool = False,
    ) -> None:
        employees.append(
            Employee(name=name, role=role, squad=squad, is_extra=is_extra)
        )

    squads = [
        "Felipe Manhães",
        "Allan Garcia",
        "Thiago Nascimento",
        "Joabe Alves",
    ]

    for squad in squads:
        add_employee(squad, "encarregado", squad, is_extra=False)

    add_employee("Rondinelli", "porteiro", "Felipe Manhães")
    add_employee("Allan Garcia (Extra)", "porteiro", "Banco de Extras", is_extra=True)
    add_employee("Ricardo (Extra)", "porteiro", "Banco de Extras", is_extra=True)
    add_employee("Meirelles (Extra)", "porteiro", "Banco de Extras", is_extra=True)
    add_employee("Mousinho", "porteiro", "Felipe Manhães")
    add_employee("Aroudo", "porteiro", "Felipe Manhães")
    add_employee("Matias", "porteiro", "Felipe Manhães")

    add_employee("Botelho", "porteiro", "Allan Garcia")
    add_employee("Leonardo", "porteiro", "Allan Garcia")
    add_employee("Willams", "porteiro", "Allan Garcia")
    add_employee("Mattos", "porteiro", "Allan Garcia")
    add_employee("Da Silva", "porteiro", "Allan Garcia")
    add_employee("Silva", "porteiro", "Allan Garcia")
    add_employee("Viera", "porteiro", "Allan Garcia")

    add_employee("Gilberto", "porteiro", "Thiago Nascimento")
    add_employee("Joabe Alves (Extra)", "porteiro", "Banco de Extras", is_extra=True)
    add_employee("Douglas", "porteiro", "Thiago Nascimento")
    add_employee("Luciano", "porteiro", "Thiago Nascimento")

    add_employee("Mariz", "porteiro", "Joabe Alves")
    add_employee("Guilherme", "porteiro", "Joabe Alves")
    add_employee("Alexandre", "porteiro", "Joabe Alves")
    add_employee("Henrique", "porteiro", "Joabe Alves")
    add_employee("Fernando", "porteiro", "Joabe Alves")
    add_employee("Júlio", "porteiro", "Joabe Alves")

    existing_names = {name for (name,) in db.session.query(Employee.name).all()}
    for emp in employees:
        if emp.name in existing_names:
            continue
        db.session.add(emp)
