"""Application use case: prepare sources, render, optionally export."""
from shape_crop.core.renderer import render, RenderCancelled
from shape_crop.services.materials import prepare
from shape_crop.services.export import save_image


def generate(design, preview=False, output=None, progress=None, cancelled=None, diagnostics=None):
    design.validate()
    outer = prepare(design.material, preview)
    if diagnostics and outer and outer.source_layout:
        diagnostics(outer.source_layout.report)
    inner = prepare(design.inner_material, preview) if design.inner_material else None
    renderer = render
    if outer and outer.source_layout:
        from shape_crop.core.source_renderer import render_source
        renderer = render_source
    result = renderer(design, outer, inner, max_side=1200 if preview else None,
                    progress=progress, cancelled=cancelled)
    if cancelled and cancelled():
        raise RenderCancelled('任务已取消')
    if output:
        effective_dpi = result.width / design.diameter_cm * 2.54 if preview else design.dpi
        save_image(result, output, effective_dpi)
    return result
