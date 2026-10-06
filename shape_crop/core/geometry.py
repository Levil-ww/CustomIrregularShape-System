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
        return math.asin(self.height / self.diameter)

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
