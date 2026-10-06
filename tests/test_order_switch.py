"""The actual regression: switch to a different uncached large source."""
from unittest.mock import patch
from PIL import Image, ImageDraw
from shape_crop.models.design import MaterialSpec
from shape_crop.services import materials


def test_different_large_orders_prepare_bounded_preview_sources(tmp_path):
    dimensions = []
    analyze = materials.analyze_layout
    def measured(image):
        dimensions.append(image.size)
        return analyze(image)
    for name, color in [('first', 'red'), ('second', 'blue')]:
        path = tmp_path / (name + '.jpg')
        image = Image.new('RGB', (4000, 2400), color)
        ImageDraw.Draw(image).rectangle((0, 0, 3999, 2399), outline='black', width=30)
        image.save(path, quality=95)
        image.close()
        with patch.object(materials, 'analyze_layout', side_effect=measured):
            preview = materials.prepare(MaterialSpec(str(path)), preview=True)
        assert max(preview.source_layout.image.shape[:2]) <= 2400
    assert all(max(size) <= 2400 for size in dimensions), '换订单后仍分析全尺寸素材'


def test_export_keeps_original_resolution_after_preview(tmp_path):
    path = tmp_path / 'large.jpg'
    image = Image.new('RGB', (3000, 1800), 'red')
    image.save(path)
    image.close()
    material = MaterialSpec(str(path))
    preview = materials.prepare(material, True)
    full = materials.prepare(material, False)
    assert preview.source_layout.width_px <= 2400
    assert full.source_layout.width_px == 3000
    assert full.source_layout.height_px == 1800
    assert preview is not full
