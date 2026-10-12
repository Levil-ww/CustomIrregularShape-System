# 蔓生花尺寸变化修复验证

## 问题与修复范围

原案例：弧形台输入宽 111.5cm、高 57cm、直边 70.5cm；补偿后实际宽 112.5cm、高 58cm。
上下直边中央圆点花边被长横线覆盖。已使用截图中的 `双面格-定制-定制尺寸-蔓生花;57x111cm.jpg` 复现。

原因是 `inset_boundary_fraction` 用侧弧的完整支撑圆判断直边/侧弧归属。
当像素位于侧弧圆心背面时，程序误选并不存在的背面圆周，截断角度后连续采到同一列花边。
修复只在弧形台的这一区域选择直边，不按花名、尺寸或颜色添加特殊规则。
未新增依赖，未修改模型校验、分层方向、GUI、匹配、OCR 或导出逻辑。

## 修改及新增文件

- `shape_crop/core/geometry.py`：修正弧形台直边/侧弧归属判断（4 行）。
- `tests/test_arc_border_mapping.py`：新增几何和实际渲染回归测试，含固定种子的 300 组合法尺寸。
- `artifacts/vine_border/verify.py`：原素材验证脚本，仅只读访问图库，在本目录生成验证结果。
- `artifacts/vine_border/README.md`：本记录。

## 执行命令与结果

- `python --version`：Python 3.13.14。
- `Get-Content`、`rg --files`、`rg -n`：读取项目、技能、实现及现有测试。部分旧 artifacts 目录不可读，不影响本次文件。
- `Get-ChildItem -LiteralPath <截图图库目录> -Filter '*蔓生花*'`、`Get-Item -LiteralPath <原素材路径>`：确认原素材；沙箱内读取被拒后，只读提升权限成功。
- `git status --short`、`git diff --stat`、`git diff -- shape_crop/core/geometry.py`、`git diff --check`：检查范围与差异；无空白错误，有 Git CRLF 提示。
- `python artifacts/vine_border/verify.py`：修复前原素材复现成功。
- `python -B -m pytest tests/test_arc_border_mapping.py -q -p no:cacheprovider`：修复前 5 failed、8 passed；补充尺寸扫描后修复版本 14 passed。
- `python -B -m pytest tests/test_arc_border_mapping.py tests/test_arc.py tests/test_border_distortion.py tests/test_dimension_adaptation.py -q -p no:cacheprovider`：测试执行完毕后，pytest 默认临时目录清理遇到 PermissionError，退出码 1；未将该次计作成功。
- 上述定向命令加 `--basetemp artifacts/vine_border/pytest-focused`：54 passed，退出码 0（补充扫描测试前）。
- `python -B artifacts/vine_border/verify.py`：修复后原素材三个尺寸预览成功。
- `python -B artifacts/vine_border/verify.py --full`：实际宽/高/直边 `(112.5,58,70.5)`、`(141,81,90)`、`(200,84,130)` 的上下直边中央花边断言通过；原分辨率素材的 JPG/PNG 导出成功，6644×3425px。
- `python -B -m pytest tests -q -p no:cacheprovider --basetemp artifacts/vine_border/pytest-suite`：405 passed，98.86s（补充扫描测试前）。
- 最终全量命令：`python -B -m pytest tests -q -p no:cacheprovider --basetemp artifacts/vine_border/pytest-final`：406 passed，100.73s，退出码 0。
- 提交前复验：`python -B -m pytest tests -q -p no:cacheprovider --basetemp artifacts/vine_border/pytest-precommit`：406 passed，175.90s，退出码 0。

## 产物及人工确认

本目录在本地生成三张修复预览、`full-export.jpg`、`full-export.png` 和 `full-export-preview.png`，以及源图缩览与条带缩览；图片与测试临时文件不纳入 Git 提交。
预览及导出缩览已检查，上下圆点连续，中央花纹保留。
需要人工确认：在实际运行/打包应用中重启并用原订单切换尺寸，确认界面结果；确认实际印刷尺寸、边框细节与成品效果。
有限回归不能证明整个图库的每张未知素材、任意尺寸组合均正确；现有合法尺寸、干净内容覆盖和像素上限等保护仍有效。
未重新打包；原有 artifacts/build/dist 未清理。提交范围仅为上述四个代码、测试与说明文件。
