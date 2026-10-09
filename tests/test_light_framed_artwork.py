"""Contrasting independent pictures keep their original clearance and proportions."""
import numpy as np
import pytest
from PIL import Image, ImageDraw
from shape_crop.services.layout_analysis import analyze_layout


def light_picture():
    y, x = np.indices((400, 650))
    pixels = np.where(((x // 20 + y // 20) % 2)[..., None], (180, 170, 145), (210, 200, 175)).astype(np.uint8)
    im = Image.fromarray(pixels)
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, 0, 649, 399), outline='black', width=12)
    draw.rectangle((75, 80, 574, 319), fill=(242, 232, 220), outline=(125, 105, 85), width=2)
    draw.line((250, 180, 400, 220), fill='black', width=4)
    return im


@pytest.mark.parametrize('factor', [1, 4])
def test_light_independent_frame_is_not_full_span_content(factor):
    im = light_picture().resize((650 * factor, 400 * factor), Image.Resampling.NEAREST)
    assert analyze_layout(im).framed_artwork is not None


def dark_picture():
    im = Image.new('RGB', (600, 380), (135, 90, 55))
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, 0, 599, 379), outline='black', width=15)
    draw.rectangle((45, 35, 554, 344), fill='black')
    for x in range(60, 530, 50):
        for y in range(50, 330, 50):
            draw.ellipse((x,y,x+25,y+25),outline=(230,215,190),width=3)
    return im


@pytest.mark.parametrize('factory',[light_picture,dark_picture])
@pytest.mark.parametrize('mode',['arc','circular'])
@pytest.mark.parametrize('width,height',[(139,87),(131,81),(151,91)])
def test_whole_rectangle_keeps_uniform_scale_and_source_clearance(factory,mode,width,height):
    from shape_crop.core.content_mapping import ContentMapping
    from shape_crop.core.geometry import create_shape
    from shape_crop.models.design import DesignSpec,BorderSpec
    layout=analyze_layout(factory())
    artwork=layout.framed_artwork
    assert artwork is not None
    assert layout.border_depth_px == round(artwork.frame[1]), "图案留白不能重复计入边框宽度"
    spec=DesignSpec(diameter_cm=width,height_cm=height,shape_mode=mode,straight_cm=width*.77,border=BorderSpec(0,0,0))
    shape=create_shape(spec)
    native=ContentMapping.source_scale(layout,width,height)
    border=max(layout.border_depth_px*native,ContentMapping.required_border(layout,width,height))
    mapping=ContentMapping.create(layout,width,height,border,shape)
    a,b,c,d=artwork.box
    gap=min(a-artwork.frame[0],b-artwork.frame[1],artwork.frame[2]-c,artwork.frame[3]-d)*native
    xs=np.array([a,a,c,c])-layout.width_px/2
    ys=np.array([b,d,b,d])-layout.height_px/2
    assert mapping.scale_cm<native
    assert np.min(shape.depth(xs*mapping.scale_cm,ys*mapping.scale_cm))>=border+gap-.001


def test_blank_panel_with_nonperiodic_flowers_retains_original_layout():
    im=Image.new('RGB',(650,400),(242,232,220))
    draw=ImageDraw.Draw(im)
    draw.rectangle((0,0,649,399),outline='black',width=12)
    draw.rectangle((75,80,574,319),outline='black',width=2)
    draw.line((500,300,550,300),fill='black',width=3)
    for x,y in [(35,45),(120,40),(440,350),(600,280)]:
        draw.ellipse((x,y,x+15,y+18),outline='black',width=1)
    assert analyze_layout(im).framed_artwork is None


@pytest.mark.parametrize('factor',[1,4])
def test_single_noisy_frame_row_does_not_hide_independent_picture(factor):
    pixels=np.asarray(light_picture()).copy()
    for x in range(12,638,8):
        pixels[11,x:x+3]=(45,45,45)
    image=Image.fromarray(pixels).resize((650*factor,400*factor),Image.Resampling.NEAREST)
    assert analyze_layout(image).framed_artwork is not None
