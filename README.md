# fastvex

`fastvex` 是面向 VEX V5 / PROS 机器人项目的槽位部署工具。

它会读取机器人项目根目录中的 `fastvex.yaml`，根据 slot、profile、route 配置生成构建参数和程序名，调用 PROS 完成构建/上传，并把本机运行状态写入 `.fastvex/state.json`。

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
fastvex deploy --slots 1,3 -y
fastvex deploy --group all -y
fastvex status
```

也可以在机器人项目子目录中运行，`fastvex` 会向上查找 `fastvex.yaml`。

如果需要显式指定配置：

```powershell
fastvex validate --config D:\path\to\robot\fastvex.yaml
fastvex --config D:\path\to\robot\fastvex.yaml validate
```

## 配置与状态

- `fastvex.yaml`：团队共享部署计划，建议提交到机器人代码仓库。
- `.fastvex/.gitignore`：用于保留 `.fastvex/` 目录并忽略本机文件，建议提交。
- `.fastvex/state.json`：本机状态、上传历史和构建签名，默认不提交。
- `.fastvex/settings.json`：本机工具偏好，默认不提交。
- `vex_upload_config.yaml`：旧配置文件名只用于迁移，新命令不再直接读取部署。

## 常用命令

```powershell
# 初始化 fastvex.yaml 和 .fastvex/ 本机文件，不覆盖已有文件
fastvex init

# 校验配置
fastvex validate

# 展示解析后的槽位部署计划
fastvex show

# 展示本机记录的 Brain 槽位快照
fastvex status

# 预览部署，不执行 PROS 构建/上传
fastvex deploy --slots 3 --dry-run

# 部署指定槽位
fastvex deploy --slots 1,3 -y

# 按配置中的槽位分组部署
fastvex deploy --group all -y

# 从旧 schema 生成 v2 草案
fastvex migrate

# 查看和清理历史
fastvex history show
fastvex history show --limit 5
fastvex history clean --keep 10
```

## Python API

`fastvex` 也提供命令级 Python API，方便测试或脚本复用：

```python
from fastvex.services import DeployRequest, deploy_slots, validate_project

report = validate_project(config="D:/path/to/robot/fastvex.yaml")

deploy_report = deploy_slots(
    DeployRequest(slots="3", dry_run=True),
    config="D:/path/to/robot/fastvex.yaml",
)
assert deploy_report.failed_slots == []
```
