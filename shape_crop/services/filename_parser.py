"""Product filenames: preserve the requested stem and normalize dimensions for matching."""
from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class ProductName:
    stem: str
    material: str
    pattern: str
    width_cm: float
    height_cm: float

    @property
    def ratio(self):
        return self.width_cm / self.height_cm


def parse_filename(value):
    # A target is a filename, not a filesystem path. Reject path separators rather than truncate.
    value = value.strip()
    if not value or any(c in value for c in '<>:"/\\|?*'):
        raise ValueError('请输入合法的目标文件名（不包含目录路径或 Windows 禁用字符）')
    stem = re.sub(r'\.(?:jpg|jpeg|png)$', '', value, flags=re.I)
    normalized = unicodedata.normalize('NFKC', stem)
    match = re.search(r'(\d+(?:\.\d+)?)\s*[xX×✕]\s*(\d+(?:\.\d+)?)\s*(?:cm|厘米)?', normalized, re.I)
    if not match:
        raise ValueError('目标名称中未找到尺寸，例如：花幔;80X140cm裁剪有图')
    a, b = map(float, match.group(1, 2))
    if min(a, b) <= 0:
        raise ValueError('文件名中的尺寸必须大于零')
    prefix = normalized[:match.start()].rstrip(' ;；-_')
    parts = [part.strip() for part in prefix.split('-') if part.strip()]
    if not parts:
        raise ValueError('文件名中缺少花型名称')
    pattern = re.sub(r'(裁剪有图|定制尺寸|矩形|横版|竖版|方形)$', '', parts[-1]).strip()
    if not pattern:
        raise ValueError('文件名中缺少花型名称')
    return ProductName(stem, parts[0] if len(parts) > 1 else '', pattern, max(a, b), min(a, b))
