"""Translucent contours must not bend the underlying floral artwork."""
import numpy as np
import pytest
from PIL import Image, ImageDraw
from dataclasses import replace
from shape_crop.services.layout_analysis import analyze_layout
from shape_crop.services.materials import PreparedMaterial
from shape_crop.models.design import DesignSpec, BorderSpec, MaterialSpec
from shape_crop.core.source_renderer import render_source


def circles_source(factor=1, offset_x=0):
    image = Image.new('RGB', (600, 360), (242, 237, 217))
    draw = ImageDraw.Draw(image)
    for y in (62, 102, 162, 222, 282, 322):
        for x in range(42+offset_x, 580, 60):
            draw.ellipse((x-10, y-10, x+10, y+10), fill=(0, 0, 0))
    pixels = np.asarray(image).copy()
    pixels[72:288, 72:528] = np.round(pixels[72:288, 72:528] * .12 + np.array([242, 237, 217]) * .88)
    image = Image.fromarray(pixels)
    ImageDraw.Draw(image).rectangle((84, 84, 515, 275), outline=(20, 20, 18), width=1)
    return image.resize((600*factor, 360*factor), Image.Resampling.NEAREST)


@pytest.mark.parametrize('factor', [1, 4])
@pytest.mark.parametrize('mode', ['arc', 'circular'])
@pytest.mark.parametrize('width,height,straight', [(181, 86, 105.2), (139, 87, 108), (105, 66.5, 82)])
@pytest.mark.parametrize('source_y', [62, 162])
def test_flower_stays_round_at_source_scale(factor, mode, width, height, straight, source_y):
    layout = analyze_layout(circles_source(factor))
    assert layout.inset_panel is not None
    # Isolate the panel mapping from synthetic outer-frame recognition.
    layout = replace(layout, border_depth_px=5*factor,
        content_box_px=(5*factor, 5*factor, 595*factor, 355*factor),
        content=layout.image[5*factor:355*factor, 5*factor:595*factor],
        strip=np.full((5*factor, 1, 3), (242, 237, 217), dtype=np.uint8))
    design = DesignSpec(diameter_cm=width, height_cm=height, straight_cm=straight,
                        shape_mode=mode, border=BorderSpec(0, 0, 0))
    material = PreparedMaterial(layout.image, layout.strip, MaterialSpec(), layout)
    pixels = np.asarray(render_source(design, material, max_side=1600))
    # A 21px disk at source x=282, before or inside the translucent panel,
    # must use the same x/y scale and source position as every other flower.
    scale = max(width/600, height/360)
    cx = round(((-17.5*scale)/width + .5)*pixels.shape[1]-.5)
    cy = round((((source_y-179.5)*scale)/height + .5)*pixels.shape[0]-.5)
    patch = pixels[max(0,cy-35):cy+36, cx-35:cx+36, :3]
    # Measure the faded disk at half its known 242→213 contrast, excluding
    # the interpolation fringe that grows with source-pixel magnification.
    rows, columns = np.nonzero(np.max(patch, axis=2) < (90 if source_y == 62 else 228))
    assert len(rows) > 20, '原位置的完整圆形花纹丢失'
    assert abs(np.ptp(rows)-np.ptp(columns)) <= 3, '外层花纹被内框映射挤压或拉伸'
    assert np.ptp(columns) == pytest.approx(20*scale*pixels.shape[1]/width, abs=3)


@pytest.mark.parametrize('value', [140, 230])
def test_unfaded_detail_next_to_panel_keeps_its_colour(value):
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import CircularBand
    from shape_crop.core.panel_mapping import _sample_translucent_panel
    image = circles_source()
    ImageDraw.Draw(image).ellipse((57, 156, 65, 168), fill=(value, value, value))
    layout = analyze_layout(image)
    result = _sample_translucent_panel(layout, ContentMapping(1, 0, 0, 0, 0),
        CircularBand(1, 1), np.array([[61.]]), np.array([[162.]]), 1)
    np.testing.assert_array_equal(result[0, 0], (value, value, value))


