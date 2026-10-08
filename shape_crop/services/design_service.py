"""Application use case: prepare sources, render, optionally export."""
from time import perf_counter
from shape_crop.core.renderer import render, RenderCancelled
from shape_crop.services.materials import prepare
from shape_crop.services.export import save_image


def generate(design, preview=False, output=None, progress=None, cancelled=None, diagnostics=None, status=None,
             timings=None):
    design.validate()
    if cancelled and cancelled():
        raise RenderCancelled('任务已取消')
    if status:
        status('正在读取素材与边框分析结果…')
    started = perf_counter()
    outer = prepare(design.material, preview)
    if diagnostics and outer and outer.source_layout:
        layout = outer.source_layout
        report = f'布局分类：{layout.category}；{layout.report}'
        if layout.floating_artwork is not None or layout.framed_artwork is not None:
            from shape_crop.core.content_mapping import ContentMapping
            from shape_crop.core.geometry import create_shape
            native = ContentMapping.source_scale(layout, design.diameter_cm, design.height_cm)
            border = max(layout.border_depth_px * native,
                ContentMapping.required_border(layout, design.diameter_cm, design.height_cm))
            mapping = ContentMapping.create(layout, design.diameter_cm, design.height_cm,
                                            border, shape=create_shape(design))
            if layout.framed_artwork is not None:
                artwork = layout.framed_artwork
                bounds, frame = artwork.box, artwork.frame
            else:
                bounds, frame, _ = layout.floating_artwork
            gap = min(bounds[0] - frame[0], bounds[1] - frame[1],
                      frame[2] - bounds[2], frame[3] - bounds[3]) * native
            if layout.framed_artwork is not None:
                report += f'；中央画框缩放 {mapping.scale_cm / native * 100:.2f}%， 最小间距 ≥{gap:.2f}cm'
            else:
                report += f'；图案组缩放 {mapping.scale_cm / native * 100:.2f}%， 最小留白 ≥{gap:.2f}cm'
        diagnostics(report)
    inner = prepare(design.inner_material, preview) if design.inner_material else None
    if timings is not None:
        timings['prepare'] = perf_counter() - started
    if cancelled and cancelled():
        raise RenderCancelled('任务已取消')
    renderer = render
    if outer and outer.source_layout:
        from shape_crop.core.source_renderer import render_source
        renderer = render_source
    if status:
        status('正在生成预览…' if preview else '正在渲染全尺寸成品…')
    # Keep progress below completion while the encoder is still writing.
    render_progress = (lambda value: progress(round(value * .90))) if progress and output else progress
    started = perf_counter()
    result = renderer(design, outer, inner, max_side=1200 if preview else None,
                    progress=render_progress, cancelled=cancelled)
    if timings is not None:
        timings['render'] = perf_counter() - started
    if cancelled and cancelled():
        raise RenderCancelled('任务已取消')
    if output:
        if status:
            status('正在编码并保存图片，请稍候…')
        if progress:
            progress(94)
        effective_dpi = result.width / design.diameter_cm * 2.54 if preview else design.dpi
        started = perf_counter()
        save_image(result, output, effective_dpi)
        if timings is not None:
            timings['save'] = perf_counter() - started
        if progress:
            progress(100)
    return result
