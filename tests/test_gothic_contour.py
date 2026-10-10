"""A textured inset frame follows the contour without shrinking its flowers."""
import numpy as np
import pytest
from PIL import Image, ImageDraw
from shape_crop.services.layout_analysis import analyze_layout
from shape_crop.services.contoured_frame import adapt_contoured_frame
from shape_crop.core.geometry import create_shape
from shape_crop.core.content_mapping import ContentMapping
from shape_crop.core.source_renderer import render_source
from shape_crop.models.design import DesignSpec, BorderSpec, MaterialSpec
from shape_crop.services.materials import PreparedMaterial


def source():
    yy, xx = np.mgrid[:480, :800]
    p = np.where(((xx//24+yy//24)%2)[...,None], (150,100,65),(130,85,55)).astype(np.uint8)
    im = Image.fromarray(p)
    d = ImageDraw.Draw(im)
    d.rectangle((0,0,799,479),outline='black',width=16)
    d.rectangle((16,16,783,463),outline=(230,215,185),width=4)
    for x in range(28,780,12):
        for y in (28,451): d.polygon([(x,y-5),(x+5,y),(x,y+5),(x-5,y)],fill=(230,215,185))
    for y in range(28,460,12):
        for x in (28,771): d.polygon([(x,y-5),(x+5,y),(x,y+5),(x-5,y)],fill=(230,215,185))
    d.rectangle((88,82,711,397),fill='black',outline=(0,0,0),width=2)
    d.rectangle((90,84,709,395),outline=(150,100,65),width=2)
    for x in range(105,690,48):
        for y in range(100,390,48): d.ellipse((x,y,x+20,y+20),fill=(230,215,185))
    return im


@pytest.mark.parametrize('mode',['arc','circular'])
@pytest.mark.parametrize('size',[(139,87,108),(131,81,102),(151,91,120.5)])
def test_inner_outline_curves_and_flower_scale_is_uniform(mode,size):
    layout = adapt_contoured_frame(analyze_layout(source()))
    assert layout.contoured_frame is not None
    spec=DesignSpec(diameter_cm=size[0],height_cm=size[1],straight_cm=size[2],shape_mode=mode,border=BorderSpec(0,0,0))
    m=PreparedMaterial(layout.image,layout.strip,MaterialSpec(),layout)
    image=np.asarray(render_source(spec,m,max_side=1400))
    shape=create_shape(spec)
    scale=ContentMapping.source_scale(layout,*size[:2])
    border=max(layout.border_depth_px*scale,ContentMapping.required_border(layout,*size[:2]))
    depth=layout.contoured_frame.inset_px*scale+border-layout.border_depth_px*scale
    inner=shape.inset(depth)
    for y in (-10,0,10):
        x=getattr(inner,'center',0)+np.sqrt(inner.radius**2-y**2)
        row=round((y/size[1]+.5)*image.shape[0]-.5)
        col=round((x/size[0]+.5)*image.shape[1]-.5)
        assert np.min(np.max(image[row-1:row+2,col-2:col+3,:3],axis=2))<45


def test_outer_diamonds_include_their_inner_half():
    layout=adapt_contoured_frame(analyze_layout(source()))
    assert layout.border_depth_px>=34
    assert np.max(layout.strip[32,:,2])>170


def test_missing_periodic_picture_does_not_activate_contour():
    image=Image.new('RGB',(800,480),'white')
    original=analyze_layout(image)
    assert adapt_contoured_frame(original) is original


def test_central_flower_is_not_stretched_or_shrunk_as_a_picture():
    im=source()
    draw=ImageDraw.Draw(im)
    draw.rectangle((95,90,704,389),fill='black')
    draw.ellipse((380,220,420,260),fill=(230,215,185))
    layout=adapt_contoured_frame(analyze_layout(im))
    assert layout.contoured_frame is not None
    spec=DesignSpec(diameter_cm=139,height_cm=87,straight_cm=108,border=BorderSpec(0,0,0))
    material=PreparedMaterial(layout.image,layout.strip,MaterialSpec(),layout)
    image=np.asarray(render_source(spec,material,max_side=1600))
    cy,cx=np.array(image.shape[:2])//2
    patch=image[cy-60:cy+60,cx-60:cx+60,:3]
    yy,xx=np.nonzero(np.min(patch,axis=2)>170)
    assert abs(np.ptp(xx)-np.ptp(yy))<=2
    assert np.ptp(xx)>60


def test_material_name_activates_only_verified_gothic_structure(tmp_path):
    from shape_crop.services.materials import prepare
    gothic=tmp_path/'双面格-定制-定制尺寸-哥特玫瑰;80x130cm.jpg'
    other=tmp_path/'双面格-定制-定制尺寸-普通画框;80x130cm.jpg'
    source().save(gothic,quality=100,subsampling=0)
    source().save(other,quality=100,subsampling=0)
    selected=prepare(MaterialSpec(path=str(gothic)),preview=True)
    assert selected.source_layout.contoured_frame is not None
    assert not selected.source_layout.contoured_frame.stroke.flags.writeable
    assert prepare(MaterialSpec(path=str(other)),preview=True).source_layout.contoured_frame is None


def test_inner_circle_uses_same_curved_frame():
    layout=adapt_contoured_frame(analyze_layout(source()))
    material=PreparedMaterial(layout.image,layout.strip,MaterialSpec(),layout)
    spec=DesignSpec(diameter_cm=139,height_cm=87,straight_cm=108,inner_diameter_cm=40,border=BorderSpec(0,0,0))
    result=np.asarray(render_source(spec,material,max_side=1000))
    assert result.shape[1]==1000
    assert result[result.shape[0]//2,500,3]==255
    inner_scale=40/layout.height_px
    radius=20-layout.contoured_frame.inset_px*inner_scale
    for y in (-4,0,4):
        x=np.sqrt(radius**2-y**2)+.5
        row=round((y/87+.5)*result.shape[0]-.5)
        col=round((x/139+.5)*result.shape[1]-.5)
        colour=result[row,col,:3]
        assert 40<np.min(colour) and np.max(colour)<180, '内圆框外必须保留棕色菱格背景'