def test_original_outline_corners_do_not_leave_black_dots():
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import CircularBand
    from shape_crop.core.panel_mapping import _sample_translucent_panel
    image = circles_source()
    draw = ImageDraw.Draw(image)
    for x, y in ((84, 84), (515, 84), (84, 275), (515, 275)):
        draw.rectangle((x-5, y-5, x+5, y+5), fill=(242, 237, 217))
    draw.rectangle((84, 84, 515, 275), outline=(20, 20, 18), width=1)
    layout = analyze_layout(image)
    for x, y in ((84, 84), (515, 84), (84, 275), (515, 275)):
        result = _sample_translucent_panel(layout, ContentMapping(1, 0, 0, 0, 0),
            CircularBand(1, 1), np.array([[float(x)]]), np.array([[float(y)]]), 1)
        np.testing.assert_allclose(result[0, 0], (242, 237, 217), atol=2)


def test_original_faded_detail_is_preserved_inside_matching_masks():
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import CircularBand
    from shape_crop.core.panel_mapping import _sample_translucent_panel
    image = circles_source()
    image.putpixel((200, 140), (240, 235, 215))
    layout = analyze_layout(image)
    result = _sample_translucent_panel(layout, ContentMapping(1, 0, 0, 0, 0),
        CircularBand(1000, 1000), np.array([[200.]]), np.array([[140.]]), 1)
    np.testing.assert_array_equal(result[0, 0], (240, 235, 215))


def test_ambiguous_pale_detail_outside_verified_outline_is_not_recovered():
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import CircularBand
    from shape_crop.core.panel_mapping import _sample_translucent_panel
    image = circles_source()
    ImageDraw.Draw(image).rectangle((70, 156, 71, 168), fill=(230, 225, 205))
    layout = analyze_layout(image)
    result = _sample_translucent_panel(layout, ContentMapping(1, 0, 0, 0, 0),
        CircularBand(1, 1), np.array([[70.]]), np.array([[162.]]), 1)
    np.testing.assert_array_equal(result[0, 0], (230, 225, 205))


def test_native_border_overshoot_uses_preview_structure_without_resizing_ink():
    from shape_crop.services.materials import _align_translucent_layout
    from shape_crop.core.content_mapping import ContentMapping
    reference = analyze_layout(circles_source())
    reference = replace(reference, content_box_px=(5, 5, 595, 355), border_depth_px=5)
    native = analyze_layout(circles_source(4))
    native = replace(native, content_box_px=(20, 20, 2100, 1420))
    assert ContentMapping.required_border(native, 181, 86) > 20
    corrected = _align_translucent_layout(native, reference)
    assert corrected.content_box_px == (20, 20, 2380, 1420)
    assert ContentMapping.required_border(corrected, 181, 86) == pytest.approx(181/120)
    assert corrected.image is native.image
    np.testing.assert_allclose(corrected.inset_panel.box, (336, 336, 2060, 1100), atol=4)


@pytest.mark.parametrize('feature', ['sentence', 'corner_gaps', 'layered_strip'])
def test_native_alignment_keeps_special_border_layers(feature):
    from shape_crop.services.materials import _align_translucent_layout
    reference = analyze_layout(circles_source())
    native = analyze_layout(circles_source(4))
    if feature == 'sentence':
        native = replace(native, strip_is_sentence=True)
    elif feature == 'corner_gaps':
        native = replace(native, corner_gaps=(0, 1, ((242, 237, 217),)*4))
    else:
        native = replace(native, layered_strip=(1, native.strip))
    assert _align_translucent_layout(native, reference) is native


