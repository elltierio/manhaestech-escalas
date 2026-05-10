from __future__ import annotations

import io
import os
from dataclasses import dataclass
from math import cos, pi, sin

from flask import current_app
from PIL import Image, ImageDraw, ImageOps
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from ..models import Assignment, Employee, Schedule


@dataclass(frozen=True)
class PdfPlayer:
    employee: Employee
    status: str


def build_schedule_pdf(schedule: Schedule) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    _draw_background(c, width, height)
    _draw_header(c, schedule, width, height)
    _draw_lineup(c, schedule, width, height)
    _draw_footer(c, width)

    c.showPage()
    c.save()
    return buf.getvalue()


def _draw_background(c: canvas.Canvas, w: float, h: float) -> None:
    c.setFillColorRGB(0.04, 0.06, 0.10)
    c.rect(0, 0, w, h, fill=1, stroke=0)

    c.setStrokeColorRGB(0.10, 0.20, 0.40)
    c.setLineWidth(1)
    for i in range(1, 8):
        c.line(36, i * (h / 8), w - 36, i * (h / 8))


def _draw_header(c: canvas.Canvas, schedule: Schedule, w: float, h: float) -> None:
    c.setFillColorRGB(0.85, 0.92, 1.0)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(36, h - 54, "ManhãesTech Escalas")

    c.setFont("Helvetica", 12)
    label = f"{schedule.day.strftime('%d/%m/%Y')}  •  {schedule.display_shift}  ({_shift_hours(schedule.shift)})"
    c.drawString(36, h - 76, label)


def _draw_footer(c: canvas.Canvas, w: float) -> None:
    c.setFillColorRGB(0.65, 0.75, 0.90)
    c.setFont("Helvetica", 10)
    c.drawCentredString(w / 2, 24, "Felipe Manhães / ManhãesTech")


def _shift_hours(shift: str) -> str:
    return "07:00–19:00" if shift == "diurno" else "19:00–07:00"


def _draw_lineup(c: canvas.Canvas, schedule: Schedule, w: float, h: float) -> None:
    players = _schedule_players(schedule)

    center_x = w / 2
    center_y = h / 2 + 40

    manager = schedule.manager
    _draw_person_card(
        c,
        manager,
        status="titular",
        x=center_x,
        y=center_y,
        radius=50,
        title="Encarregado",
    )

    ring_r = 220
    angle_start = -pi / 2
    for i, p in enumerate(players):
        angle = angle_start + (2 * pi * i / max(1, len(players)))
        x = center_x + ring_r * cos(angle)
        y = center_y + ring_r * sin(angle)
        _draw_person_card(c, p.employee, p.status, x=x, y=y, radius=38, title=None)


def _schedule_players(schedule: Schedule) -> list[PdfPlayer]:
    assigns: list[Assignment] = list(schedule.assignments or [])
    assigns.sort(key=lambda a: (0 if a.status == "titular" else 1, a.employee.name))
    return [PdfPlayer(employee=a.employee, status=a.status) for a in assigns]


def _draw_person_card(
    c: canvas.Canvas,
    emp: Employee,
    status: str,
    x: float,
    y: float,
    radius: int,
    title: str | None,
) -> None:
    ring_color = _status_color(status)
    c.setStrokeColorRGB(*ring_color)
    c.setLineWidth(4)
    c.circle(x, y, radius + 4, stroke=1, fill=0)

    img = _load_avatar_circle(emp)
    if img:
        c.drawImage(img, x - radius, y - radius, 2 * radius, 2 * radius, mask="auto")
    else:
        c.setFillColorRGB(0.10, 0.15, 0.22)
        c.circle(x, y, radius, stroke=0, fill=1)
        c.setFillColorRGB(0.85, 0.92, 1.0)
        c.setFont("Helvetica-Bold", 10)
        initials = _initials(emp.name)
        c.drawCentredString(x, y - 4, initials)

    c.setFillColorRGB(0.92, 0.96, 1.0)
    c.setFont("Helvetica", 10 if not title else 11)
    if title:
        c.drawCentredString(x, y + radius + 22, title)
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(x, y - radius - 18, emp.name)
    else:
        c.drawCentredString(x, y - radius - 16, emp.name)


def _status_color(status: str) -> tuple[float, float, float]:
    if status == "extra":
        return (0.98, 0.80, 0.20)
    if status == "ferias":
        return (1.00, 0.54, 0.00)
    if status == "falta":
        return (0.95, 0.25, 0.25)
    return (0.20, 0.55, 1.00)


def _initials(name: str) -> str:
    parts = [p for p in name.replace("(", "").replace(")", "").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _load_avatar_circle(emp: Employee) -> ImageReader | None:
    img = None
    if emp.photo_blob:
        try:
            raw = emp.photo_blob
            if isinstance(raw, memoryview):
                raw = raw.tobytes()
            img = Image.open(io.BytesIO(raw))
        except Exception:
            img = None

    if img is None and emp.photo_path:
        upload_dir = current_app.config["UPLOAD_DIR"]
        abs_path = os.path.join(upload_dir, emp.photo_path)
        if os.path.exists(abs_path):
            try:
                img = Image.open(abs_path)
            except Exception:
                img = None

    if img is None:
        return None

    img = ImageOps.exif_transpose(img).convert("RGB").resize((256, 256), Image.LANCZOS)
    mask = Image.new("L", (256, 256), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, 256, 256), fill=255)

    out = Image.new("RGBA", (256, 256))
    out.paste(img, (0, 0))
    out.putalpha(mask)

    bio = io.BytesIO()
    out.save(bio, format="PNG")
    bio.seek(0)
    return ImageReader(bio)
