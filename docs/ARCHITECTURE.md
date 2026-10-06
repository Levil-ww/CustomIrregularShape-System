# 架构与维护约定

## 数据流

```text
GUI / CLI
  → ProductRequest（目标名称、图库、补偿、DPI）
  → services.workflow.resolve_request
      → services.filename_parser / services.catalog
  → DesignSpec（不可变快照、厘米参数）
  → WorkflowWorker / RenderWorker（仅桌面使用）
  → services.design_service.generate
      → services.materials.prepare
      → core.source_renderer.render_source（自动） / core.renderer.render（手工）
          → core.geometry.CircularBand
          → core.sampling
      → services.export.save_image
```

`models` 不依赖 Qt 或文件操作。`core` 不依赖 GUI、Worker 或文件路径读取。`services` 组织核心能力及文件操作。`workers` 仅依赖模型与服务，不导入 GUI。界面仅编辑参数、提供文件选择并呈现结果，不实现裁剪数学。

## 模块职责

| 模块 | 职责 | 后续修改位置 |
|---|---|---|
| models/design.py | 尺寸、选区、边框、素材、内圆参数及校验 | 新参数和业务约束 |
| models/request.py | 文件名工作流不可变请求 | 目标输入参数 |
| services/filename_parser.py | 尺寸、花型、材质、原输出名 | 命名规则 |
| services/catalog.py | 同花型矩形 JPG 扫描、比例/尺寸排名 | 匹配与图库缓存 |
| services/workflow.py | 目标解析、补偿、模型创建、输出名称 | 自动生成编排 |
| services/layout_analysis.py | 原边框到花纹边界检测、完整条带提取 | 自动排版识别 |
| services/texture_period.py | 装饰行的周期相关性识别、整周期截取 | 花边重复相位 |
| core/source_renderer.py | 原色、原层次、统一缩放、周长映射 | 默认素材渲染 |
| core/content_mapping.py | 原图中心坐标、单次等比映射、内容覆盖校验 | 花纹保持与居中裁剪 |
| core/geometry.py | 精确轮廓、等距内缩、周长与弧长坐标 | 几何扩展 |
| core/sampling.py | 双线性采样、等比填充、平铺、花边重复 | 纹理映射与采样质量 |
| core/renderer.py | 分块合成、透明遮罩、线条与内圆叠加 | 图层关系、渲染效果 |
| services/materials.py | EXIF 方向、图片读取、标准化选区裁切 | 素材格式和自动区域识别 |
| services/project_io.py | 版本化 JSON 读写、相对路径 | 项目格式升级 |
| services/export.py | PNG/JPG 编码、DPI、原子替换 | 出血、色彩管理、新输出格式 |
| services/design_service.py | 素材准备、预览/导出应用用例 | 功能编排 |
| workers/render_worker.py | QThread、进度、错误和取消信号 | 后台任务调度 |
| gui/main_window.py | 目标名称、图库、输出目录、自动生成 | 默认 UI 工作流 |
| gui/manual_window.py | 首版参数工具、选区、JSON 项目 | 手工兼容功能 |
| gui/crop_dialog.py | 鼠标选区、归一化坐标 | 选区工具 |

## 关键约束

- 所有尺寸在模型中使用厘米。像素转换只在渲染和输出尺寸计算时进行。
- `height_cm <= diameter_cm`；内圆包含自身花边，必须完全位于外部内容轮廓中。
- 自动模式以直径/原图宽度确定花纹的唯一缩放，保持原图中心，目标高度只决定上下等距裁剪。禁止花纹镜像、重复或单独缩放；覆盖不足时报错，不允许原竖边参与填充。
- 边框周向坐标使用 `-abs(y)` 保持上下对称，花纹采样保留有符号的 y。边宽取原四边安全内容区所需的最大内缩距离，兼顾尺寸补偿；各层按同一径向比例映射，不改变花纹坐标。
- SourceLayout 的 strip 排除矩形转角后提取整周期。周长使用整数次周期闭合，避免尺寸变化时在轮廓起点产生相位断裂；无法可靠提取周期时报告不确定性并用完整安全条带。
- 目标补偿仅在 workflow 加一次：long+1cm、short+1cm。输出保留目标名称，不改大小写、不追加实际尺寸。
- 参数是 frozen dataclass，后台任务拿快照；运行期间禁用参数编辑，关闭窗口先请求取消，等线程结束后关闭。
- 取消在分块之间响应；图片加载和文件编码阶段需要等待当前操作结束。未完成编码不会替换已有目标文件。
- JSON `schema_version=1`。未来新增字段应有默认值；格式迁移单独实现，避免静默丢弃旧字段。
- 自动识别返回 SourceLayout：源像素、完整边框带、边界深度及报告。没有可靠边界时报告降级，不虚构固定线条。

## 建议扩展顺序

1. 真实图库素材的条带周期提取和闭合接缝处理。
2. 草图 OCR 将识别结果转成 DesignSpec，保持手工尺寸校验。
3. 多个独立内圆、偏心内圆及真实镂空输出。
4. 印刷余量、色彩管理、PSD 导出和打包。

对几何、映射、项目格式和后台任务的改动，应分别增加边界或端到端验证，而不是在界面复制计算公式。