def test_native_outline_cleanup_uses_actual_stroke_width():
    from shape_crop.services.materials import _align_translucent_layout
    reference = analyze_layout(circles_source())
    image = circles_source(4)
    ImageDraw.Draw(image).rectangle((336, 336, 2060, 349), fill=(20, 20, 18))
    native = analyze_layout(image)
    corrected = _align_translucent_layout(native, reference)
    assert corrected.inset_panel.translucent[3] >= 16


@pytest.mark.parametrize('horizontal', [True, False])
@pytest.mark.parametrize('fraction', [.22, .78])
def test_fractional_old_outline_cleanup_includes_resampled_jpeg_fringe(horizontal, fraction):
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import CircularBand
    from shape_crop.core.panel_mapping import _sample_translucent_panel
    layout = analyze_layout(circles_source())
    pixels = layout.image.copy()
    background = np.array((242, 237, 217), dtype=np.uint8)
    # The detected edge is fractional after scaling the analysis thumbnail.
    # A dark JPEG lobe just outside the cleanup band is amplified by the
    # nearly opaque fade, leaving a seam below the new curved corner.
    pixels[250:295, 250:295] = background
    if horizontal:
        pixels[270, 250:295] = background - 5
        pixels[272:276, 250:295] = 20
        point = (260., 270.)
    else:
        pixels[250:295, 270] = background - 5
        pixels[250:295, 272:276] = 20
        point = (270., 260.)
    panel = replace(layout.inset_panel, box=(84., 84., 275.+fraction, 275.+fraction),
        translucent=((72., 72., 300., 300.), .88, tuple(background), 4., (20, 20, 18)),
        stroke_repeat_px=0, partial_fade_edges=())
    layout = replace(layout, image=pixels, inset_panel=panel)
    result = _sample_translucent_panel(layout, ContentMapping(1, 0, 0, 0, 0),
        CircularBand(1, 1), np.array([[point[0]]]), np.array([[point[1]]]), 1)
    np.testing.assert_allclose(result[0, 0], background, atol=2,
        err_msg='旧描边附近的JPEG暗边恢复后形成接缝')


def test_tinted_source_fade_recovers_neutral_black_without_blue_fringe():
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import CircularBand
    from shape_crop.core.panel_mapping import _sample_translucent_panel
    pixels = np.asarray(circles_source()).copy()
    interior = pixels[85:275, 85:515]
    interior[np.max(interior, axis=2) < 230] = (217, 213, 205)
    layout = analyze_layout(Image.fromarray(pixels))
    assert layout.inset_panel.translucent is not None
    result = _sample_translucent_panel(layout, ContentMapping(1, 0, 0, 0, 0),
        CircularBand(1, 1), np.array([[282.]]), np.array([[162.]]), 1)
    np.testing.assert_array_equal(result[0, 0], (0, 0, 0))


def test_translucent_background_with_zero_channel_does_not_divide_by_zero():
    import warnings
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import CircularBand
    from shape_crop.core.panel_mapping import _sample_translucent_panel
    pixels = np.asarray(circles_source()).copy()
    pixels[..., 0] = 0
    layout = analyze_layout(Image.fromarray(pixels))
    with warnings.catch_warnings():
        warnings.simplefilter('error', RuntimeWarning)
        result = _sample_translucent_panel(layout, ContentMapping(1, 0, 0, 0, 0),
            CircularBand(1000, 1000), np.array([[282.]]), np.array([[162.]]), 1)
    assert result[0, 0, 0] == 0


def test_source_fade_bounds_include_painted_fringe_beyond_outline():
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import CircularBand
    from shape_crop.core.panel_mapping import _sample_translucent_panel
    layout = analyze_layout(circles_source(offset_x=36))
    assert layout.inset_panel.translucent[0][0] == 72
    result = _sample_translucent_panel(layout, ContentMapping(1, 0, 0, 0, 0),
        CircularBand(1, 1), np.array([[78.]]), np.array([[162.]]), 1)
    np.testing.assert_array_equal(result[0, 0], (0, 0, 0))


