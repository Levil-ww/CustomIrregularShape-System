"""Native edge refinement must retain the final thin separator."""
import numpy as np
from PIL import Image
from shape_crop.services.layout_analysis import analyze_layout


def test_native_analysis_keeps_thin_black_separator():
    pixels = np.full((3000, 4800, 3), [254, 242, 226], dtype=np.uint8)
    pixels[:150] = [120, 76, 43]
    pixels[190:194] = 0
    # Dense artwork starts directly after the last thin outline. Its median
    # stays near the background, so the outline is the strongest colour jump.
    pixels[194:-194, 194:-194] = np.random.default_rng(4).integers(
        100, 255, (2612, 4412, 3), dtype=np.uint8)
    pixels[-194:] = pixels[:194][::-1]
    pixels[:, :150] = [120, 76, 43]
    pixels[:, 150:190] = [254, 242, 226]
    pixels[:, 190:194] = 0
    pixels[:, -194:] = pixels[:, :194][:, ::-1]
    layout = analyze_layout(Image.fromarray(pixels))
    assert layout.border_depth_px >= 194, '原尺寸分析截掉了内侧黑色分隔线'
    assert np.count_nonzero(np.max(layout.strip, axis=(1, 2)) < 40) >= 4
