from dataclasses import replace
import math
import numpy as np
import pytest
from PIL import Image
from shape_crop.core.geometry import ArcBand, CircularBand, create_shape
from shape_crop.models.design import DesignSpec, BorderSpec, MaterialSpec
from shape_crop.models.request import ProductRequest
from shape_crop.services.workflow import resolve_request, output_path
from shape_crop.services.project_io import load_project, save_project
from shape_crop.services.design_service import generate
from shape_crop.services.sketch_recognition import associate_dimensions


@pytest.mark.parametrize('width,height,straight', [(138, 86, 108), (130, 80, 103), (150, 90, 120.5)])
def test_arc_compensates_only_width_height(width, height, straight, tmp_path):
    request = ProductRequest(f'花幔;{height}x{width}cm', material_override='unused.jpg',
                             shape_mode='arc', straight_cm=straight)
    design, _ = resolve_request(request)
    shape = create_shape(design)
    assert (shape.diameter, shape.height, shape.chord) == (width + 1, height + 1, straight)
    assert shape.depth((width + 1) / 2, 0) == pytest.approx(0, abs=1e-10)
    assert shape.depth(straight / 2, (height + 1) / 2) == pytest.approx(0, abs=1e-10)
    assert output_path(request, tmp_path).endswith(request.target_name + '.jpg')


@pytest.mark.parametrize('width,height,straight', [(139,87,108), (131,81,103), (151,91,120.5), (200,80,190)])
def test_arc_parallel_insets_and_arc_length_joints(width, height, straight):
    shape = ArcBand(width, height, straight)
    for distance in (0, 1, 6):
        inner = shape.inset(distance)
        assert inner.radius == pytest.approx(shape.radius - distance)
        assert inner.center == pytest.approx(shape.center)
        assert inner.diameter == pytest.approx(width - 2 * distance)
        assert inner.height == pytest.approx(height - 2 * distance)
        for theta in np.linspace(-inner.angle, inner.angle, 9)[1:-1]:
            x = inner.center + inner.radius * math.cos(theta)
            y = inner.radius * math.sin(theta)
            assert shape.depth(x, y) == pytest.approx(distance, abs=1e-9)
        arc = 2 * inner.radius * inner.angle
        for x, y, expected in [(-inner.chord / 2, -inner.half_height, 0),
                               (inner.chord / 2, -inner.half_height, inner.chord),
                               (inner.chord / 2, inner.half_height, inner.chord + arc),
                               (-inner.chord / 2, inner.half_height, 2 * inner.chord + arc)]:
            assert inner.boundary_coordinate(x, y) == pytest.approx(expected, abs=1e-8)


def test_arc_reduces_to_circle_and_remains_symmetric():
    circular = CircularBand(200, 83.76)
    arc = ArcBand(200, 83.76, circular.chord)
    assert arc.center == pytest.approx(0, abs=1e-10)
    assert arc.perimeter == pytest.approx(circular.perimeter)
    x = np.linspace(-100, 100, 151)[None, :]
    y = np.linspace(-41, 41, 83)[:, None]
    np.testing.assert_allclose(arc.depth(x, y), circular.depth(x, y), atol=1e-9)
    np.testing.assert_allclose(arc.depth(x, y), arc.depth(-x, -y), atol=1e-9)


@pytest.mark.parametrize('values', [(139,87,0), (139,87,139), (139,87,140), (139,87,20),
                                    (139,87,float('nan')), (0,1,1)])
def test_invalid_arc(values):
    with pytest.raises(ValueError):
        ArcBand(*values)


def test_arc_project_round_trip_and_old_project_defaults(tmp_path):
    design = replace(DesignSpec(), diameter_cm=139, height_cm=87, shape_mode='arc', straight_cm=108)
    path = tmp_path / 'arc.json'
    save_project(path, design)
    assert load_project(path) == design
    import json
    payload = json.loads(path.read_text(encoding='utf-8'))
    del payload['design']['shape_mode']
    del payload['design']['straight_cm']
    path.write_text(json.dumps(payload), encoding='utf-8')
    assert load_project(path).shape_mode == 'circular'