def test_fringe_repair_is_independent_of_output_row_sampling():
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import CircularBand
    from shape_crop.core.panel_mapping import _sample_translucent_panel
    pixels = np.asarray(circles_source(offset_x=36)).copy()
    pixels[162, 8:29] = (0, 0, 0)
    pixels[162, 70] = (230, 225, 205)
    layout = analyze_layout(Image.fromarray(pixels))
    for coordinates in (np.array([70.]), np.arange(600.), np.arange(2., 600., 4.)):
        result = _sample_translucent_panel(layout, ContentMapping(1, 0, 0, 0, 0),
            CircularBand(1, 1), coordinates[None, :], np.array([[162.]]), 1)
        np.testing.assert_array_equal(result[0, np.flatnonzero(coordinates == 70)[0]], (230, 225, 205))


def test_curved_fade_preserves_original_clearance_outside_fine_outline():
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import CircularBand
    from shape_crop.core.panel_mapping import _sample_translucent_panel
    image = circles_source(offset_x=36)
    image.putpixel((200, 140), (240, 235, 215))
    layout = analyze_layout(image)
    result = _sample_translucent_panel(layout, ContentMapping(1, 200, 89, 0, 0),
        CircularBand(100, 100), np.array([[0.]]), np.array([[51.]]), 1)
    np.testing.assert_array_equal(result[0, 0], (240, 235, 215))


def test_verified_repeat_recovers_flower_hidden_by_vertical_stroke():
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import CircularBand
    from shape_crop.core.panel_mapping import _sample_translucent_panel
    image = circles_source(offset_x=36)
    draw = ImageDraw.Draw(image)
    for centre in range(84, 520, 60):
        draw.rectangle((centre-1, 146, centre+1, 151), fill=(213, 209, 191))
    draw.rectangle((84, 84, 515, 275), outline=(20, 20, 18), width=1)
    layout = analyze_layout(image)
    assert layout.inset_panel.stroke_repeat_px == 60
    result = _sample_translucent_panel(layout, ContentMapping(1, 0, 0, 0, 0),
        CircularBand(1, 1), np.array([[84.]]), np.array([[150.]]), 1)
    np.testing.assert_array_equal(result[0, 0], (0, 0, 0))
    fallback = replace(layout, inset_panel=replace(layout.inset_panel, stroke_repeat_px=0))
    old_result = _sample_translucent_panel(fallback, ContentMapping(1, 0, 0, 0, 0),
        CircularBand(1, 1), np.array([[84.]]), np.array([[150.]]), 1)
    assert np.min(old_result[0, 0]) > 190, '此回归须能检出插值抹掉细花纹的情况'


def test_source_fade_edge_does_not_create_grey_interpolation_seam():
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import CircularBand
    from shape_crop.core.panel_mapping import _sample_translucent_panel
    layout = analyze_layout(circles_source(offset_x=36))
    result = _sample_translucent_panel(layout, ContentMapping(1, 0, 0, 0, 0),
        CircularBand(1, 1), np.array([[71.5]]), np.array([[162.]]), 1)
    np.testing.assert_array_equal(result[0, 0], (0, 0, 0))


def test_naturally_pale_repetitions_do_not_authorize_fringe_recovery():
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import CircularBand
    from shape_crop.core.panel_mapping import _sample_translucent_panel
    pixels = np.asarray(circles_source()).copy()
    pixels[70, [162, 222, 282, 342, 402]] = (230, 225, 205)
    layout = analyze_layout(Image.fromarray(pixels))
    result = _sample_translucent_panel(layout, ContentMapping(1, 0, 0, 0, 0),
        CircularBand(1, 1), np.array([[282.]]), np.array([[70.]]), 1)
    np.testing.assert_array_equal(result[0, 0], (230, 225, 205))


