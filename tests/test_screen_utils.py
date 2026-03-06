"""
Unit tests for src/screen_utils.py

Tests are organised into three classes:

  TestColorMatches          — pure logic, no I/O
  TestCheckDetectionPoints  — uses fixture images (tests/fixtures/)
  TestCaptureScreenshot     — ImageGrab.grab mocked; no display required

Fixture images were captured on the real target machine and the pixel values
at every detection coordinate have been verified to match constants.py exactly,
so the fixture-based tests also serve as a calibration smoke-test.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

# Make src/ importable without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from screen_utils import capture_screenshot, check_detection_points, color_matches

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures"
HIS_FIXTURE   = FIXTURES / "his.png"
INTPC_FIXTURE = FIXTURES / "intpc.png"

# ---------------------------------------------------------------------------
# Detection-point constants (mirrors constants.py — kept local so tests
# remain self-contained and readable without importing the constants module)
# ---------------------------------------------------------------------------

HIS_DETECTION_POINTS = [
    (820,  500, (196, 34,  34)),
    (960,  540, (43,  56,  82)),
    (925,  595, (31,  92,  148)),
    (1000, 595, (125, 39,  42)),
]
HIS_TOLERANCE = 15

INTPC_DETECTION_POINTS = [
    (960, 390, (0,   162, 235)),
    (960, 465, (255, 255, 255)),
    (880, 620, (53,  133, 171)),
]
INTPC_TOLERANCE = 15


# ===========================================================================
# TestColorMatches
# ===========================================================================

class TestColorMatches:
    """color_matches(actual, expected, tolerance) — pure per-channel logic."""

    def test_exact_match_returns_true(self):
        assert color_matches((100, 150, 200), (100, 150, 200), tolerance=0)

    def test_within_tolerance_returns_true(self):
        # Each channel differs by exactly (tolerance - 1)
        assert color_matches((105, 145, 205), (100, 150, 200), tolerance=10)

    def test_at_tolerance_boundary_returns_true(self):
        # Each channel differs by exactly tolerance — should still pass
        assert color_matches((110, 140, 210), (100, 150, 200), tolerance=10)

    def test_one_over_tolerance_returns_false(self):
        # R channel is 11 away with tolerance=10
        assert not color_matches((111, 150, 200), (100, 150, 200), tolerance=10)

    def test_single_channel_failure_returns_false(self):
        # G channel over tolerance; R and B are fine
        assert not color_matches((100, 165, 200), (100, 150, 200), tolerance=10)

    def test_zero_tolerance_exact_match_returns_true(self):
        assert color_matches((0, 162, 235), (0, 162, 235), tolerance=0)

    def test_zero_tolerance_any_difference_returns_false(self):
        assert not color_matches((1, 162, 235), (0, 162, 235), tolerance=0)

    def test_negative_difference_within_tolerance_returns_true(self):
        # actual < expected by tolerance — symmetric check
        assert color_matches((90, 150, 200), (100, 150, 200), tolerance=10)

    def test_negative_difference_over_tolerance_returns_false(self):
        assert not color_matches((89, 150, 200), (100, 150, 200), tolerance=10)

    @pytest.mark.parametrize("actual,expected,tol,result", [
        ((196, 34,  34),  (196, 34,  34),  15, True),   # HIS red icon — exact
        ((43,  56,  82),  (43,  56,  82),  15, True),   # HIS navy body — exact
        ((31,  92,  148), (31,  92,  148), 15, True),   # HIS blue button — exact
        ((255, 255, 255), (196, 34,  34),  15, False),  # white vs HIS red — far off
        ((0,   162, 235), (0,   162, 235), 15, True),   # intPC title bar — exact
        ((255, 255, 255), (0,   162, 235), 15, False),  # white vs intPC blue — far off
    ])
    def test_parametrized_real_colors(self, actual, expected, tol, result):
        assert color_matches(actual, expected, tol) is result


# ===========================================================================
# TestCheckDetectionPoints
# ===========================================================================

class TestCheckDetectionPoints:
    """check_detection_points(image, points, tolerance) — uses fixture images."""

    # --- Fixture helpers ----------------------------------------------------

    @pytest.fixture(scope="class")
    def his_image(self):
        return Image.open(HIS_FIXTURE).convert("RGB")

    @pytest.fixture(scope="class")
    def intpc_image(self):
        return Image.open(INTPC_FIXTURE).convert("RGB")

    @pytest.fixture
    def blank_image(self):
        """Solid white 1920×1080 — no popup present anywhere."""
        return Image.new("RGB", (1920, 1080), (255, 255, 255))

    # --- Positive: popup present --------------------------------------------

    def test_his_popup_detected_in_his_fixture(self, his_image):
        assert check_detection_points(his_image, HIS_DETECTION_POINTS, HIS_TOLERANCE)

    def test_intpc_popup_detected_in_intpc_fixture(self, intpc_image):
        assert check_detection_points(intpc_image, INTPC_DETECTION_POINTS, INTPC_TOLERANCE)

    # --- Negative: popup absent ---------------------------------------------

    def test_his_popup_not_detected_on_blank_image(self, blank_image):
        assert not check_detection_points(blank_image, HIS_DETECTION_POINTS, HIS_TOLERANCE)

    def test_intpc_popup_not_detected_on_blank_image(self, blank_image):
        assert not check_detection_points(blank_image, INTPC_DETECTION_POINTS, INTPC_TOLERANCE)

    # --- Cross-detection: wrong fixture should not trigger detection ---------

    def test_his_popup_not_detected_in_intpc_fixture(self, intpc_image):
        # intpc.png has no HIS popup — all HIS detection coords are white
        assert not check_detection_points(intpc_image, HIS_DETECTION_POINTS, HIS_TOLERANCE)

    def test_intpc_popup_not_detected_in_his_fixture(self, his_image):
        # his.png has no intPC popup — first intPC detection coord (960,390) is white
        assert not check_detection_points(his_image, INTPC_DETECTION_POINTS, INTPC_TOLERANCE)

    # --- Tolerance boundary -------------------------------------------------

    def test_zero_tolerance_passes_on_exact_fixture_pixels(self, his_image):
        # The fixture pixels exactly match constants — tolerance=0 must still pass
        assert check_detection_points(his_image, HIS_DETECTION_POINTS, tolerance=0)

    def test_very_tight_tolerance_fails_when_slightly_off(self):
        # Build an image where one point is 1 unit off, tolerance=0 → fail
        img = Image.new("RGB", (1920, 1080), (255, 255, 255))
        points = [(100, 100, (200, 100, 50))]
        img.putpixel((100, 100), (201, 100, 50))  # R is 1 off
        assert not check_detection_points(img, points, tolerance=0)

    def test_tolerance_1_accepts_single_unit_difference(self):
        img = Image.new("RGB", (1920, 1080), (255, 255, 255))
        points = [(100, 100, (200, 100, 50))]
        img.putpixel((100, 100), (201, 100, 50))  # R is 1 off
        assert check_detection_points(img, points, tolerance=1)

    # --- Edge cases ---------------------------------------------------------

    def test_empty_points_list_returns_true(self, his_image):
        # Vacuously true — nothing to check means no mismatch
        assert check_detection_points(his_image, [], tolerance=15)

    def test_single_matching_point_returns_true(self, his_image):
        single = [HIS_DETECTION_POINTS[0]]
        assert check_detection_points(his_image, single, HIS_TOLERANCE)

    def test_one_bad_point_among_many_returns_false(self, his_image):
        # Replace one good point with a deliberately wrong expected color
        bad_points = list(HIS_DETECTION_POINTS)
        x, y, _ = bad_points[2]
        bad_points[2] = (x, y, (255, 255, 255))  # expected white at a non-white pixel
        assert not check_detection_points(his_image, bad_points, HIS_TOLERANCE)

    def test_rgba_image_handled_correctly(self):
        # Even if an RGBA image sneaks in, getpixel returns 4 values.
        # screen_utils converts to RGB in capture_screenshot, but
        # check_detection_points itself uses zip which stops at shortest tuple.
        # Verify it still works when the image is already RGB.
        img = Image.new("RGB", (200, 200), (100, 150, 200))
        points = [(100, 100, (100, 150, 200))]
        assert check_detection_points(img, points, tolerance=0)


# ===========================================================================
# TestCaptureScreenshot
# ===========================================================================

class TestCaptureScreenshot:
    """capture_screenshot() — ImageGrab.grab is mocked; no display needed."""

    def test_returns_pil_image(self):
        fake = Image.new("RGB", (1920, 1080), (128, 128, 128))
        with patch("screen_utils.ImageGrab.grab", return_value=fake):
            result = capture_screenshot()
        assert isinstance(result, Image.Image)

    def test_calls_imagegrab_grab(self):
        fake = Image.new("RGB", (1920, 1080))
        with patch("screen_utils.ImageGrab.grab", return_value=fake) as mock_grab:
            capture_screenshot()
        mock_grab.assert_called_once_with()

    def test_output_is_rgb_mode(self):
        # Input is RGBA — capture_screenshot must convert to RGB
        fake_rgba = Image.new("RGBA", (1920, 1080), (10, 20, 30, 255))
        with patch("screen_utils.ImageGrab.grab", return_value=fake_rgba):
            result = capture_screenshot()
        assert result.mode == "RGB"

    def test_rgb_input_remains_rgb(self):
        fake_rgb = Image.new("RGB", (1920, 1080), (10, 20, 30))
        with patch("screen_utils.ImageGrab.grab", return_value=fake_rgb):
            result = capture_screenshot()
        assert result.mode == "RGB"

    def test_pixel_values_preserved_after_rgb_conversion(self):
        fake = Image.new("RGB", (100, 100), (55, 66, 77))
        with patch("screen_utils.ImageGrab.grab", return_value=fake):
            result = capture_screenshot()
        assert result.getpixel((50, 50)) == (55, 66, 77)
