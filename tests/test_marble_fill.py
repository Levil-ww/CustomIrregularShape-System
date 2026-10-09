"""Marble veins are full-bleed content, with only a thin black outline."""
import numpy as np
import pytest
from PIL import Image
from shape_crop.services.materials import prepare
from shape_crop.models.design import MaterialSpec, DesignSpec, BorderSpec
from shape_crop.core.source_renderer import render_source


def marble_image(width=600, height=400):
    pixels = np.full((height, width, 3), 90, dtype=np.uint8)
    yy, xx = np.mgrid[:height, :width]
    pixels[(xx + 2*yy) % 137 < 3] = 220
    pixels[:3] = pixels[-3:] = 0
    pixels[:, :3] = pixels[:, -3:] = 0
    return Image.fromarray(pixels)


@pytest.mark.parametrize('name', ['白色大理石1', '白色大理石2', '黑色大理石1', '黑色大理石5', '灰色大理石', '褐色大理石', '灰色大理石1号', '褐色大理石1', '浅灰大理石'])
def test_marble_extracts_only_black_outline(tmp_path, name):
    path = tmp_path / f'双面格-定制-定制尺寸-{name};85X140cm.jpg'
    marble_image().save(path, quality=95)
    material = prepare(MaterialSpec(path=str(path)))
    layout = material.source_layout
    assert layout.content_box_px == pytest.approx((3, 3, 597, 397), abs=1)
    assert layout.border_depth_px <= 4, '石纹不能成为宽边框'
    assert layout.floating_artwork is None and layout.framed_artwork is None


@pytest.mark.parametrize('size', [(600,400), (1200,80)])
@pytest.mark.parametrize('mode', ['arc','circular'])
def test_marble_keeps_texture_near_outline_without_widening_or_failure(tmp_path, size, mode):
    path = tmp_path / '双面格-定制-定制尺寸-黑色大理石5;75X120cm.jpg'
    marble_image(*size).save(path, quality=95)
    material = prepare(MaterialSpec(path=str(path)))
    spec = DesignSpec(diameter_cm=151, height_cm=91, shape_mode=mode, straight_cm=120.5, border=BorderSpec(0,0,0))
    result = np.asarray(render_source(spec,material,max_side=900))
    top = result[8, result.shape[1]//2-60:result.shape[1]//2+60,:3]
    assert np.mean(np.min(top,axis=1)>60) > .95, '细线内侧必须直接是石纹，不能加宽黑色带'
    assert np.max(result[0,result.shape[1]//2,:3]) < 30, '保留外沿黑线'


def test_decorated_marble_keeps_normal_border_analysis(tmp_path):
    path = tmp_path / '双面格-定制-定制尺寸-城堡皇冠大理石;85X140cm.jpg'
    image = marble_image()
    pixels = np.asarray(image).copy()
    pixels[30:-30,30:-30] = np.random.default_rng(7).integers(70,210,(340,540,3),dtype=np.uint8)
    pixels[:30] = pixels[-30:] = 0
    pixels[:,:30] = pixels[:,-30:] = 0
    Image.fromarray(pixels).save(path, quality=95)
    assert prepare(MaterialSpec(path=str(path))).source_layout.border_depth_px >= 30


def test_marble_without_source_outline_gets_a_fine_black_stroke(tmp_path):
    path = tmp_path / '黑色大理石5;26X415cm.jpg'
    Image.new('RGB',(600,100),(90,90,90)).save(path)
    spec = DesignSpec(diameter_cm=151,height_cm=91,shape_mode='arc',straight_cm=120.5,border=BorderSpec(0,0,0),dpi=150)
    result = np.asarray(render_source(spec,prepare(MaterialSpec(path=str(path)))))
    middle = result.shape[1]//2
    assert np.max(result[0,middle,:3]) < 30
    assert np.min(result[4,middle,:3]) > 60


def test_outline_includes_outer_jpeg_antialias_row(tmp_path):
    path = tmp_path / '黑色大理石5;26X415cm.jpg'
    pixels = np.asarray(marble_image()).copy()
    pixels[0] = pixels[-1] = 25
    pixels[:,0] = pixels[:,-1] = 25
    Image.fromarray(pixels).save(path,quality=95)
    assert prepare(MaterialSpec(path=str(path))).source_layout.border_depth_px == 3


def test_inner_circle_marble_uses_its_own_cover_scale(tmp_path):
    outer_path = tmp_path / '白色大理石1;85X140cm.jpg'
    inner_path = tmp_path / '黑色大理石5;26X415cm.jpg'
    marble_image().save(outer_path)
    pixels = np.repeat(np.linspace(40,200,80,dtype=np.uint8)[:,None,None],600,axis=1)
    pixels = np.repeat(pixels,3,axis=2)
    pixels[:3] = pixels[-3:] = 0
    pixels[:,:3] = pixels[:,-3:] = 0
    Image.fromarray(pixels).save(inner_path,quality=95)
    spec = DesignSpec(diameter_cm=151,height_cm=91,shape_mode='arc',straight_cm=120.5,inner_diameter_cm=40,border=BorderSpec(0,0,0),dpi=30)
    result = np.asarray(render_source(spec,prepare(MaterialSpec(path=str(outer_path))),prepare(MaterialSpec(path=str(inner_path)))))
    rows = [round((y/91+.5)*result.shape[0]-.5) for y in (7,13)]
    values = [int(result[row,result.shape[1]//2,0]) for row in rows]
    assert values[1]-values[0] > 20, '内圆石纹不得因细线缩放而越界夹取成同一条纹'


def test_thicker_source_outline_is_removed_without_a_wide_output_band(tmp_path):
    path = tmp_path / '白色大理石1;85X140cm.jpg'
    pixels = np.asarray(marble_image()).copy()
    pixels[:60] = pixels[-60:] = 0
    pixels[:,:60] = pixels[:,-60:] = 0
    Image.fromarray(pixels).save(path,quality=95)
    material = prepare(MaterialSpec(path=str(path)))
    spec = DesignSpec(diameter_cm=151,height_cm=91,shape_mode='arc',straight_cm=120.5,border=BorderSpec(0,0,0))
    result = np.asarray(render_source(spec,material,max_side=900))
    assert np.min(result[8,result.shape[1]//2,:3]) > 60, '原图粗黑框必须裁除，输出仅保留细线'
