from __future__ import annotations

import os
import secrets
from pathlib import Path

from flask import current_app
from PIL import Image, ImageOps


ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def save_employee_photo(file_storage) -> str:
    ext = Path(file_storage.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Formato de imagem não suportado.")

    upload_dir = current_app.config["UPLOAD_DIR"]
    os.makedirs(upload_dir, exist_ok=True)

    filename = f"{secrets.token_hex(16)}{ext}"
    abs_path = os.path.join(upload_dir, filename)

    img = Image.open(file_storage.stream)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = _crop_square_center(img)
    img = img.resize((512, 512), Image.LANCZOS)
    img.save(abs_path, format="JPEG", quality=90, optimize=True)

    return filename


def _crop_square_center(img: Image.Image) -> Image.Image:
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    right = left + side
    bottom = top + side
    return img.crop((left, top, right, bottom))
