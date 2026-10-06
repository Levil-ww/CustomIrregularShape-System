"""One centred, uniform cover transform. Never synthesize or reflect content."""
from dataclasses import dataclass
from shape_crop.core.sampling import sample


@dataclass(frozen=True)
class ContentMapping:
    scale_cm: float
    centre_x: float
    centre_y: float
    left: int
    top: int

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
    def create(cls, layout, diameter_cm, height_cm, border_cm):
        scale = cls.source_scale(layout, diameter_cm, height_cm)
        left, top, right, bottom = layout.content_box_px
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
        return sample(layout.content, x / self.scale_cm + self.centre_x - self.left,
                      y / self.scale_cm + self.centre_y - self.top)
