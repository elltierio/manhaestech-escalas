from __future__ import annotations

from pathlib import Path
import io

from PIL import Image, ImageOps


ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def process_employee_photo(file_storage) -> tuple[bytes, str]:
    ext = Path(file_storage.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Formato de imagem não suportado.")

    img = Image.open(file_storage.stream)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = _crop_square_center(img)
    img = img.resize((512, 512), Image.LANCZOS)

    bio = io.BytesIO()
    img.save(bio, format="JPEG", quality=90, optimize=True)
    return bio.getvalue(), "image/jpeg"


def process_employee_photo_path(path: str | Path) -> tuple[bytes, str]:
    p = Path(path)
    ext = p.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Formato de imagem não suportado.")

    with p.open("rb") as f:
        img = Image.open(f)
        img = ImageOps.exif_transpose(img).convert("RGB")
        img = _crop_square_center(img)
        img = img.resize((512, 512), Image.LANCZOS)

        bio = io.BytesIO()
        img.save(bio, format="JPEG", quality=90, optimize=True)
        return bio.getvalue(), "image/jpeg"


def _crop_square_center(img: Image.Image) -> Image.Image:
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    right = left + side
    bottom = top + side
    return img.crop((left, top, right, bottom))
