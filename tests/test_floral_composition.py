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


@pytest.mark.parametrize('size', [(600,400),(1200,800)])
def test_peony_brocade_uses_patterned_inset_layout_at_every_source_size(tmp_path,size):
    image=patterned_source().resize(size,Image.Resampling.LANCZOS)
    source=material(tmp_path,image,'牡丹织锦')
    assert source.source_layout.patterned_inset is not None, '牡丹织锦各尺寸应统一按中央花纹内框排版'
    assert source.source_layout.category=='中央花纹内框类'


def test_peony_side_motifs_follow_curve_instead_of_being_cut_off(tmp_path):
    image=patterned_source()
    draw=ImageDraw.Draw(image)
    draw.rectangle((51,73,65,85),fill=(0,0,240))
    draw.rectangle((534,314,548,326),fill=(0,0,240))
    source=material(tmp_path,image,'牡丹织锦')
    result=np.asarray(render_source(spec(),source,max_side=1000))
    blue=(result[...,2]>180)&(result[...,0]<20)&(result[...,1]<20)
    assert blue[:,:500].sum()>10, '牡丹左侧花纹应顺着内弧保留'
    assert blue[:,500:].sum()>10, '牡丹右侧花纹应顺着内弧保留'


@pytest.mark.parametrize('size', [(655,400),(1300,800),(2620,1600)])
@pytest.mark.parametrize('preview', [False,True])
@pytest.mark.parametrize('filename', ['牡丹织锦;80X131CM.png','双面格-标准-80x131-牡丹织锦;80x131.png'])
def test_peony_shallow_gutter_curves_with_each_target_size(tmp_path,size,preview,filename):
    # The real 80x130/131 sources start their black floral panel at 9% height,
    # inside the old fixed background probe (8-14%).
    image=Image.new('RGB',(655,400),'black')
    draw=ImageDraw.Draw(image)
    draw.rectangle((12,12,642,387),fill=(255,241,228))
    for x in range(14,642,5):
        for y in (12,387):
            draw.ellipse((x-2,y-2,x+2,y+2),fill=(230,198,158),outline='black')
    draw.rectangle((41,37,613,362),fill='black')
    for y in range(39,360,21):
        for x in range(44,610,27):
            draw.ellipse((x,y,x+9,y+13),outline=(230,198,158),width=2)
    path=tmp_path/filename
    image.resize(size,Image.Resampling.LANCZOS).save(path)
    source=prepare(MaterialSpec(path=str(path)),preview=preview)
    assert source.source_layout.patterned_inset is not None, '窄留白不能使中央花纹退回矩形画框'
    for width,height,straight in ((136,84,107),(138,76.8,110),(180,90,150)):
        design=replace(spec(),diameter_cm=width,height_cm=height,straight_cm=straight)
        result=np.asarray(render_source(design,source,max_side=700))
        h,w=result.shape[:2]
        def left_edge(row):
            background=np.max(np.abs(result[row,:w//2,:3].astype(float)-(255,241,228)),axis=1)<8
            background &= result[row,:w//2,3]>240
            changes=np.diff(np.r_[False,background,False].astype(np.int8))
            starts=np.flatnonzero(changes==1); ends=np.flatnonzero(changes==-1)
            gaps=ends[(ends-starts)>w*.02]
            assert gaps.size, '花纹与圆点边框之间应保留完整留白'
            return gaps[0]
        assert left_edge(round(h*.18))>left_edge(h//2)+w*.02, '中间花纹左右边缘必须随外轮廓弯曲'


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
