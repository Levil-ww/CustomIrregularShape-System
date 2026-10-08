"""Exact circle/strip intersection and parallel insets, independent of image/UI."""
from dataclasses import dataclass
import math
import numpy as np


@dataclass(frozen=True)
class CircularBand:
    diameter: float
    height: float

    def __post_init__(self):
        if not (math.isfinite(self.diameter) and math.isfinite(self.height)
                and 0 < self.height <= self.diameter):
            raise ValueError('圆直径和保留高度不合法')

    @property
    def radius(self):
        return self.diameter / 2

    @property
    def half_height(self):
        return self.height / 2

    @property
    def chord(self):
        return 2 * math.sqrt(max(0, self.radius**2 - self.half_height**2))

    @property
    def angle(self):
        return math.asin(min(1., self.height / self.diameter))

    @property
    def perimeter(self):
        return 2 * self.chord + 4 * self.radius * self.angle

    def inset(self, distance):
        if distance < 0 or 2 * distance >= self.height:
            raise ValueError('轮廓内缩距离不合法')
        return CircularBand(self.diameter - 2 * distance, self.height - 2 * distance)

    def depth(self, x, y):
        """Positive inside; minimum distance to the disk or strip complement."""
        return np.minimum(self.radius - np.hypot(x, y), self.half_height - np.abs(y))

    def boundary_coordinate(self, x, y):
        """Arc length of closest boundary, clockwise from the top-left joint.

        Intended for interior points. Used with depth() for perimeter texture mapping.
        At a full circle the start point is the top; the coordinate wraps seamlessly.
        """
        radius, half_h, alpha, chord = self.radius, self.half_height, self.angle, self.chord
        theta = np.arctan2(y, x)
        on_line = half_h - np.abs(y) <= radius - np.hypot(x, y)
        top = np.clip(x + chord / 2, 0, chord)
        bottom = chord + 2 * radius * alpha + np.clip(chord / 2 - x, 0, chord)
        right = chord + radius * (np.clip(theta, -alpha, alpha) + alpha)
        # Left arc: angle pi-alpha .. pi+alpha, traversed through the left-most point.
        left_theta = np.where(theta < 0, theta + 2 * np.pi, theta)
        left = 2 * chord + 2 * radius * alpha + radius * (
            np.clip(left_theta, np.pi - alpha, np.pi + alpha) - (np.pi - alpha))
        arc = np.where(x >= 0, right, left)
        return np.where(on_line, np.where(y <= 0, top, bottom), arc) % self.perimeter


@dataclass(frozen=True)
class ArcBand:
    """Symmetric straight sides joined by independent, minor circular arcs."""
    diameter: float  # bounding width; shared renderer compatibility
    height: float
    chord: float

    def __post_init__(self):
        if not all(math.isfinite(v) for v in (self.diameter, self.height, self.chord)):
            raise ValueError('弧形台尺寸必须为有限数值')
        if not 0 < self.height <= self.diameter or not 0 < self.chord < self.diameter:
            raise ValueError('弧形台须满足 0 < 总高 ≤ 最大宽度、0 < 直边 < 最大宽度')
        if self.diameter - self.chord > self.height:
            raise ValueError('侧弧鼓出过大，不符合对称短圆弧模型')

    @property
    def half_height(self):
        return self.height / 2

    @property
    def radius(self):
        sagitta = (self.diameter - self.chord) / 2
        return (self.half_height**2 + sagitta**2) / (2 * sagitta)

    @property
    def center(self):
        return self.diameter / 2 - self.radius

    @property
    def angle(self):
        return math.asin(min(1., self.half_height / self.radius))

    @property
    def perimeter(self):
        return 2 * self.chord + 4 * self.radius * self.angle

    def inset(self, distance):
        if not math.isfinite(distance) or distance < 0 or 2 * distance >= self.height:
            raise ValueError('轮廓内缩距离不合法')
        radius, half_h = self.radius - distance, self.half_height - distance
        chord = 2 * (self.center + math.sqrt(max(0, radius**2 - half_h**2)))
        return ArcBand(self.diameter - 2 * distance, 2 * half_h, chord)

    def _arc_projection(self, x, y):
        ax = np.abs(x)
        theta = np.clip(np.arctan2(y, ax - self.center), -self.angle, self.angle)
        px = self.center + self.radius * np.cos(theta)
        py = self.radius * np.sin(theta)
        return theta, np.hypot(ax - px, y - py)

    def depth(self, x, y):
        # Project onto the finite arc, not the unused part of its supporting circle.
        _, distance = self._arc_projection(x, y)
        limit = self.center + np.sqrt(np.maximum(0, self.radius**2 - np.minimum(np.abs(y), self.half_height)**2))
        signed = np.where(np.abs(x) <= limit, distance, -distance)
        return np.minimum(self.half_height - np.abs(y), signed)

    def boundary_coordinate(self, x, y):
        theta, arc_distance = self._arc_projection(x, y)
        line_x = np.clip(x, -self.chord / 2, self.chord / 2)
        line_distance = np.hypot(x - line_x, np.abs(y) - self.half_height)
        arc_length = 2 * self.radius * self.angle
        top = line_x + self.chord / 2
        bottom = self.chord + arc_length + self.chord / 2 - line_x
        right = self.chord + self.radius * (theta + self.angle)
        left = 2 * self.chord + arc_length + self.radius * (self.angle - theta)
        on_line = line_distance <= arc_distance + 1e-10
        return np.where(on_line, np.where(y <= 0, top, bottom),
                        np.where(x >= 0, right, left)) % self.perimeter


