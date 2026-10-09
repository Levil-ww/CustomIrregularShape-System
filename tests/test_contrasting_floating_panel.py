"""Dense shaped pictures on flat coloured moats remain independent artwork."""
import numpy as np
import pytest
from PIL import Image, ImageDraw
from shape_crop.services.layout_analysis import analyze_layout
from shape_crop.core.content_mapping import ContentMapping
from shape_crop.core.geometry import create_shape
from shape_crop.models.design import DesignSpec, BorderSpec


def source():
    im = Image.new('RGB', (600, 372), (98, 76, 65))
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, 0, 599, 371), outline=(20, 15, 10), width=1)
    draw.rectangle((9, 9, 590, 362), outline=(35, 25, 17), width=2)
    draw.rectangle((14, 14, 585, 357), outline=(35, 25, 17), width=1)
    # A large light filled wave panel exceeds the old large-frame thresholds.
    points = [(x, 40 + 12*np.cos(x/20)) for x in range(40,561)]
    points += [(x, 331 + 12*np.cos(x/20)) for x in range(560,39,-1)]
    draw.polygon(points, fill=(248,232,213), outline=(30,20,13))
    for x in range(65,540,60):
        for y in range(80,310,45):
            draw.line((x,y,x+20,y+15),fill=(98,76,65),width=1)
    return im


@pytest.mark.parametrize('factor', [1,4])
def test_dense_wave_picture_has_flat_moat_classification(factor):
    im=source().resize((600*factor,372*factor),Image.Resampling.NEAREST)
    layout=analyze_layout(im)
    assert layout.category=='独立图案留白类', '波浪画框被当作局部文字边框'
    assert layout.floating_artwork is not None
    assert not layout.strip_is_sentence
    assert layout.border_depth_px < 20*factor, '边框带混入波浪轮廓'


@pytest.mark.parametrize('mode',['arc','circular'])
@pytest.mark.parametrize('width,height',[(139,87),(131,81),(151,91)])
def test_wave_and_inner_artwork_share_uniform_smaller_scale(mode,width,height):
    layout=analyze_layout(source())
    design=DesignSpec(diameter_cm=width,height_cm=height,shape_mode=mode,straight_cm=width*.78,border=BorderSpec(0,0,0))
    shape=create_shape(design)
    native=ContentMapping.source_scale(layout,width,height)
    border=max(layout.border_depth_px*native,ContentMapping.required_border(layout,width,height))
    mapping=ContentMapping.create(layout,width,height,border,shape)
    assert mapping.scale_cm < native*.95, '中央波浪框及花纹未整体等比缩小'
    assert mapping.background==(98,76,65)


def test_image_edge_alone_does_not_prove_independent_artwork():
    from shape_crop.services.floating_artwork import detect_contrasting_artwork

    im = source()
    draw = ImageDraw.Draw(im)
    draw.rectangle((5, 5, 594, 25), fill=(98, 76, 65))
    draw.rectangle((5, 346, 594, 366), fill=(98, 76, 65))
    draw.rectangle((5, 5, 25, 366), fill=(98, 76, 65))
    draw.rectangle((574, 5, 594, 366), fill=(98, 76, 65))
    assert detect_contrasting_artwork(im) is None
