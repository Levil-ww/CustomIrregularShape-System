"""Keep Huaman flowers out of the curved frame strip."""
import numpy as np
import pytest
from dataclasses import replace
from PIL import Image, ImageDraw
from shape_crop.models.design import BorderSpec, DesignSpec, MaterialSpec
from shape_crop.services.materials import prepare
from shape_crop.core.source_renderer import render_source


def huaman_source():
    image = Image.new('RGB', (1200, 700), (250, 249, 239))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1199, 699), outline='black', width=2)
    draw.rectangle((35, 30, 1164, 669), outline='black', width=3)
    draw.line((35, 275, 1164, 275), fill='black', width=2)
    draw.line((35, 420, 1164, 420), fill='black', width=2)
    for x in (100, 340, 600, 850, 1080):
        draw.ellipse((x-40, 35, x+40, 115), outline='black', width=2)
        draw.line((x-35, 80, x+35, 145), fill='black', width=2)
        draw.ellipse((x-40, 560, x+40, 640), outline='black', width=2)
    draw.text((500, 330), 'WONDERFUL LIFE', fill='black')
    return image


def test_closed_frame_removes_flower_fragments_from_overshot_strip():
    from shape_crop.services.layout_analysis import analyze_layout
    from shape_crop.services.materials import _align_huaman_frame
    layout = analyze_layout(huaman_source())
    overshot = replace(layout, border_depth_px=85, strip=layout.image[:85],
                       content=layout.image[85:615], content_box_px=(35, 85, 1165, 615))
    corrected = _align_huaman_frame(overshot)
    assert corrected.border_depth_px <= 35
    assert corrected.strip.shape[0] == corrected.border_depth_px
    assert corrected.content_box_px[1] == corrected.border_depth_px


@pytest.mark.parametrize('mode', ['arc', 'circular'])
@pytest.mark.parametrize('width,height,chord', [(151, 91, 127.5), (130, 80, 105), (180, 80, 150)])
def test_huaman_closed_frame_does_not_repeat_flowers(tmp_path, mode, width, height, chord):
    path = tmp_path / '花幔;86.5x150.5cm.png'
    huaman_source().save(path)
    layout = prepare(MaterialSpec(str(path)), preview=True).source_layout
    assert layout.border_depth_px <= 35, '外框不能包含花枝'
    strip = layout.strip
    # The verified near-horizontal outer border contains no localized floral
    # contours: dark ink is either a continuous row or absent.
    dark_coverage = np.mean(np.max(strip, axis=2) < 80, axis=1)
    assert np.count_nonzero((dark_coverage > .03) & (dark_coverage < .95)) <= 4
    material = prepare(MaterialSpec(str(path)), preview=True)
    design = DesignSpec(diameter_cm=width, height_cm=height, straight_cm=chord,
                        shape_mode=mode, border=BorderSpec(0, 0, 0))
    output = np.asarray(render_source(design, material, max_side=800))
    assert output.shape[1] == 800
