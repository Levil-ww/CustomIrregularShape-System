"""Independent framed artwork on a periodic background keeps its clearance."""
import numpy as np
import pytest
from PIL import Image, ImageDraw
from shape_crop.services.layout_analysis import analyze_layout


def framed_source():
    y, x = np.indices((400, 650))
    check = ((x // 20 + y // 20) % 2).astype(bool)
    pixels = np.where(check[..., None], (135, 90, 55), (165, 110, 70)).astype(np.uint8)
    image = Image.fromarray(pixels)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 649, 399), outline='black', width=12)
    draw.rectangle((12, 12, 637, 387), outline=(240, 225, 195), width=3)
    draw.rectangle((80, 90, 569, 309), fill='black', outline=(230, 190, 140), width=2)
    for x in range(100, 550, 70):
        for y in range(110, 290, 60):
            draw.ellipse((x, y, x + 25, y + 30), fill=(250, 240, 215))
    return image


def test_periodic_background_does_not_hide_independent_central_frame():
    layout = analyze_layout(framed_source())
    assert getattr(layout, 'framed_artwork', None) is not None, 'Independent frame is treated as full-span content'


@pytest.mark.parametrize('factor', [1, 4])
@pytest.mark.parametrize('mode', ['arc', 'circular'])
@pytest.mark.parametrize('width,height', [(139, 87), (131, 81), (151, 91)])
def test_complete_picture_uses_uniform_scale_and_original_clearance(factor, mode, width, height):
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import create_shape
    from shape_crop.models.design import DesignSpec, BorderSpec
    image = framed_source().resize((650 * factor, 400 * factor), Image.Resampling.NEAREST)
    layout = analyze_layout(image)
    artwork = layout.framed_artwork
    assert artwork is not None
    design = DesignSpec(diameter_cm=width, height_cm=height, shape_mode=mode,
                        straight_cm=width * .77, border=BorderSpec(0, 0, 0))
    shape = create_shape(design)
    native = ContentMapping.source_scale(layout, width, height)
    border = max(layout.border_depth_px * native, ContentMapping.required_border(layout, width, height))
    mapping = ContentMapping.create(layout, width, height, border, shape)
    a, b, c, d = artwork.box
    clearance = min(a - artwork.frame[0], b - artwork.frame[1],
                    artwork.frame[2] - c, artwork.frame[3] - d) * native
    xs = np.array([a, a, c, c]) - layout.width_px / 2
    ys = np.array([b, d, b, d]) - layout.height_px / 2
    assert mapping.scale_cm < native
    assert np.min(shape.depth(xs * mapping.scale_cm, ys * mapping.scale_cm)) >= border + clearance - .001


def test_background_and_picture_are_sampled_as_separate_layers():
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.framed_artwork_mapping import sample_framed_artwork
    from shape_crop.models.design import DesignSpec, BorderSpec
    from shape_crop.core.geometry import create_shape
    layout = analyze_layout(framed_source())
    design = DesignSpec(diameter_cm=139, height_cm=87, shape_mode='arc', straight_cm=108,
                        border=BorderSpec(0, 0, 0))
    native = ContentMapping.source_scale(layout, 139, 87)
    border = max(layout.border_depth_px * native, ContentMapping.required_border(layout, 139, 87))
    mapping = ContentMapping.create(layout, 139, 87, border, create_shape(design))
    # Source pixels close to all four artwork edges must survive the same scale.
    a, b, c, d = (round(value) for value in layout.framed_artwork.box)
    for u, v in ((a + 4, b + 4), (c - 5, b + 4), (a + 4, d - 5), (c - 5, d - 5), (100, 110)):
        x = np.array([[u - mapping.centre_x]]) * mapping.scale_cm
        y = np.array([[v - mapping.centre_y]]) * mapping.scale_cm
        actual = sample_framed_artwork(layout, mapping, native, x, y, .01)[0, 0]
        np.testing.assert_allclose(actual, layout.image[v, u], atol=1)


def test_arbitrary_textured_surroundings_do_not_count_as_a_periodic_background():
    image = framed_source()
    pixels = np.asarray(image).copy()
    noise = np.random.default_rng(13).integers(75, 190, pixels.shape, dtype=np.uint8)
    mask = np.ones(pixels.shape[:2], dtype=bool)
    mask[90:310, 80:570] = False
    mask[:15] = mask[-15:] = False
    mask[:, :15] = mask[:, -15:] = False
    pixels[mask] = noise[mask]
    assert analyze_layout(Image.fromarray(pixels)).framed_artwork is None


@pytest.mark.parametrize('size', [(1197, 743), (2401, 1603)])
def test_antialiased_frame_edges_remain_recognizable(size):
    image = framed_source().resize(size, Image.Resampling.LANCZOS)
    assert analyze_layout(image).framed_artwork is not None
