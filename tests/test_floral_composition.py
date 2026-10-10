"""Inset textures and corner bouquets must remain separate from perimeter bands."""
from dataclasses import replace
import numpy as np
import pytest
from PIL import Image,ImageDraw
from shape_crop.services.materials import prepare
from shape_crop.models.design import MaterialSpec,DesignSpec,BorderSpec
from shape_crop.core.source_renderer import render_source


def patterned_source():
    image=Image.new('RGB',(600,400),(193,180,155))
    draw=ImageDraw.Draw(image)
    draw.rectangle((0,0,599,399),outline='black',width=1)
    draw.rectangle((12,12,587,387),fill=(255,248,235))
    draw.rectangle((22,24,577,375),outline=(193,180,155),width=1)
    draw.rectangle((50,64,549,335),fill=(193,180,155))
    for y in range(64,330,30):
        for x in range(50,550,35):
            draw.ellipse((x,y,x+15,y+20),outline=(255,248,235),width=2)
    return image


def corner_source(top=18):
    image=Image.new('RGB',(600,400),'white'); draw=ImageDraw.Draw(image)
    draw.rectangle((0,0,599,399),outline='black',width=7)
    for x in range(15,586,10):
        for y in (15,384): draw.ellipse((x-2,y-2,x+2,y+2),fill='black')
    for y in range(15,385,10):
        for x in (15,584): draw.ellipse((x-2,y-2,x+2,y+2),fill='black')
    for x,y in ((420,top),(465,65),(500,108),(18,235),(60,280),(130,325)):
        draw.ellipse((x,y,x+70,y+60),fill='white',outline='black',width=2)
        draw.line((x+10,y+20,x+60,y+40),fill='black',width=2)
    draw.multiline_text((260,350),'The love of\nflowers',fill='black',spacing=2)
    return image


def material(tmp_path,image,name):
    path=tmp_path/(name+';85X140cm.png'); image.save(path)
    return prepare(MaterialSpec(path=str(path)))


def spec():
    return DesignSpec(diameter_cm=139,height_cm=87,straight_cm=108,shape_mode='arc',border=BorderSpec(0,0,0),dpi=30)


def test_patterned_inset_keeps_its_height_and_follows_curved_contour(tmp_path):
    source=material(tmp_path,patterned_source(),'素缕花肆')
    assert getattr(source.source_layout,'patterned_inset',None) is not None
    result=np.asarray(render_source(spec(),source,max_side=900))
    middle=result[:,result.shape[1]//2,:3]
    pattern=np.max(np.abs(middle.astype(float)-(193,180,155)),axis=1)<12
    assert np.mean(pattern[60:-60])>.50,'中央花纹不能被误识别边框挤压成窄条'


@pytest.mark.parametrize('top',[2,18])
def test_corner_bouquets_and_bottom_text_are_kept_as_independent_layers(tmp_path,top):
    source=material(tmp_path,corner_source(top),'花漾之约')
    composition=getattr(source.source_layout,'corner_composition',None)
    assert composition is not None and len(composition.groups)==2
    assert composition.text_box is not None
    assert composition.text_box[3]>=372, '英文第二行不能被花组误识别边界裁掉'
    result=np.asarray(render_source(spec(),source,max_side=900))
    h,w=result.shape[:2]
    center=result[int(h*.43):int(h*.57),int(w*.40):int(w*.60),:3]
    assert np.count_nonzero(np.max(center,axis=2)<80)>20,'英文必须完整移到中央'
    assert all(not group.alpha.flags.writeable for group in composition.groups)
    left_group=composition.groups[0]
    a,b,_,_=left_group.box
    assert left_group.alpha[305-b,12-a]<15, '原矩形边框白带不能进入花瓣蒙版'

    if top==2:
        group=composition.groups[1]
        a,b,_,_=group.box
        assert group.alpha[12-b,455-a]>230, '贴着原黑边的花瓣必须保留白色填充'


def test_corner_text_crop_does_not_include_partial_bottom_dot_row(tmp_path):
    image=corner_source()
    # One faint edge row can be missed by the narrow frame probe while the
    # wider text probe still sees isolated dots there.
    draw=ImageDraw.Draw(image)
    for x in range(250,391,10):
        draw.ellipse((x-2,378,x+2,382),fill='black')
    source=material(tmp_path,image,'花漾之约')
    composition=source.source_layout.corner_composition
    assert composition is not None
    assert composition.text_box[3]<378, '边框圆点不能混入中央英文选区'


def test_joined_corner_frame_dots_are_not_moved_with_bouquet(tmp_path):
    image=corner_source()
    draw=ImageDraw.Draw(image)
    draw.ellipse((12,373,18,383),fill='black')
    draw.ellipse((17,379,26,387),fill='black')
    source=material(tmp_path,image,'花漾之约')
    group=source.source_layout.corner_composition.groups[0]
    a,b,_,_=group.box
    assert group.alpha[377-b,15-a]<15, '角落相连的边框圆点不能作为花瓣移动'


@pytest.mark.parametrize('separate',[False,True])
def test_inner_circle_preserves_centered_corner_composition_text(tmp_path,separate):
    bouquet=material(tmp_path,corner_source(),'花漾之约')
    outer=material(tmp_path,patterned_source(),'素缕花肆') if separate else bouquet
    result=np.asarray(render_source(replace(spec(),inner_diameter_cm=30),outer,bouquet if separate else None,max_side=900))
    h,w=result.shape[:2]
    center=result[int(h*.46):int(h*.54),int(w*.45):int(w*.55),:3]
    assert np.count_nonzero(np.max(center,axis=2)<80)>20, '内圆不能覆盖已居中的英文'