@pytest.mark.parametrize('layout', ['source', 'manual'])
def test_both_renderers_follow_arc_mask(tmp_path, layout):
    path = tmp_path / 'source.jpg'
    Image.new('RGB', (400, 260), (240, 220, 190)).save(path)
    design = DesignSpec(diameter_cm=139, height_cm=87, straight_cm=108, shape_mode='arc', dpi=12,
                        border=BorderSpec(0,0,0), material=MaterialSpec(str(path), layout=layout))
    result = np.asarray(generate(design))
    h, w = result.shape[:2]
    x = ((np.arange(w) + .5) / w - .5) * 139
    y = ((np.arange(h) + .5) / h - .5) * 87
    depth = ArcBand(139,87,108).depth(x[None,:], y[:,None])
    assert np.all(result[:,:,3][depth > .5] == 255)
    assert np.all(result[:,:,3][depth < -.5] == 0)


def test_arc_keeps_asymmetric_artwork_and_complete_border(tmp_path):
    from shape_crop.core.sampling import sample
    from shape_crop.services.layout_analysis import analyze_layout
    source = np.zeros((260,400,3), dtype=np.uint8)
    source[5:-5,5:-5] = np.random.default_rng(29).integers(40,235,(250,390,3),dtype=np.uint8)
    path = tmp_path / 'asymmetric.png'
    Image.fromarray(source).save(path)
    assert analyze_layout(Image.fromarray(source)).border_depth_px == 5
    design = DesignSpec(diameter_cm=139,height_cm=87,straight_cm=108,shape_mode='arc',dpi=20,
                        border=BorderSpec(0,0,0),material=MaterialSpec(str(path)))
    output = tmp_path / 'result.png'
    result = np.asarray(generate(design, output=output))
    h,w = result.shape[:2]
    x = ((np.arange(w)+.5)/w-.5)*139
    y = ((np.arange(h)+.5)/h-.5)*87
    scale = 139/400
    expected = sample(source,x[None,:]/scale+199.5,y[:,None]/scale+129.5)
    depth = ArcBand(139,87,108).depth(x[None,:],y[:,None])
    interior = depth > 5*scale + 2*139/w
    np.testing.assert_allclose(result[:,:,:3][interior], expected[interior], atol=1)
    frame = (depth > .5) & (depth < 1)
    np.testing.assert_array_equal(result[:,:,:3][frame],0)
    with Image.open(output) as saved:
        assert saved.size == design.pixel_size()
        # PNG stores integer pixels/metre; half a unit is 0.0127 DPI.
        assert saved.info['dpi'][0] == pytest.approx(20, abs=.013)


def word(text, x, y, width=10, height=10):
    return dict(text=text, x=x, y=y, width=width, height=height)


def test_sketch_positions_split_digits_and_decimal():
    result = associate_dimensions([word('1',48,27,4), word('38',54,27,9), word('86',3,55),
                                   word('108',48,80,15)],100,100)
    assert (result.width_cm,result.height_cm,result.straight_cm) == (138,86,108)
    result = associate_dimensions([word('150',48,27),word('90',3,55),word('120.5',48,80)],100,100)
    assert result.straight_cm == 120.5


def test_sketch_two_dimensions_and_ambiguity():
    result = associate_dimensions([word('200cm',80,45),word('83.76cm',40,30)],100,100)
    assert (result.width_cm,result.height_cm,result.straight_cm) == (200,83.76,None)
    result = associate_dimensions([word('108',48,80)],100,100)
    assert result.width_cm is None


def test_sketch_decimal_marker_separate_from_digits():
    result = associate_dimensions([word('83',40,30,8,10), word('?',49,38,1,2),
                                   word('76',51,30,8,10),word('200',80,35)],100,100)
    assert (result.width_cm, result.height_cm) == (200, 83.76)
