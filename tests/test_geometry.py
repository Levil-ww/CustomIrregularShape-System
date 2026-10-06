import math
import numpy as np
import pytest
from shape_crop.core.geometry import CircularBand


def test_customer_dimensions_and_symmetric_intersection():
    band = CircularBand(200, 83.76)
    assert band.chord == pytest.approx(181.615699761887)
    assert band.half_height == 41.88
    assert band.depth(100, 0) == 0
    assert band.depth(0, 41.88) == 0
    assert band.depth(99, 41) < 0
    for x, y in [(90, 40), (80, 30), (99, 2)]:
        assert band.depth(x, y) == band.depth(-x, -y)


def test_full_circle_and_exact_parallel_inset():
    circle = CircularBand(200, 200)
    assert circle.chord == 0
    assert circle.perimeter == pytest.approx(200 * math.pi)
    band = CircularBand(200, 83.76)
    inset = band.inset(6)
    assert inset.diameter == 188
    assert inset.height == 71.76
    for x, y in [(0, 0), (90, 20), (50, 30)]:
        assert inset.depth(x, y) == pytest.approx(band.depth(x, y) - 6)


def test_boundary_arc_length_is_continuous_at_joints():
    band = CircularBand(200, 83.76)
    half_chord, h = band.chord / 2, band.half_height
    arc = 2 * band.radius * band.angle
    expected = [0, band.chord, band.chord + arc, 2 * band.chord + arc]
    points = [(-half_chord, -h), (half_chord, -h), (half_chord, h), (-half_chord, h)]
    for (x, y), s in zip(points, expected):
        actual = float(band.boundary_coordinate(x, y))
        assert min(abs(actual - s), abs(actual - s - band.perimeter)) < 1e-8


def test_full_circle_coordinates():
    circle = CircularBand(200, 200)
    values = circle.boundary_coordinate(np.array([0., 100., 0., -100.]), np.array([-100., 0., 100., 0.]))
    np.testing.assert_allclose(values, np.array([0, .25, .5, .75]) * circle.perimeter)


@pytest.mark.parametrize('diameter,height', [(0, 1), (200, 201), (200, -1), (float('nan'), 20)])
def test_invalid_geometry(diameter, height):
    with pytest.raises(ValueError):
        CircularBand(diameter, height)
