"""Symmetric belly outline with circular corners and smooth interpolated sides."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class BellyOutline:
    width: float
    height: float
    side_span: float
    horizontal_span: float
    corner_diameter: float

    def __post_init__(self):
        values = (self.width, self.height, self.side_span, self.horizontal_span, self.corner_diameter)
        if not all(math.isfinite(v) and v > 0 for v in values):
            raise ValueError('马肚形各尺寸必须为大于零的有限数值')
        if self.horizontal_span + self.corner_diameter > self.width:
            raise ValueError('D 加圆角直径不能超过 B')
        if self.side_span + self.corner_diameter > self.height:
            raise ValueError('C 加圆角直径不能超过 A')

    def reference_approximation(self):
        """Bias spans toward the approved reference; A, B and diameter stay fixed.

        The shift is bounded for small or nearly square shapes.  The returned
        spans are the actual values and must be shown before export.
        """
        shift = self.corner_diameter * .2
        side_span = max(self.side_span - shift, self.side_span * .5)
        horizontal_span = min(self.horizontal_span + shift, self.width - self.corner_diameter)
        return BellyOutline(self.width, self.height, side_span, horizontal_span, self.corner_diameter)

    def points(self, steps=48):
        """Return a clockwise closed outline in centimetres, centred at zero.

        C and D join the side curves to quarter-circle corners. Smoothstep
        interpolation keeps the corner joins and symmetry axes tangent.
        """
        if steps < 2:
            raise ValueError('轮廓采样数量过小')
        r = self.corner_diameter / 2
        hx, hy = self.horizontal_span / 2, self.side_span / 2
        dx = self.width / 2 - hx - r
        dy = self.height / 2 - hy - r
        def smooth(t):
            return t * t * (3 - 2 * t)
        quadrant = []
        for i in range(steps + 1):
            t = i / steps
            quadrant.append((hx * t, -self.height / 2 + dy * smooth(t)))
        for i in range(1, steps + 1):
            theta = -math.pi / 2 + math.pi / 2 * i / steps
            quadrant.append((hx + r * math.cos(theta), -hy + r * math.sin(theta)))
        for i in range(1, steps + 1):
            t = i / steps
            quadrant.append((hx + r + dx * smooth(t), -hy * (1 - t)))
        top_right = quadrant
        bottom_right = [(x, -y) for x, y in reversed(top_right[:-1])]
        right = top_right + bottom_right
        left = [(-x, y) for x, y in reversed(right[1:-1])]
        return right + left + [right[0]]
