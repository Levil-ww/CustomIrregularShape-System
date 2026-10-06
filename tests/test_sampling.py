import numpy as np
from shape_crop.core.sampling import sample, strip_sample, content_sample
from shape_crop.models.design import MaterialSpec


def test_bilinear_pixel_centres_and_repeat_wrap():
    source = np.array([[[0, 0, 0], [100, 100, 100]]], dtype=np.uint8)
    np.testing.assert_array_equal(sample(source, np.array([0, .5, 1]), 0),
                                  [[0, 0, 0], [50, 50, 50], [100, 100, 100]])
    np.testing.assert_array_equal(sample(source, np.array([-.5, 1.5]), 0, True),
                                  [[50, 50, 50], [50, 50, 50]])


def test_automatic_strip_length_and_closed_repeat():
    image = np.zeros((10, 40, 3), dtype=np.uint8)
    image[:, 10:20] = 200
    s = np.array([0., 1., 5., 79.99])
    auto = strip_sample(image, s, 1., 80., 2., 0.)
    manual = strip_sample(image, s, 1., 80., 2., 8.)
    np.testing.assert_array_equal(auto, manual)
    np.testing.assert_array_equal(strip_sample(image, 0., 1., 80., 2., 0.),
                                  strip_sample(image, 80., 1., 80., 2., 0.))


def test_tiled_content_preserves_physical_scale_across_regions():
    image = np.zeros((10, 20, 3), dtype=np.uint8)
    image[:, 5:10] = 200
    material = MaterialSpec(fit='tile', tile_width_cm=20)
    # Centres differ but equal displacements by complete periods map to identical texture.
    np.testing.assert_array_equal(content_sample(image, 3, 2, 100, 100, material),
                                  content_sample(image, 3, 2, 20, 20, material))
