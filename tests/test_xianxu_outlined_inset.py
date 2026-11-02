"""Outlined Xianxu panels follow arcs while retaining their original inner trim."""
from pathlib import Path
import numpy as np
import pytest
from PIL import Image, ImageDraw
from shape_crop.models.design import MaterialSpec, DesignSpec, BorderSpec
from shape_crop.services.materials import prepare
from shape_crop.core.source_renderer import render_source


def outlined_source(beads=False):
    yy,xx=np.mgrid[:360,:600]
    p=np.where(((xx//8+yy//8)%2)[...,None],(235,225,205),(175,165,145)).astype(np.uint8)
    p[60:300,55:545]=np.where(((xx[60:300,55:545]//12+yy[60:300,55:545]//12)%2)[...,None],(225,220,210),(205,200,190))
    image=Image.fromarray(p);draw=ImageDraw.Draw(image)
    draw.rectangle((0,0,599,359),outline='black',width=10)
    if beads:
        for x in range(60,542,8):
            for y in (60,299):draw.ellipse((x-3,y-3,x+3,y+3),fill=(15,10,8))
        for y in range(65,297,8):
            for x in (55,544):draw.ellipse((x-3,y-3,x+3,y+3),fill=(15,10,8))
    draw.rectangle((55,60,544,299),outline=(15,10,8),width=2)
    return image


@pytest.mark.parametrize('pattern,beads',[('闲叙浅川',False),('闲叙・浅川',False),('闲叙.浅川',False),('闲叙素年',True),('闲叙·素年',True),('闲叙.素年',True)])
@pytest.mark.parametrize('factor',[1,5])
def test_outlined_panel_and_complete_trim_follow_the_arc(tmp_path,pattern,beads,factor):
    path=tmp_path/f'{pattern};80x140cm.png'
    outlined_source(beads).resize((600*factor,360*factor),Image.Resampling.NEAREST).save(path)
    material=prepare(MaterialSpec(str(path)),preview=False);layout=material.source_layout
    frame=layout.contoured_frame
    assert frame is not None,'浅川、素年中央细框不能继续按独立矩形缩小'
    assert frame.uniform_texture
    assert frame.stroke.shape[0] > 0 and np.min(frame.stroke)<40,'原细描边必须保留'
    if beads:
        coverage=np.mean(np.max(frame.stroke,axis=2)<80,axis=1)
        assert np.any((coverage>.05)&(coverage<.9)),'素年细框外侧的圆点末端必须保留'
        assert frame.inset_px<=57*factor,'缩略识别不能把原图圆点的外侧末端裁掉'
    for w,h,straight in ((130,75,95),(180,80,100)):
        design=DesignSpec(diameter_cm=w,height_cm=h,straight_cm=straight,shape_mode='arc',border=BorderSpec(0,0,0))
        pixels=np.asarray(render_source(design,material,max_side=1000))
        dark=np.max(pixels[...,:3],axis=2)<80
        # A straight original side must not survive inside the curved content.
        assert dark[pixels.shape[0]//2-10:pixels.shape[0]//2+10,250:750].sum()==0,'旧矩形描边不能残留在中央'
        # Both curved sides retain a black inner outline distinct from the rim.
        row=dark[pixels.shape[0]//2]
        transitions=np.flatnonzero(np.diff(row.astype(int)))
        assert len(transitions)>=6,'左右两侧必须同时保留外黑边和中央细线'


@pytest.mark.parametrize('pattern',['闲叙浅川','闲叙素年'])
def test_incomplete_outline_does_not_force_an_unverified_curved_frame(tmp_path,pattern):
    image=outlined_source()
    ImageDraw.Draw(image).rectangle((180,58,420,64),fill=(225,220,210))
    path=tmp_path/f'{pattern};80x140cm.png'
    image.save(path)
    assert prepare(MaterialSpec(str(path)),preview=True).source_layout.contoured_frame is None
