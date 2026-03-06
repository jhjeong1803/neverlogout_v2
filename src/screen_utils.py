"""
Shared screenshot and pixel-color checking utilities.

Used by Module 2 (his_keepalive) and Module 3 (intpc_keepalive) to detect
session timeout popups via pixel color matching.

Detection strategy
------------------
Rather than matching a single pixel, each module defines a list of
(x, y, expected_rgb) tuples (DETECTION_POINTS in constants.py). ALL points
must match within tolerance for a popup to be considered present. This
multi-point approach dramatically reduces false positives compared to
checking a single pixel.
"""

from PIL import Image, ImageGrab


def capture_screenshot() -> Image.Image:
    """
    Capture the full primary screen and return a PIL Image in RGB mode.

    On Windows, ImageGrab.grab() captures the virtual desktop.
    The returned image is always RGB (alpha channel stripped if present).
    """
    img = ImageGrab.grab()
    return img.convert("RGB")


def color_matches(
    actual: tuple[int, int, int],
    expected: tuple[int, int, int],
    tolerance: int,
) -> bool:
    """
    Return True if each RGB channel of *actual* is within *tolerance* of
    the corresponding channel of *expected*.

    Args:
        actual:    Measured (R, G, B) pixel value.
        expected:  Target (R, G, B) value from constants.
        tolerance: Maximum allowed difference per channel (inclusive).
    """
    return all(abs(a - e) <= tolerance for a, e in zip(actual, expected))


def check_detection_points(
    image: Image.Image,
    points: list[tuple[int, int, tuple[int, int, int]]],
    tolerance: int,
) -> bool:
    """
    Check all detection points against *image*. Returns True only if every
    point matches within tolerance — i.e., the popup is present.

    Args:
        image:     Full-screen PIL Image (RGB).
        points:    List of (x, y, expected_rgb) tuples from constants.py.
        tolerance: Per-channel tolerance passed to color_matches().

    Returns:
        True  — all points matched → popup detected.
        False — at least one point did not match → popup absent.
    """
    for x, y, expected in points:
        actual = image.getpixel((x, y))  # returns (R, G, B) after convert("RGB")
        if not color_matches(actual, expected, tolerance):
            return False
    return True
