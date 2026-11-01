from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_DIRS = [Path("/usr/share/fonts/truetype"), Path("C:/Windows/Fonts")]
FONT_FILES = {
    "serif": ["liberation/LiberationSerif-Regular.ttf", "times.ttf"],
    "serif-bold": ["liberation/LiberationSerif-Bold.ttf", "timesbd.ttf"],
    "sans": ["liberation/LiberationSans-Regular.ttf", "arial.ttf"],
    "sans-bold": ["liberation/LiberationSans-Bold.ttf", "arialbd.ttf"],
    "dejavu": ["dejavu/DejaVuSans.ttf"],
    "dejavu-bold": ["dejavu/DejaVuSans-Bold.ttf"],
}

Segment = tuple[str, str, int]


@lru_cache
def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    for base in FONT_DIRS:
        for rel in FONT_FILES[name]:
            path = base / rel
            if path.exists():
                return ImageFont.truetype(str(path), size)
    raise FileNotFoundError(name)


def render(lines: list[list[Segment]], width: int = 1600, margin: int = 80, gap: int = 34, spacing: float = 0.0) -> np.ndarray:
    heights = [max(font(f, s).size for _, f, s in line) for line in lines]
    height = margin * 2 + sum(h + gap for h in heights)
    img = Image.new("RGB", (width, height), (250, 250, 247))
    draw = ImageDraw.Draw(img)
    y = margin
    for line, h in zip(lines, heights):
        x = margin
        for text, fname, size in line:
            f = font(fname, size)
            if spacing:
                for ch in text:
                    draw.text((x, y), ch, font=f, fill=(25, 25, 30))
                    x += f.getlength(ch) + spacing
            else:
                draw.text((x, y), text, font=f, fill=(25, 25, 30))
                x += f.getlength(text)
            x += f.getlength(" ")
        y += h + gap
    return np.array(img)


def scan(rgb: np.ndarray, seed: int = 1, blur: float = 0.6, noise: float = 3.0, quality: int = 88) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = cv2.GaussianBlur(rgb, (0, 0), blur).astype(np.float32)
    out += rng.normal(0, noise, out.shape)
    out = np.clip(out, 0, 255).astype(np.uint8)
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(out, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, quality])
    return cv2.cvtColor(cv2.imdecode(buf, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)


def to_bytes(rgb: np.ndarray, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format=fmt)
    return buf.getvalue()


def words(text: str, fname: str, size: int) -> list[Segment]:
    return [(w, fname, size) for w in text.split()]


BODY = [
    "The University has no objection to the student carrying out the program",
    "at your esteemed organization for the period mentioned in this letter",
    "and requests you to extend the usual support and guidance to the student",
    "during the internship period except on internal and semester exam dates",
]
