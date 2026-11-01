import cv2
import numpy as np

from app.forensics import imageforensics as imf
from app.forensics.types import Category, Page


def _textured(seed: int = 3, size: tuple[int, int] = (900, 1200)) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = rng.integers(60, 200, (size[0] // 8, size[1] // 8, 3), dtype=np.uint8)
    img = cv2.resize(base, (size[1], size[0]), interpolation=cv2.INTER_CUBIC)
    for _ in range(40):
        center = (int(rng.integers(0, size[1])), int(rng.integers(0, size[0])))
        color = tuple(int(c) for c in rng.integers(0, 255, 3))
        cv2.circle(img, center, int(rng.integers(8, 40)), color, -1)
    return img


def _stamp(img: np.ndarray, x: int, y: int, seed: int) -> None:
    rng = np.random.default_rng(seed)
    cv2.circle(img, (x, y), 70, (40, 40, 160), 4)
    cv2.circle(img, (x, y), 50, (40, 40, 160), 2)
    cv2.putText(img, "SEAL", (x - 45, y + 12), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (40, 40, 160), 3)
    pts = rng.integers(-60, 60, (25, 2))
    for dx, dy in pts:
        cv2.circle(img, (x + int(dx), y + int(dy)), 3, (40, 40, 160), -1)


def _paper(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.clip(rng.normal(238, 4, (1000, 800, 3)), 0, 255).astype(np.uint8)


def test_copy_move_detects_cloned_patch():
    img = _textured()
    img[600:760, 850:1050] = img[100:260, 100:300]
    findings = imf.copy_move(Page(number=1, image=img))
    assert findings and all(f.category == Category.COPY_MOVE for f in findings)
    boxes = [f.box for f in findings]
    assert any(abs(b[0] - 850) < 60 and abs(b[1] - 600) < 60 for b in boxes)


def test_copy_move_ignores_clean_image():
    assert imf.copy_move(Page(number=1, image=_textured())) == []


def test_noise_map_flags_regraded_region():
    img = _paper(5)
    smooth = cv2.GaussianBlur(img, (0, 0), 3)
    img[300:560, 250:560] = smooth[300:560, 250:560]
    layer, findings = imf.noise_map(Page(number=1, image=img))
    assert layer.shape == img.shape
    assert any(f.category == Category.NOISE and f.evidence["direction"] == "lower" for f in findings)


def test_noise_map_clean_paper_has_no_findings():
    _, findings = imf.noise_map(Page(number=1, image=_paper(6)))
    assert findings == []


def test_error_level_layer_matches_page():
    img = _paper(7)
    layer, _ = imf.error_level(Page(number=1, image=img))
    assert layer.shape == img.shape and layer.dtype == np.uint8


def test_identical_stamp_on_two_pages_is_flagged():
    first, second = _paper(10), _paper(11)
    _stamp(first, 400, 700, seed=1)
    second[620:780, 320:480] = first[620:780, 320:480]
    findings = imf.cross_page_copies([Page(number=1, image=first), Page(number=2, image=second)])
    assert {f.page for f in findings} == {1, 2}


def test_separately_stamped_pages_are_not_flagged():
    first, second = _paper(12), _paper(13)
    _stamp(first, 400, 700, seed=1)
    _stamp(second, 400, 700, seed=1)
    second = np.clip(second.astype(np.int16) + np.random.default_rng(2).normal(0, 6, second.shape), 0, 255).astype(np.uint8)
    findings = imf.cross_page_copies([Page(number=1, image=first), Page(number=2, image=second)])
    assert findings == []
