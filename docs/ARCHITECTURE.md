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
          → core.geometry.create_shape → CircularBand / ArcBand
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
- 自动模式以 `max(目标宽/原图宽, 目标高/原图高)` 确定整幅素材的唯一缩放，保持原图中心，超出的宽高等距裁剪。禁止花纹镜像、重复或单独缩放；覆盖不足时报错，不允许原竖边参与填充。
- 边框沿有符号的 y 顺时针连续映射，下半圈文字旋转180度，避免镜像。直边各径向行共用物理 x 坐标；圆弧以装饰所在轮廓为角度参考，仅在接头附近修正相位，避免圆点倾斜、文字变成斜体。边宽取原四边安全内容区所需的最大内缩距离；需要额外加宽时只扩展原条带中连续、近似纯色的留白，装饰和细线保持原径向缩放。没有可扩展留白则明确报错，不拉伸装饰补齐。中央花纹坐标不变。
- 边界识别在最长边2400px的尺度进行，大图再在预计边界附近寻找原分辨率颜色分隔线。原分辨率像素用于内容、细线和边框提取；英文条带通过被纯色行包围的稀疏笔画识别，不要求具有周期。
- SourceLayout 的 strip 排除矩形转角后提取整周期。周长使用整数次周期闭合，避免尺寸变化时在轮廓起点产生相位断裂；无法可靠提取周期时报告不确定性并用完整安全条带。
- 目标补偿仅在 workflow 加一次：long+1cm、short+1cm。输出保留目标名称，不改大小写、不追加实际尺寸。
- 弧形台直边为独立参数，不参与尺寸补偿。原始及补偿后的参数均校验；最大宽度、总高可从草图校正，图库匹配使用校正后的原始尺寸。
- ArcBand 采用对称短圆弧：鼓出 s=(W-L)/2，半径 R=((H/2)²+s²)/(2s)，右圆心 c=W/2-R、左圆心-c。要求 0<L<W、W-L≤H；等距内缩保持圆心，减小半径和半高，再重算直边交点。边界距离投影到有限圆弧，不能使用支撑圆未参与轮廓的部分。
- services/sketch_recognition.py 与 windows_ocr.ps1 封装本地系统 OCR 及尺寸位置关联；workers/sketch_worker.py 后台运行，不依赖 GUI。OCR 结果始终需要核对，缺失数据留给手工输入；更换订单清除草图来源。gui/shape_preview.py 展示厘米参数重建的轮廓。
- 参数是 frozen dataclass，后台任务拿快照；运行期间禁用参数编辑，关闭窗口先请求取消，等线程结束后关闭。
- catalog 按花型索引解析结果，最多缓存 4 个图库。CLI 默认核对已知目录条目，增量解析新增文件；桌面 CatalogSession 从首次匹配到窗口关闭保持单个 ReadDirectoryChangesW 递归监听（64KiB 缓冲，兼容 SMB），按文件事件更新索引。正常换单禁止全库遍历；通知溢出、监听失败、手动刷新时才核对目录，新增子目录只扫描新目录。异常和取消不会提交部分索引；匹配结果再验证文件存在。
- materials 以素材参数、文件标识、大小和纳秒时间戳为键，缓存最多 8 项 / 256MiB，按底层数组所有者去重计算大小。缓存像素数组只读，内容区为原像素视图。大图预览最长边 2400px，JPEG draft 按原比例的目标尺寸缩小解码；导出独立读取、分析原分辨率，不能使用缩图缓存。小自动素材共享缓存，手工模式分别缓存缩略和完整选区。
- sampling 使用 float32 插值，减少 NumPy float64 隐式提升；导出保留尺寸、DPI、透明度和 JPG 编码质量。PNG compress_level=1 为无损快速压缩。generate 的进度为渲染 0–90、编码保存 94、成功写入 100，status 区分阶段。
- 取消在分块之间响应；图片加载和文件编码阶段需要等待当前操作结束。未完成编码不会替换已有目标文件。
- JSON `schema_version=1`。未来新增字段应有默认值；格式迁移单独实现，避免静默丢弃旧字段。
- 自动识别返回 SourceLayout：源像素、完整边框带、边界深度及报告。没有可靠边界时报告降级，不虚构固定线条。

## 建议扩展顺序

1. 真实图库素材的条带周期提取和闭合接缝处理。
2. 草图 OCR 将识别结果转成 DesignSpec，保持手工尺寸校验。
3. 多个独立内圆、偏心内圆及真实镂空输出。
4. 印刷余量、色彩管理、PSD 导出和打包。

对几何、映射、项目格式和后台任务的改动，应分别增加边界或端到端验证，而不是在界面复制计算公式。
