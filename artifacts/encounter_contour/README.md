# 闲叙系列纹理内框修复

## 原因与效果

用户提供的青釉成品参考要求中央纹理区域随圆桌/弧形台轮廓弯曲。
原处理将闲叙青釉、闲叙邂逅识别为独立矩形画框，整体缩小后保留矩形边缘。
本次将这两款有已验证中央矩形的纹理改为等比满铺内层轮廓，保留浅色外层和原来的内层上下间距，不新增内侧描边。
支持花名中的 `·`、`・`、`.` 及空白写法。其他独立画框仍走原处理。

原分辨率的重复纹理识别可能失败，而预览能识别。因此只在这些指定系列识别失败且图片长边超过 2400px 时，补充有界结构识别，将验证后的轮廓和纹理坐标映射回原像素，保留导出分辨率。
纯色背景的合成色块保留其已识别颜色，不能从原图左上角黑色描边取色。

## 文件范围

- `shape_crop/services/materials.py`：仅指定青釉、邂逅系列使用纹理内框。
- `shape_crop/services/contoured_frame.py`：纹理内框适配及原分辨率识别回退。
- `shape_crop/core/framed_artwork_mapping.py`：允许没有内侧描边的纹理边界。
- `tests/test_encounter_contour.py`：12 项回归测试。
- `artifacts/encounter_contour/verify.py`：两款真实素材、两种轮廓、三个尺寸及原分辨率 JPG/PNG 验证。
- `artifacts/encounter_contour/README.md`：本记录。

未新增依赖，未修改模型校验、分层方向、OCR、图库匹配、GUI 或导出格式逻辑。

## 命令与结果

- `Get-Content`、`rg`：读取实现及既有测试；`git status --short -uno`、`git diff --stat`、`git diff --check`：检查修改范围与空白。
- `Get-ChildItem -LiteralPath <图库目录> -Filter '*闲叙*'`：只读定位原素材。
- `python -B artifacts/encounter_contour/verify.py`：原素材复现并验证预览。
- `python -B -m pytest tests/test_encounter_contour.py -q -p no:cacheprovider --basetemp artifacts/encounter_contour/red`：修复前 8 failed、2 passed。
- 定向测试另检查了既有 `tests/test_gothic_contour.py`，并逐次验证原分辨率识别、纯色背景回退的失败测试；相应问题已修复。
- `python -B -m pytest tests/test_encounter_contour.py -q -p no:cacheprovider --basetemp artifacts/encounter_contour/flat-green`：最终 12 passed，8.31s。
- `python -B -m pytest tests -q -p no:cacheprovider --basetemp artifacts/encounter_contour/full`：首轮 416 passed，137.84s；此后又补充原分辨率与纯色背景回退测试及修复，因此该轮不代表最终版本。
- `python -B artifacts/encounter_contour/verify.py --full`：最终两款真实素材在圆桌/弧形台的实际尺寸 `(141,81,103)`、`(131,81,103)`、`(181,91,140)` 上共 12 组预览断言通过。两款原分辨率素材的 JPG/PNG 导出成功，8327×4783px。已检查导出缩览：内层侧边弯曲。
- 验证过程中发现原分辨率仍为矩形、以及纯色回退误采黑边，已通过失败测试锁定并修复；早期单点颜色检查受到纹理变化干扰，真实素材验证改为沿侧弧采样的内外层统计差异。
- `python -B -m pytest tests -q -p no:cacheprovider --basetemp artifacts/encounter_contour/final-verified`：最终全量 418 passed，134.82s，退出码 0。
- 提交前复验：`python -B -m pytest tests -q -p no:cacheprovider --basetemp artifacts/encounter_contour/precommit`：418 passed，173.05s，退出码 0。

## 人工确认

需重启实际使用的程序，并确认青釉/邂逅在真实订单尺寸、直边和补偿参数下的留白与内层轮廓符合生产要求。
此次示例使用默认 1cm 补偿后的 141×81cm 等尺寸，不能代替用户当前具体订单参数。
未重新打包；图中“订单已更换”的旧预览提示和无效尺寸提示属于界面状态，本次未调整。
所有验证图片与导出仅保存在本地，不自动提交或推送。
