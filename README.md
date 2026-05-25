# fastvex

`fastvex` 是面向 VEX V5 / PROS 机器人项目的槽位构建与上传工具。

它会读取机器人项目根目录中的 `fastvex.yaml`，根据 slot、role、route 配置生成构建参数和程序名，调用 PROS 完成构建/上传，并把本机运行状态写入 `.fastvex/state.json`。

## 安装与运行

临时运行：

```powershell
uvx fastvex validate
uvx fastvex
```

全局安装：

```powershell
uv tool install fastvex
fastvex
fvx
```

安装后也可以使用短命令 `fvx`，它和 `fastvex` 等价。

本仓库本地开发时：

```powershell
uv sync
uv run pytest
uv run ruff check .
```

## 在机器人项目中使用

在包含 `fastvex.yaml` 的机器人仓库根目录运行：

```powershell
fastvex validate
fvx validate
fastvex show
fastvex upload --slots 1,3 -y
fastvex route show
fastvex route set red r1
```

也可以在机器人项目子目录中运行，`fastvex` 会向上查找 `fastvex.yaml`。

如果需要显式指定配置：

```powershell
fastvex validate --config D:\path\to\robot\fastvex.yaml
fastvex --config D:\path\to\robot\fastvex.yaml validate
```

## 配置与状态

- `fastvex.yaml`：机器人项目配置，建议提交到机器人代码仓库。
- `.fastvex/state.json`：本机状态与上传历史，建议加入机器人仓库的 `.gitignore`。
- `vex_upload_config.yaml`：旧配置文件名仍可读取，但新项目建议迁移到 `fastvex.yaml`。

## 常用命令

```powershell
# 初始化 fastvex.yaml 和 .fastvex/state.json，不覆盖已有文件
fastvex init

# 校验配置
fastvex validate

# 展示槽位映射、当前状态和历史
fastvex show

# 展示完整历史
fastvex show --full

# 预览上传，不执行 PROS 构建/上传
fastvex upload --slots 3 --dry-run

# 上传指定槽位
fastvex upload --slots 1,3 -y

# 按配置中的分组上传
fastvex upload --group all-enabled -y

# 查看和切换当前路线
fastvex route show
fastvex route set red r1

# 查看和清理历史
fastvex history show
fastvex history show --limit 5
fastvex history clean --keep 10
```

## Python API

`fastvex` 也提供命令级 Python API，方便测试或脚本复用：

```python
from fastvex.services import UploadRequest, upload_slots, validate_project

report = validate_project(config="D:/path/to/robot/fastvex.yaml")
assert report.warnings == []

upload_report = upload_slots(
    UploadRequest(slots="3", dry_run=True),
    config="D:/path/to/robot/fastvex.yaml",
)
assert upload_report.failed_slots == []
```
