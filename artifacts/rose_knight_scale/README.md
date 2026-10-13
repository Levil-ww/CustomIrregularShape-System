# 玫瑰骑士裁剪修复与验证

## 原因与最终处理

玫瑰骑士大图及小图均有压入 JPG 的矩形淡化层和细描边。此前为贴合弧形内框而改变花纹横纵坐标，造成花朵变形；改为等比采样后，仅按细框范围反淡化又留下框外的旧浅色竖带和横向断纹。

最终处理区分细框与实际淡化范围：在源图的固定分析分辨率上，从闭合细框向外扫描连续淡化色阶区域，清晰深色花纹阻止扩张，空白背景不能单独证明存在淡化层。天然浅色细节保护和输出采样密度一致性均有回归测试。移除了按渲染行数量和重复匹配来扩张修补区域的方案，本轮重新使用可选长周期参数，仅为恢复旧竖直描边遮住的窄带花纹；已有调用的默认周期范围保持不变，不再凭重复颜色扩张淡化区域。

花纹始终采用统一等比源图坐标。曲线仅决定新淡化遮罩与细描边；旧细框以窄范围局部插值清理。新旧遮罩重合区域保留原采样色彩，反淡化结果限制在原背景色上限，避免 JPEG 亮噪声变成白色接缝。

原分辨率还会因 JPEG 缩略图低估细框粗细，使插值端点仍落在旧黑线内。现在在原图中央带测量实际黑线行数，再确定清理宽度，新增粗线回归。

另修复小素材原分辨率右边框扫描过深：对于普通边框的已识别半透明内框，同步预览结构坐标，仍从原图采样花纹与条带。带文字、角落空隙或分层条带的素材保留原结构准备。

## 修改文件

- shape_crop/core/panel_mapping.py
- shape_crop/core/source_renderer.py
- shape_crop/services/inset_panel.py
- shape_crop/services/materials.py
- tests/test_translucent_pattern_scale.py
- artifacts/rose_knight_scale/verify.py
- artifacts/rose_knight_scale/README.md

工作区原有 shape_crop/gui/main_window.py 和 tests/test_gui.py 修改未编辑、撤销或纳入本次变更。没有新增依赖，没有修改模型全局约束、架构依赖方向、图库匹配、OCR 或导出格式。

## 运行命令

- git status --short -uno；git diff --stat -- <本次文件>；Get-Content、rg：检查工作区与相关实现。
- Get-ChildItem -LiteralPath <原共享图库目录> -Filter '*玫瑰骑士*'：只读定位真实素材。
- python -B -m pytest tests/test_translucent_pattern_scale.py -q -p no:cacheprovider --basetemp artifacts/rose_knight_scale/red2：早期四项几何回归失败，确认旧映射变形。
- python -B -m pytest tests/test_translucent_pattern_scale.py -q -k 'matching_repeated or naturally_pale or ambiguous or unfaded_detail' -p no:cacheprovider --basetemp artifacts/rose_knight_scale/source-bounds2：5 passed；确认源图边界修复及浅色细节保护。
- python -B -m pytest tests/test_translucent_pattern_scale.py tests/test_inset_panel.py -q -p no:cacheprovider --basetemp artifacts/rose_knight_scale/source-bound-focused：46 passed，43.20s；此后补充原图实际线宽回归，final-stroke-regression2定向2项通过（0.83s）。
- python -B -m pytest tests -q -p no:cacheprovider --basetemp artifacts/rose_knight_scale/final-all：最终460 passed，196.54s。
- python -B artifacts/rose_knight_scale/verify.py：两款真实素材、两种轮廓、三种目标尺寸的预览断言通过，共12组。
- python -B artifacts/rose_knight_scale/verify.py --full --layout-only：原分辨率与预览结构一致性检查，早期小图失败，修复后通过。
- python -B artifacts/rose_knight_scale/verify.py --full：两款素材、预览与原分辨率、圆桌与弧形台、三种目标尺寸，共24组；另导出两款10689×5079像素 JPG/PNG，验证文件尺寸。最终24组通过，且两款10689×5079像素JPG/PNG导出均通过；最后只读结构复核确认原图线宽为24px/17px。
- git diff --check -- shape_crop/core/panel_mapping.py shape_crop/core/source_renderer.py shape_crop/services/inset_panel.py shape_crop/services/materials.py：检查通过。

目标尺寸为 (181,86,105.2)、(141,81,103)、(105,66.5,82)，分别表示最大宽度、总高、直边厘米数。等比断言比较遮罩及描边影响范围之外的花纹与原图统一采样坐标。