def create_shape(design):
    if design.shape_mode == 'arc':
        return ArcBand(design.diameter_cm, design.height_cm, design.straight_cm)
    if design.shape_mode != 'circular':
        raise ValueError('未知轮廓模块')
    return CircularBand(design.diameter_cm, design.height_cm)


def inset_boundary_fraction(shape, x, y, depth, reference=None):
    """Continuous perimeter coordinate on each pixel's parallel contour.

    Projecting an entire thick band onto one fixed contour repeats/truncates
    glyphs near the straight/arc joints. Each radial row has its own joint.
    """
    center = shape.center if isinstance(shape, ArcBand) else 0.
    radius = shape.radius - depth
    half_h = shape.half_height - depth
    angle = np.arcsin(np.clip(half_h / radius, 0, 1))
    chord = 2 * (center + np.sqrt(np.maximum(0, radius**2 - half_h**2)))
    arc_length = 2 * radius * angle
    # Straight sections use physical x, shared by every radial row. Normalizing
    # x by each inset chord shears circles and turns upright letters into italics.
    ref_chord = reference.chord if reference is not None else chord
    ref_arc = 2 * reference.radius * reference.angle if reference is not None else arc_length
    perimeter = 2 * ref_chord + 2 * ref_arc
    theta = np.arctan2(y, np.abs(x) - center)
    radial_depth = shape.radius - np.hypot(np.abs(x) - center, y)
    on_line = shape.half_height - np.abs(y) <= radial_depth
    line_x = np.clip(x, -chord / 2, chord / 2)
    top = line_x + ref_chord / 2
    bottom = ref_chord + ref_arc + ref_chord / 2 - line_x
    phase = (np.clip(theta, -angle, angle) + angle) / (2 * angle)
    right = ref_chord + phase * ref_arc
    left = 2 * ref_chord + ref_arc + (1 - phase) * ref_arc
    if reference is not None:
        clipped_theta = np.clip(theta, -angle, angle)
        right = ref_chord + reference.radius * (clipped_theta + reference.angle)
        left = 2 * ref_chord + ref_arc + reference.radius * (reference.angle - clipped_theta)
        # Confine the miter adjustment to the straight/arc joint. Away from it,
        # a fixed angular origin prevents radial rows from drifting in phase.
        transition = max(min(2 * (shape.radius - reference.radius),
                             reference.radius * .02), 1e-6)
        weight = np.clip(1 - (angle - np.abs(clipped_theta)) * reference.radius / transition, 0, 1)
        correction = ((chord - ref_chord) / 2 +
                      reference.radius * (angle - reference.angle)) * weight
        right -= np.sign(clipped_theta) * correction
        left += np.sign(clipped_theta) * correction
    coordinate = np.where(on_line, np.where(y <= 0, top, bottom),
                          np.where(x >= 0, right, left))
    return (coordinate / perimeter) % 1
