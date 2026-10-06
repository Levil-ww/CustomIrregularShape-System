# AGENTS.md

## 项目目标

圆桌 / 弧形台素材设计器 — PyQt5 桌面应用，根据目标文件名自动匹配素材图库，将矩形素材排版到圆形或弧形台轮廓中，保留原花纹层次和边框，导出成品图（JPG/PNG）。支持草图上传 + 本地 OCR 识别尺寸。

## 技术栈

- Python 3.13, PyQt5, NumPy, Pillow
- 包管理: pip (`requirements.txt` / `requirements-dev.txt`)
- 测试: pytest
- 无 linter / formatter 配置

## 命令

```bash
# 安装
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt   # + pytest

# 启动桌面应用
python main.py

# 命令行
python -m shape_crop.cli --target "花幔;80X140cm" --library "图库" --output-dir "输出"

# 测试
python -m pytest tests -q

# 性能基准
python benchmarks/performance.py
```

## 架构与分层依赖

```
GUI / CLI → workers → services → core → models
```

严格单向依赖，禁止反向导入。`models` 和 `core` 不导入 Qt 或文件操作。

| 层 | 目录 | 职责 |
|---|---|---|
| models | `shape_crop/models/` | frozen dataclass，尺寸校验，业务参数 |
| core | `shape_crop/core/` | 纯计算：几何、渲染、采样，无 I/O |
| services | `shape_crop/services/` | 文件名解析、图库匹配、工作流、OCR、导出 |
| workers | `shape_crop/workers/` | QThread 后台线程，仅依赖 models + services |
| gui | `shape_crop/gui/` | PyQt5 界面，只编辑参数和呈现结果 |

## 代码风格

- 文件名 snake_case，类名 PascalCase，函数/变量 snake_case
- 模块级 docstring 用英文，用户可见字符串和异常消息用中文
- 模型使用 `@dataclass(frozen=True)`，参数在模型层用厘米，像素转换仅在渲染/输出时
- 测试文件 `test_*.py`，测试函数 `test_*`，中文断言描述可接受
- 不引入额外依赖或抽象，除非任务明确要求

## 提交信息

- 使用中文，简洁描述变更原因
- 格式参考: `修复圆弧裁剪英文环识别`、`新增圆桌与弧形台模块选择`
- feat / fix 前缀可接受（英文或中文均可）

## 禁止修改

- `.venv/` — 虚拟环境
- `outputs/` — 用户输出目录
- `verification/` — 视觉验证素材
- `__pycache__/`、`.pytest_cache/` — 自动生成

## 需要批准的操作

- 推送到远程 (`git push`)
- 新增或升级依赖
- 修改架构分层依赖方向
- 删除测试文件或 verification 素材
- 修改 `models/design.py` 中的校验逻辑（影响全局约束）
