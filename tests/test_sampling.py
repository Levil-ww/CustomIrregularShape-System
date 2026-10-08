import numpy as np
import pytest
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


@pytest.mark.parametrize('channels', [3, 4])
@pytest.mark.parametrize('wrap_x,wrap_y', [(False, False), (True, False), (False, True), (True, True)])
@pytest.mark.parametrize('output_shape', [(128, 200), (1, 200), (128, 1), (1, 1), (7, 9)])
def test_grid_sampling_matches_individual_pixel_coordinates(channels, wrap_x, wrap_y, output_shape):
    source = np.random.default_rng(32).integers(0, 256, (17, 29, channels), dtype=np.uint8)
    height, width = output_shape
    # Include reverse coordinates, repeated rows, clamping and both wrap seams.
    x = np.linspace(35, -8, width, dtype=np.float32)[None, :]
    y = np.linspace(-5, 25, height, dtype=np.float32)[:, None]
    # Independent original four-neighbour formula, including float32 rounding.
    u = x % 29 if wrap_x else np.clip(x, 0, 28)
    v = y % 17 if wrap_y else np.clip(y, 0, 16)
    x0, y0 = np.floor(u).astype(np.int32), np.floor(v).astype(np.int32)
    x1 = (x0 + 1) % 29 if wrap_x else np.minimum(x0 + 1, 28)
    y1 = (y0 + 1) % 17 if wrap_y else np.minimum(y0 + 1, 16)
    fx = (u - x0.astype(np.float32))[..., None]
    fy = (v - y0.astype(np.float32))[..., None]
    a = source[y0, x0].astype(np.float32) * (1 - fx) + source[y0, x1] * fx
    b = source[y1, x0].astype(np.float32) * (1 - fx) + source[y1, x1] * fx
    expected = np.clip(a * (1 - fy) + b * fy, 0, 255).astype(np.uint8)
    np.testing.assert_array_equal(sample(source, x, y, wrap_x, wrap_y), expected)


def test_upscaled_grid_reuses_source_rows_instead_of_gathering_every_output_pixel():
    gathered = []

    class CountedImage(np.ndarray):
        def __getitem__(self, indices):
            result = super().__getitem__(indices)
            gathered.append(result.size // 3)
            return np.asarray(result)

    source = np.random.default_rng(33).integers(0, 256, (17, 29, 3), dtype=np.uint8)
    counted = source.view(CountedImage)
    x = np.linspace(0, 28, 200, dtype=np.float32)[None, :]
    y = np.linspace(0, 16, 128, dtype=np.float32)[:, None]
    actual = sample(counted, x, y)
    dense_x, dense_y = np.broadcast_arrays(x, y)
    expected = sample(source, dense_x.ravel(), dense_y.ravel()).reshape(128, 200, 3)
    np.testing.assert_array_equal(actual, expected)
    assert sum(gathered) < 128 * 200, '放大采样应复用源行，避免每个输出像素重复读取四个邻点'
