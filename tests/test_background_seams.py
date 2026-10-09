"""Independent artwork must not expose its old cleanup rectangle in the background."""
from dataclasses import replace
import numpy as np
import pytest
from PIL import Image, ImageDraw
from shape_crop.services.layout_analysis import analyze_layout
from shape_crop.services.framed_artwork import FramedArtwork
from shape_crop.core.content_mapping import ContentMapping
from shape_crop.core.framed_artwork_mapping import sample_framed_artwork


@pytest.mark.parametrize('flat',[True,False])
@pytest.mark.parametrize('axis',[0,1])
def test_old_panel_boundary_does_not_create_background_jump(flat,axis):
    y,x=np.indices((400,650))
    shade=(120+x*.08+y*.06).astype(np.uint8)
    image=Image.fromarray(np.repeat(shade[...,None],3,axis=2))
    draw=ImageDraw.Draw(image)
    draw.rectangle((0,0,649,399),outline='black',width=12)
    draw.rectangle((75,80,574,319),fill=(242,232,220),outline='black',width=2)
    bg=(160,160,160)
    art=FramedArtwork((75.,80.,575.,320.),(12.,12.,638.,388.),np.array([[bg]],dtype=np.uint8),(0,0),True,bg if flat else None,(73.,78.,577.,322.))
    layout=replace(analyze_layout(image),framed_artwork=art)
    native=.2
    mapping=ContentMapping(.1,324.5,199.5,12,12)
    # The old rectangle boundary is now well outside the smaller picture.
    source_u=np.arange(68,84,dtype=float)[None,:] if axis==0 else np.full((1,16),320.)
    source_v=np.full((1,16),199.) if axis==0 else np.arange(71,87,dtype=float)[None,:]
    result=sample_framed_artwork(layout,mapping,native,(source_u-324.5)*native,(source_v-199.5)*native,.001)
    jumps=np.max(np.abs(np.diff(result.astype(float),axis=1)),axis=2)
    assert jumps.max()<4, '旧中央框位置出现背景色或纹理的矩形拼接边界'


def test_texture_period_is_refined_in_original_pixels():
    from shape_crop.services.framed_artwork import _textured_rectangle
    y, x = np.indices((1800,2600))
    shade = 175 + 30*np.sin(x*2*np.pi/157) + 25*np.cos(y*2*np.pi/223)
    full = np.repeat(shade.astype(np.uint8)[...,None],3,axis=2)
    image = Image.fromarray(full)
    ImageDraw.Draw(image).rectangle((200,200,1999,1299),fill=(50,50,50))
    probe = image.copy()
    probe.thumbnail((1200,1200))
    sx,sy = image.width/probe.width, image.height/probe.height
    box = tuple(round(v/r) for v,r in zip((200,200,2000,1300),(sx,sy,sx,sy)))
    art = _textured_rectangle(image,np.asarray(probe),box,(0.,0.,2600.,1800.),sx,sy)
    assert art is not None
    assert art.tile.shape[0] % 223 == 0 and art.tile.shape[1] % 157 == 0, 'Native period must match the original texture'
    expected_box = tuple(float(v*r) for v,r in zip(box,(sx,sy,sx,sy)))
    assert art.box == expected_box, 'Central rectangle must not include an extra ring of background stripes'
