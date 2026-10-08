"""Immutable design parameters. Dimensions are centimetres; crops are normalized."""
from dataclasses import dataclass, field
import math


@dataclass(frozen=True)
class CropBox:
    left: float = 0.0
    top: float = 0.0
    right: float = 1.0
    bottom: float = 1.0

    def validate(self):
        values = (self.left, self.top, self.right, self.bottom)
        if not all(math.isfinite(v) for v in values):
            raise ValueError('素材选区包含无效数值')
        if not (0 <= self.left < self.right <= 1 and 0 <= self.top < self.bottom <= 1):
            raise ValueError('素材选区必须位于图片内，且宽高大于零')


@dataclass(frozen=True)
class MaterialSpec:
    path: str = ''
    content_box: CropBox = field(default_factory=lambda: CropBox(.058, .103, .944, .899))
    strip_box: CropBox = field(default_factory=lambda: CropBox(.06, .064, .94, .098))
    fit: str = 'cover'  # cover preserves aspect ratio; tile preserves physical repeat size
    tile_width_cm: float = 40.0
    border_repeat_cm: float = 0.0  # zero derives length from strip aspect ratio and border width
    layout: str = 'source'  # source preserves complete original layers; manual is the legacy editor

    def validate(self):
        if self.layout not in ('source', 'manual'):
            raise ValueError('素材排版模式必须为 source 或 manual')
        self.content_box.validate()
        self.strip_box.validate()
        if self.fit not in ('cover', 'tile'):
            raise ValueError('素材填充方式必须为 cover 或 tile')
        if not math.isfinite(self.tile_width_cm) or self.tile_width_cm <= 0:
            raise ValueError('花纹平铺宽度必须大于零')
        if not math.isfinite(self.border_repeat_cm) or self.border_repeat_cm < 0:
            raise ValueError('花边重复长度不能为负数（0 表示按选区比例自动计算）')


@dataclass(frozen=True)
class BorderSpec:
    margin_cm: float = 3.5
    width_cm: float = 2.5
    line_cm: float = .10
    color: tuple[int, int, int] = (155, 138, 107)

    @property
    def inset_cm(self):
        return self.margin_cm + self.width_cm


@dataclass(frozen=True)
class DesignSpec:
    diameter_cm: float = 200.0
    height_cm: float = 83.76
    dpi: int = 150
    border: BorderSpec = field(default_factory=BorderSpec)
    material: MaterialSpec = field(default_factory=MaterialSpec)
    inner_diameter_cm: float = 0.0  # zero disables the inner circle
    inner_border_cm: float = 2.5
    inner_material: MaterialSpec | None = None  # None reuses the outer content
    background: tuple[int, int, int] = (248, 235, 205)
    shape_mode: str = 'circular'
    straight_cm: float = 0.0

    def validate(self):
        values = (self.diameter_cm, self.height_cm, self.border.margin_cm,
                  self.border.width_cm, self.border.line_cm, self.inner_diameter_cm,
                  self.inner_border_cm)
        if not all(math.isfinite(v) for v in values):
            raise ValueError('尺寸必须为有限数值')
        if not 0 < self.height_cm <= self.diameter_cm:
            raise ValueError('保留高度须大于零，且不能超过外圆直径')
        if isinstance(self.dpi, bool) or not isinstance(self.dpi, int) or not 1 <= self.dpi <= 1200:
            raise ValueError('DPI 必须为 1–1200 的整数')
        if min(self.border.margin_cm, self.border.width_cm, self.border.line_cm,
               self.inner_diameter_cm, self.inner_border_cm) < 0:
            raise ValueError('边框和内圆尺寸不能为负数')
        if self.border.inset_cm >= self.height_cm / 2:
            raise ValueError('外边框过宽，已占满保留高度')
        if self.border.line_cm > self.border.width_cm:
            raise ValueError('描边宽度不能超过装饰花边宽度')
        if self.inner_diameter_cm:
            if self.inner_diameter_cm / 2 >= self.height_cm / 2 - self.border.inset_cm:
                raise ValueError('内圆必须完整位于外边框内侧')
            if self.inner_border_cm >= self.inner_diameter_cm / 2:
                raise ValueError('内圆边框过宽')
            if self.border.line_cm > self.inner_border_cm:
                raise ValueError('描边宽度不能超过内圆边框宽度')
        self.material.validate()
        if self.inner_material:
            self.inner_material.validate()
        for color in (self.background, self.border.color):
            if len(color) != 3 or any(isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 255 for v in color):
                raise ValueError('颜色须为三个 0–255 的整数')

    def pixel_size(self, max_side: int | None = None):
        self.validate()
        width = max(1, round(self.diameter_cm * self.dpi / 2.54))
        height = max(1, round(self.height_cm * self.dpi / 2.54))
        if max_side is not None:
            scale = min(1.0, max_side / max(width, height))
            width, height = max(1, round(width * scale)), max(1, round(height * scale))
        return width, height
