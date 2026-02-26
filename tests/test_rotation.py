"""
Tests for annotation rotation transform mathematics.

The core formula used in MusicScoreApp._transform_annotations_for_rotation:
    90° CW in normalised space:  (nx, ny) -> (1 - ny, nx)

Applied `steps` times for (90 * steps)° total clockwise rotation.

NOTE (Phase 3): Once _transform_annotations_for_rotation is extracted into a
standalone function these tests should import and call it directly rather than
replicating the formula here.
"""
import pytest


# ---------------------------------------------------------------------------
# Replicate the formula from _transform_annotations_for_rotation
# ---------------------------------------------------------------------------

def _rot_pt_cw90(nx: float, ny: float) -> tuple:
    """One 90° clockwise rotation in normalised [0,1] space."""
    return 1.0 - ny, nx


def _rot_pt(nx: float, ny: float, delta: int) -> tuple:
    """
    Rotate point (nx, ny) by delta degrees clockwise in normalised space.
    Matches the steps = (delta // 90) % 4 logic in the production code.
    """
    steps = (delta // 90) % 4
    for _ in range(steps):
        nx, ny = _rot_pt_cw90(nx, ny)
    return nx, ny


EPSILON = 1e-10


# ---------------------------------------------------------------------------
# Basic properties
# ---------------------------------------------------------------------------

class TestRotationIdentity:
    def test_zero_degrees_is_identity(self):
        x, y = _rot_pt(0.3, 0.7, 0)
        assert abs(x - 0.3) < EPSILON and abs(y - 0.7) < EPSILON

    def test_360_degrees_is_identity(self):
        x, y = _rot_pt(0.3, 0.7, 360)
        assert abs(x - 0.3) < EPSILON and abs(y - 0.7) < EPSILON

    def test_four_steps_of_90_is_identity(self):
        for px, py in [(0.0, 0.0), (1.0, 0.0), (0.3, 0.7), (0.5, 0.2)]:
            x, y = _rot_pt(px, py, 360)
            assert abs(x - px) < EPSILON and abs(y - py) < EPSILON

    def test_centre_invariant_under_all_rotations(self):
        """(0.5, 0.5) is the centre of rotation and must never move."""
        for delta in [0, 90, 180, 270, 360, -90, -180]:
            x, y = _rot_pt(0.5, 0.5, delta)
            assert abs(x - 0.5) < EPSILON, f"centre shifted at delta={delta}"
            assert abs(y - 0.5) < EPSILON, f"centre shifted at delta={delta}"


class TestKnownRotations:
    """Verify specific (input, delta) -> expected output pairs."""

    # Top-left corner (0, 0) behaviour
    def test_top_left_90_cw(self):
        # (0,0) -> top-right (1,0)
        assert _rot_pt(0.0, 0.0, 90) == (1.0, 0.0)

    def test_top_left_180(self):
        # (0,0) -> bottom-right (1,1)
        assert _rot_pt(0.0, 0.0, 180) == (1.0, 1.0)

    def test_top_left_270_cw(self):
        # (0,0) -> bottom-left (0,1)
        assert _rot_pt(0.0, 0.0, 270) == (0.0, 1.0)

    # All four corners should cycle correctly
    def test_corners_cycle_under_90_cw(self):
        corners      = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        corners_90cw = [(1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0)]
        for (x, y), (ex, ey) in zip(corners, corners_90cw):
            rx, ry = _rot_pt(x, y, 90)
            assert abs(rx - ex) < EPSILON and abs(ry - ey) < EPSILON


class TestInverseRelationship:
    """CW 90° and CCW 90° (= CW 270°) should be inverses of each other."""

    def test_cw_then_ccw_is_identity(self):
        for px, py in [(0.1, 0.9), (0.3, 0.3), (0.7, 0.2)]:
            x1, y1 = _rot_pt(px, py, 90)   # 90° CW
            x2, y2 = _rot_pt(x1, y1, 270)  # 90° CCW (= 270° CW)
            assert abs(x2 - px) < EPSILON and abs(y2 - py) < EPSILON

    def test_ccw_then_cw_is_identity(self):
        for px, py in [(0.1, 0.9), (0.3, 0.3), (0.7, 0.2)]:
            x1, y1 = _rot_pt(px, py, 270)  # 90° CCW
            x2, y2 = _rot_pt(x1, y1, 90)   # 90° CW
            assert abs(x2 - px) < EPSILON and abs(y2 - py) < EPSILON

    def test_negative_delta_matches_equivalent_positive(self):
        """-90° should produce the same result as +270°."""
        for px, py in [(0.2, 0.8), (0.6, 0.4)]:
            xn, yn = _rot_pt(px, py, -90)
            xp, yp = _rot_pt(px, py, 270)
            assert abs(xn - xp) < EPSILON and abs(yn - yp) < EPSILON


class TestComposition:
    """Two rotations applied in sequence equal their sum."""

    def test_90_plus_90_equals_180(self):
        for px, py in [(0.1, 0.4), (0.8, 0.2)]:
            x1, y1 = _rot_pt(px, py, 90)
            x2, y2 = _rot_pt(x1, y1, 90)
            xe, ye = _rot_pt(px, py, 180)
            assert abs(x2 - xe) < EPSILON and abs(y2 - ye) < EPSILON

    def test_90_plus_180_equals_270(self):
        for px, py in [(0.1, 0.4), (0.8, 0.2)]:
            x1, y1 = _rot_pt(px, py, 90)
            x2, y2 = _rot_pt(x1, y1, 180)
            xe, ye = _rot_pt(px, py, 270)
            assert abs(x2 - xe) < EPSILON and abs(y2 - ye) < EPSILON


class TestNormalisedSpaceBounds:
    """After any rotation, a point inside [0,1]² stays inside [0,1]²."""

    @pytest.mark.parametrize("delta", [0, 90, 180, 270])
    def test_unit_square_stays_in_unit_square(self, delta):
        test_points = [
            (0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0),
            (0.3, 0.7), (0.5, 0.5), (0.1, 0.9),
        ]
        for px, py in test_points:
            rx, ry = _rot_pt(px, py, delta)
            assert 0.0 - EPSILON <= rx <= 1.0 + EPSILON, \
                f"x={rx} out of bounds after {delta}° (from {px},{py})"
            assert 0.0 - EPSILON <= ry <= 1.0 + EPSILON, \
                f"y={ry} out of bounds after {delta}° (from {px},{py})"
