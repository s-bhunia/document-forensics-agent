import cv2
import numpy as np

from app.forensics.textfeatures import is_tall, measure_word, to_lab
from app.forensics.types import Word
from tests.synth import font, render


def _measure(text: str, fname: str, size: int = 40) -> dict:
    img = render([[(text, fname, size)]], width=900, margin=40)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    ys, xs = np.nonzero(gray < 128)
    box = (int(xs.min()), int(ys.min()), int(np.ptp(xs)) + 1, int(np.ptp(ys)) + 1)
    feats = measure_word(gray, to_lab(img), Word(text=text, box=box, line_id="l"))
    assert feats is not None
    return feats


def test_bold_is_heavier_than_regular():
    regular = _measure("HANDBOOK", "sans")
    bold = _measure("HANDBOOK", "sans-bold")
    assert bold["weight"] > regular["weight"] * 1.3


def test_serif_has_more_stroke_contrast_than_sans():
    serif = _measure("Research", "serif")
    sans = _measure("Research", "sans")
    assert serif["modulation"] > sans["modulation"] + 0.05


def test_letter_height_scales_with_font_size():
    small = _measure("ABCD", "sans", 30)
    large = _measure("ABCD", "sans", 45)
    assert 1.35 < large["cap_height"] / small["cap_height"] < 1.65


def test_ink_contrast_and_tall_detection():
    feats = _measure("Level", "serif")
    assert feats["contrast"] > 60
    assert is_tall("Level") and not is_tall("ocean")


def test_tiny_box_is_ignored():
    img = np.full((40, 40, 3), 250, np.uint8)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    assert measure_word(gray, to_lab(img), Word(text="ab", box=(10, 10, 3, 3), line_id="l")) is None
    assert font("sans", 20) is not None
