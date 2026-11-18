"""Check dimensioned belly outline and its corner connections."""
import math
import pytest
from shape_crop.core.belly_geometry import BellyOutline


def test_belly_outline_dimensions_and_quarter_circle():
    shape = BellyOutline(140, 80, 63, 120, 15)
    points = shape.points(48)
    assert points[0] == points[-1]
    assert max(x for x, _ in points) == pytest.approx(70)
    assert min(x for x, _ in points) == pytest.approx(-70)
    assert max(y for _, y in points) == pytest.approx(40)
    assert min(y for _, y in points) == pytest.approx(-40)
    assert (60, -39) in points
    assert (67.5, -31.5) in points
    for x, y in points[48:97]:
        assert math.hypot(x - 60, y + 31.5) == pytest.approx(7.5)
    for x, y in points:
        assert any(abs(a + x) < 1e-8 and abs(b - y) < 1e-8 for a, b in points)


@pytest.mark.parametrize('values', [(140, 80, 63, 126, 15), (140, 80, 66, 120, 15),
                                    (140, 80, 63, 120, 0)])
def test_invalid_corner_geometry(values):
    with pytest.raises(ValueError):
        BellyOutline(*values)


def test_reference_approximation_shows_adjusted_spans_and_keeps_other_dimensions():
    shape = BellyOutline(121, 76, 60, 100, 15).reference_approximation()
    assert (shape.width, shape.height, shape.side_span, shape.horizontal_span, shape.corner_diameter) == (121, 76, 57, 103, 15)
    # Reference outline is nearly vertical near the upper side while retaining
    # a gentle bow along the top; strict inputs remain available separately.
    points = shape.points(300)
    nearest = min(points, key=lambda p: abs(p[1] + 29))
    assert abs(abs(nearest[0]) - shape.width / 2) < 2
    assert points[0][1] == -38
