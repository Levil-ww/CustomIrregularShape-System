"""Material ranking balances size proximity against excessive ratio differences."""
from pathlib import Path

import pytest

from shape_crop.models.request import ProductRequest
from shape_crop.services.catalog import match_material
from shape_crop.services.filename_parser import parse_filename
from shape_crop.services.workflow import resolve_request


@pytest.mark.parametrize(('target_size', 'sizes', 'expected'), [
    ('90x138', ['60x92', '93x140'], '93x140'),
    ('90x138', ['72x110.4', '93x140'], '93x140'),
    ('90x138', ['90x120', '75x115'], '75x115'),
    ('90x138', ['60x92'], '60x92'),
    # At exactly 5%, size wins; just outside it, the eligible candidate wins.
    ('100x100', ['105x100', '80x80'], '105x100'),
    ('100x100', ['105.001x100', '80x80'], '80x80'),
    # With no eligible candidate, ratio takes priority over size.
    ('100x100', ['100x80', '79.5x75'], '79.5x75'),
])
def test_size_priority_with_ratio_limit_and_fallback(tmp_path, target_size, sizes, expected):
    for size in sizes:
        (tmp_path / f'花幔;{size}cm.jpg').touch()
    match = match_material(parse_filename(f'花幔;{target_size}cm'), tmp_path)
    assert Path(match.path).name == f'花幔;{expected}cm.jpg'


@pytest.mark.parametrize(('size', 'small', 'fallback'), [
    ('60x92', True, False),
    ('72x110.4', False, False),
    ('93x140', False, False),
    ('90x120', False, True),
    ('50x100', True, True),
    ('71.9x138', True, True),
])
def test_workflow_warns_without_rejecting_material(tmp_path, size, small, fallback):
    source = tmp_path / f'花幔;{size}cm.jpg'
    source.touch()
    design, detail = resolve_request(ProductRequest('花幔;90x138cm', str(tmp_path)))
    assert design.material.path == str(source)
    assert ('素材尺寸偏小' in detail) == small
    assert ('已使用兜底素材' in detail) == fallback


def test_workflow_includes_exactly_five_percent_without_fallback_warning(tmp_path):
    (tmp_path / '花幔;105x100cm.jpg').touch()
    _, detail = resolve_request(ProductRequest('花幔;100x100cm', str(tmp_path)))
    assert '比例差 5.00%' in detail
    assert '已使用兜底素材' not in detail


def test_equal_candidates_use_deterministic_path_order(tmp_path):
    for folder in ('b', 'a'):
        directory = tmp_path / folder
        directory.mkdir()
        (directory / '花幔;93x140cm.jpg').touch()
    match = match_material(parse_filename('花幔;90x138cm'), tmp_path)
    assert Path(match.path).parent.name == 'a'


def test_matching_uses_dimension_overrides(tmp_path):
    for size in ('90x138', '93x140'):
        (tmp_path / f'花幔;{size}cm.jpg').touch()
    design, _ = resolve_request(ProductRequest(
        '花幔;90x138cm', str(tmp_path), width_cm=140, height_cm=93))
    assert Path(design.material.path).name == '花幔;93x140cm.jpg'


def test_material_override_has_no_automatic_match_warning():
    design, detail = resolve_request(ProductRequest(
        '花幔;90x138cm', material_override='指定素材.jpg'))
    assert design.material.path == '指定素材.jpg'
    assert detail == '使用指定素材\n素材：指定素材.jpg'