## 人工确认与限制

重启实际程序后，使用截图订单核对放大预览与实际印刷补偿参数，重点查看弧形内框两侧和上下旧矩形细框位置的花纹接缝。JPEG 中被原细框覆盖的细节无法精确恢复，局部插值与淡化色阶估计需要视觉确认。

该处理由素材结构决定，不依赖花名或厘米尺寸。已测试范围不等于证明所有未知花型与任意尺寸均正确；现有合法几何、内容覆盖与输出像素上限仍生效。

验证图片保存在本地 artifacts/rose_knight_scale；未修改用户 outputs/ 或 verification/，未重新打包。

## 本轮细节校正（2026-10-13）

用户确认素材为双面格-定制-定制尺寸-玫瑰骑士;85x135cm.jpg，实际W=130cm、H=85cm、L=99cm。65.5×104期望图用于核对淡化边缘和花纹连续性，不要求两种不同订单的花纹坐标完全相同。

此前遗漏了细框外的淡化留边，本轮将淡化层与细描边分别映射到弧形轮廓，保留上下及两侧的淡化间距；源图边界在原像素上进一步定位。跨源遮罩边缘采样先恢复各源像素再插值，避免未淡化黑色与淡化黑色混合产生灰线。旧竖直细描边的窄带通过经过全行误差检验的花纹周期修补，还必须核对窄带两側邻域；没有证据时保留原局部插值。

新增修改：shape_crop/services/texture_period.py；artifacts/rose_knight_scale/detail_verify.py。其余修改仍在前述四个生产文件与tests/test_translucent_pattern_scale.py内，source_renderer.py本轮未进一步改动。

运行：python -B -m pytest tests -q -p no:cacheprovider --basetemp artifacts/rose_knight_scale/detail-complete（463 passed，169.67s）；python -B artifacts/rose_knight_scale/detail_verify.py（指定素材，三组尺寸，预览/原分辨率共6组，原尺寸JPG/PNG导出7677×5020均通过）；git diff --check -- <本次生产文件>（通过）。

定向回归detail-final-focused：49 passed，40.37s；随后补充源遮罩边缘插值回归。filter-edge：5 passed，0.60s。verified-stem：1 passed，0.25s，并确认关闭重复修补时插值会把应存在的细花纹抹成背景。最终全量检查覆盖所有生产修改。新增加的遮罩边缘插值检查：先分别恢复未淡化/淡化源像素，再进行双线性插值，防止旧遮罩边缘混出灰线。

真实输出：detail-130-85-preview.png、detail-130-85-native.png、detail-130-85-full-preview.png及detail-130-85-full.jpg/png。人工核对当前源码程序中箭头处的花纹连接、淡化留边及实际印刷补偿；没有重新打包现有可执行程序。

本轮最终验证导出已打开检查；预览与原分辨率缩略图均为1200×785，完整JPG/PNG为7677×5020。所有新结果都来自用户指定85×135素材，未更换素材，未调整目标W/H/L。

最后全量detail-verified-all曾发现1项角点失败（462通过）：源淡化边界恰与细框重合时，四点边缘恢复采样覆盖了已经插值修补的角点。已限定边缘恢复不覆盖修补过的描边区域。detail-corner-green：角点、细枝和灰缝3项通过（0.33s）。修复后重新运行完整detail-complete及真实detail_verify.py。

最终结果：detail-complete全量463 passed（169.67s）；最终detail_verify.py共6组预览/原分辨率尺寸验证通过，7677×5020 JPG/PNG导出通过。git diff --check通过。

## 本轮轻微白框（2026-10-13）

用户继续反馈旧矩形周围轻微白线。实际源图四边窄带约2.5%的像素超过背景亮度，99分位过亮约9级、峰值21至29级。上一版只处理淡化范围内的对比反算，范围外JPEG亮度振铃仍保留。

本轮仅在旧细框及旧淡化边界附近处理保持底色通道差异的过亮中性色偏移，不改变花纹坐标、淡化留边或其它图层。原白色花纹与远离原边界的亮色细节有保护回归。生产代码仅进一步修改shape_crop/core/panel_mapping.py；测试修改tests/test_translucent_pattern_scale.py；增加white_line_verify.py并加强detail_verify.py的真实白线断言。本轮未改变其它服务/GUI、依赖或模型校验。