def test_fade_recovery_does_not_amplify_jpeg_bright_noise_above_background():
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import CircularBand
    from shape_crop.core.panel_mapping import _sample_translucent_panel
    pixels = np.asarray(circles_source()).copy()
    pixels[140, 200] = (246, 241, 221)
    layout = analyze_layout(Image.fromarray(pixels))
    result = _sample_translucent_panel(layout, ContentMapping(1, 0, 0, 0, 0),
        CircularBand(1, 1), np.array([[200.]]), np.array([[140.]]), 1)
    np.testing.assert_array_equal(result[0, 0], (242, 237, 217))


@pytest.mark.parametrize('point', [(71,162), (78,83), (516,162), (78,289)])
def test_neutral_jpeg_bright_ringing_outside_source_fade_is_removed(point):
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import CircularBand
    from shape_crop.core.panel_mapping import _sample_translucent_panel
    image = circles_source(offset_x=36)
    image.putpixel(point, (252, 247, 227))
    layout = analyze_layout(image)
    result = _sample_translucent_panel(layout, ContentMapping(1, 0, 0, 0, 0),
        CircularBand(1, 1), np.array([[float(point[0])]]), np.array([[float(point[1])]]), 1)
    np.testing.assert_array_equal(result[0, 0], (242, 237, 217))


@pytest.mark.parametrize('point,value', [((71,162),(255,255,255)), ((40,162),(252,247,227))])
def test_white_artwork_and_detail_away_from_old_frame_remain_unchanged(point, value):
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import CircularBand
    from shape_crop.core.panel_mapping import _sample_translucent_panel
    image = circles_source(offset_x=36)
    image.putpixel(point, value)
    layout = analyze_layout(image)
    result = _sample_translucent_panel(layout, ContentMapping(1, 0, 0, 0, 0),
        CircularBand(1, 1), np.array([[float(point[0])]]), np.array([[float(point[1])]]), 1)
    np.testing.assert_array_equal(result[0, 0], value)


@pytest.mark.parametrize('edge,point,offset', [('left',(71,162),36), ('top',(78,71),36),
                                             ('right',(528,162),0), ('bottom',(78,288),36)])
def test_partial_original_fade_outside_rectangle_does_not_leave_a_grey_line(edge, point, offset):
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import CircularBand
    from shape_crop.core.panel_mapping import _sample_translucent_panel
    image = circles_source(offset_x=offset)
    pixels = np.asarray(image).copy()
    if edge == 'left':
        band = pixels[72:288, 71]
    elif edge == 'right':
        band = pixels[72:288, 528]
    elif edge == 'top':
        band = pixels[71, 72:528]
    else:
        band = pixels[288, 72:528]
    band[:] = np.round(band*.7 + np.array([242,237,217])*.3)
    layout = analyze_layout(Image.fromarray(pixels))
    result = _sample_translucent_panel(layout, ContentMapping(1, 0, 0, 0, 0),
        CircularBand(1, 1), np.array([[float(point[0])]]), np.array([[float(point[1])]]), 1)
    np.testing.assert_array_equal(result[0, 0], (0, 0, 0))


def test_nearly_opaque_jpeg_transition_keeps_black_ink_and_flat_background():
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import CircularBand
    from shape_crop.core.panel_mapping import _sample_translucent_panel
    pixels = np.asarray(circles_source(offset_x=36)).copy()
    for column, alpha in ((71,.97),(70,.3)):
        pixels[72:288,column] = np.round(pixels[72:288,column]*(1-alpha)+np.array([242,237,217])*alpha)
    pixels[162,71] += 4
    layout = analyze_layout(Image.fromarray(pixels))
    result = _sample_translucent_panel(layout, ContentMapping(1, 0, 0, 0, 0),
        CircularBand(1, 1), np.array([[71.,71.]]), np.array([[162.,140.]]), 1)
    np.testing.assert_array_equal(result[0,0], (0,0,0))
    np.testing.assert_array_equal(result[0,1], (242,237,217))
