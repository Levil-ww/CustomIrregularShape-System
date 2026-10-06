from dataclasses import dataclass


@dataclass(frozen=True)
class ProductRequest:
    target_name: str
    library_dir: str = ''
    material_override: str = ''
    allowance_cm: float = 1.0
    dpi: int = 150
    inner_diameter_cm: float = 0.0