运行命令与结果：
- python -B -m pytest tests/test_translucent_pattern_scale.py -q -k 'bright_ringing or white_artwork' -p no:cacheprovider --basetemp artifacts/rose_knight_scale/ringing-red：修复前四个白线回归失败、两个保护项通过。
- 同一测试选择，--basetemp artifacts/rose_knight_scale/ringing-green2：6 passed，0.45s。
- python -B artifacts/rose_knight_scale/white_line_verify.py：真实130×85、L99预览在原矩形窄带内的过亮白线像素，修复前190，修复后0。
- python -B artifacts/rose_knight_scale/detail_verify.py：预览/原分辨率、三组尺寸共六组花纹区白线检查通过；130×85、L99的7677×5020 JPG/PNG导出通过。外装饰边框重新绘制的像素不属于旧内框白线断言范围。
- python -B -m pytest tests -q -p no:cacheprovider --basetemp artifacts/rose_knight_scale/ringing-final-all：469 passed，196.51s。
- git diff --check -- shape_crop/core/panel_mapping.py shape_crop/core/source_renderer.py shape_crop/services/inset_panel.py shape_crop/services/materials.py shape_crop/services/texture_period.py：通过。

另用原图未淡化的纵向重复叶片（1049px位移）对照，612个实心墨色参考像素中没有出现异常灰色缺口；原叶脉属于原花纹，不予抹除。源图边缘统计、重复花纹对照及局部放大图通过只读Python/Pillow诊断命令生成。

人工确认：重启当前源码程序后重新生成，查看本轮detail-130-85-full-preview.png及white-line-130-85-preview.png，重点核对箭头位置。现有可执行程序没有重新打包，旧进程不会自动加载本次Python源码修改。

## 实际成品四边过渡修复（2026-10-13）

用户提供的实际导出为7736×5079像素、150 DPI，对应含补偿131×86cm、直边99cm。此前130×85cm验证遗漏了补偿尺寸，也只检查过亮振铃，不能证明部分透明灰边已被清除。

本轮在原图像素上读取完整淡化区域边界，并分别识别上下左右连续的部分透明过渡行/列。按每条过渡带的墨色色阶恢复源像素，再执行双线性插值。JPEG边缘接近底色、反算缺少对比时，仅在边缘两侧均为连续墨色或均为背景的证据下修补，参考点避开八像素压缩过渡块。天然浅色/白色花纹保护回归保持通过。修改涉及core/panel_mapping.py、services/inset_panel.py、services/materials.py、tests/test_translucent_pattern_scale.py；没有添加依赖。

本轮执行：
- python -B -m pytest tests -q -p no:cacheprovider --basetemp artifacts/rose_knight_scale/block-reference-final：473 passed，164.72s，覆盖当前全部生产代码；随后仅补充下边缘测试。
- python -B -m pytest tests/test_translucent_pattern_scale.py -q -k 'partial_original or nearly_opaque' -p no:cacheprovider --basetemp artifacts/rose_knight_scale/four-edge-final：5 passed，49 deselected，0.46s。
- python -B artifacts/rose_knight_scale/actual_export_verify.py：读取用户原素材和旧成品，重新生成含补偿的完整PNG/JPG（7736×5079）。
- python -B artifacts/rose_knight_scale/actual_export_verify.py --reuse：最新结果通过。左315、上924、右256、下1238，共2733个跨边缘两侧均为实心墨色的参考点；旧成品1359个异常灰白像素，新PNG/JPG均为0。先前46个额外候选为新外边框的正常米色区域，测量轮廓深度4.68cm小于边框4.88cm后排除；断言仅覆盖花纹区域，并单独排除新弧形淡化范围和抗锯齿边缘。
- git diff --check -- shape_crop/core/panel_mapping.py shape_crop/core/source_renderer.py shape_crop/services/inset_panel.py shape_crop/services/materials.py shape_crop/services/texture_period.py：通过。

本地结果：actual-131-86-full.png、actual-131-86-full.jpg、actual-131-86-full-preview.png、actual-edge-{top,left,right,bottom}.png。已查看整体与四边放大图。所有验证写入artifacts，用户E盘成品及共享素材均只读。GUI既有改动未编辑，未重新打包。

人工确认：重启当前源码应用，以同一85×135素材、W130/H85/L99和原补偿设置重新生成，放大核对四边花纹和实际印刷效果。自动断言覆盖稳定连续墨色，不能代替全部花纹细节的人工视觉验收。

提交前复核：python -B -m pytest tests -q -p no:cacheprovider --basetemp artifacts/rose_knight_scale/commit-final：474 passed，175.95s。actual_export_verify.py --reuse再次通过，四边2733个采样点的新PNG/JPG异常灰白像素均为0。提交仅包含本次五个生产文件、一个回归测试文件和五个验证脚本/说明文件，生成图片与既有GUI修改不包含在内。
