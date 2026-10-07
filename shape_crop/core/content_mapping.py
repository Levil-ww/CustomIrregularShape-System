"""Uniform source mapping with clearance-preserving fits for isolated artwork."""
from dataclasses import dataclass
import numpy as np
from shape_crop.core.sampling import sample


@dataclass(frozen=True)
class ContentMapping:
    scale_cm: float
    centre_x: float
    centre_y: float
    left: int
    top: int
    background: tuple | None = None

    @staticmethod
    def source_scale(layout, diameter_cm, height_cm):
        return max(diameter_cm / layout.width_px, height_cm / layout.height_px)

    @staticmethod
    def required_border(layout, diameter_cm, height_cm):
        """Minimum symmetric frame that covers all four original rectangular edges."""
        scale = ContentMapping.source_scale(layout, diameter_cm, height_cm)
        left, top, right, bottom = layout.content_box_px
        return max(left * scale, (layout.width_px - right) * scale,
                   (height_cm - layout.height_px * scale) / 2 + top * scale,
                   (height_cm - layout.height_px * scale) / 2 +
                   (layout.height_px - bottom) * scale)

    @classmethod
    def create(cls, layout, diameter_cm, height_cm, border_cm, shape=None):
        scale = cls.source_scale(layout, diameter_cm, height_cm)
        left, top, right, bottom = layout.content_box_px
        if layout.floating_artwork is not None and shape is not None:
            bounds, frame, background = layout.floating_artwork
            a, b, c, d = bounds
            clearance = min(a - frame[0], b - frame[1], frame[2] - c, frame[3] - d) * scale
            xs = np.array([a, a, c, c]) - layout.width_px / 2
            ys = np.array([b, d, b, d]) - layout.height_px / 2
            low, high = 0., scale
            if float(shape.depth(0., 0.)) < border_cm + clearance:
                raise ValueError('当前轮廓无法保留原素材的图案留白距离，请增大尺寸')
            for _ in range(32):
                middle = (low + high) / 2
                if np.min(shape.depth(xs * middle, ys * middle)) >= border_cm + clearance:
                    low = middle
                else:
                    high = middle
            return cls(low, (layout.width_px - 1) / 2, (layout.height_px - 1) / 2,
                       left, top, background)
        half_w, half_h = diameter_cm / 2 - border_cm, height_cm / 2 - border_cm
        tolerance = .75 * scale
        safe_left = (left - layout.width_px / 2) * scale
        safe_right = (right - layout.width_px / 2) * scale
        safe_top = (top - layout.height_px / 2) * scale
        safe_bottom = (bottom - layout.height_px / 2) * scale
        if (-half_w < safe_left - tolerance or half_w > safe_right + tolerance or
                -half_h < safe_top - tolerance or half_h > safe_bottom + tolerance):
            raise ValueError('当前素材的干净花纹区不足以覆盖目标尺寸；请匹配比例更接近的矩形素材。程序不会镜像、复制或拉伸花纹补齐。')
        return cls(scale, (layout.width_px - 1) / 2, (layout.height_px - 1) / 2, left, top)

    def sample(self, layout, x, y):
        u = x / self.scale_cm + self.centre_x - self.left
        v = y / self.scale_cm + self.centre_y - self.top
        result = sample(layout.content, u, v)
        if self.background is not None:
            height, width = layout.content.shape[:2]
            inside = (u >= 0) & (u <= width - 1) & (v >= 0) & (v <= height - 1)
            result = np.where(inside[..., None], result, self.background).astype(np.uint8)
        return result
