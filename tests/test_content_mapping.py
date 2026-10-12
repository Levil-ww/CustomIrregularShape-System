"""Content coordinates must respect the analysed source crop bounds."""
import numpy as np

from shape_crop.core.content_mapping import ContentMapping
from shape_crop.services.layout_analysis import SourceLayout


def test_content_mapping_preserves_pixels_at_crop_corners():
    image = np.full((8, 10, 3), 240, dtype=np.uint8)
    image[2, 2] = (20, 40, 60)
    image[5, 7] = (80, 100, 120)
    layout = SourceLayout(
        image=image,
        strip=image[:2],
        border_depth_px=2,
        width_px=10,
        height_px=8,
        report='',
        content=image[2:6, 2:8],
        content_box_px=(2, 2, 8, 6),
    )

    mapping = ContentMapping.create(layout, 10, 8, 2)
    result = mapping.sample(layout, np.array([-2.5, 2.5]), np.array([-1.5, 1.5]))

    np.testing.assert_array_equal(result, [[20, 40, 60], [80, 100, 120]])
