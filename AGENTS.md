# fastvex Agent Handoff

## 项目快照

`fastvex` 是一个独立的 Python CLI/package，用于管理 VEX V5 / PROS 机器人项目的槽位构建和上传流程。机器人项目只消费这个包；本仓库才是 `fastvex` 的实现仓库。

当前状态：

- 包名 / import 名 / 主命令：`fastvex`
- 短命令：`fvx`，与 `fastvex` 等价
- 当前版本：`0.1.0`
- Python：`>=3.11`
- 包管理器：`uv`
- 远端：`https://github.com/WyattYuan/fastvex.git`
- 主分支：`main`
- README 推荐安装方式：`uvx fastvex` 或 `uv tool install fastvex`

## 当前工作区上下文

最近一轮工作已经实现部署中断保护，但这些改动可能尚未提交。

相关改动包括：

- `state.json` 改为原子写入，降低进程中断时状态文件损坏风险。
- `State` 新增 `activeExecution`，用于记录正在执行的 deploy。
- `execute_deploy()` 支持步骤级 checkpoint。
- build/upload 每步完成后保存已确认的执行记录。
- 下次读取状态时，如果发现遗留的 `activeExecution.status == "running"`，会自动转为 `interrupted` 历史记录。
- `CHANGELOG.md` 已补充这次 0.1.0 Unreleased 更新。

注意：当前工作区里 `README.md`、`CONTRIBUTING.md` 可能已有其他未提交改动。不要为了整理本次工作而随手还原这些文件。

## 最近 Git 背景

最近检查过的提交：

- `e468046` 更新 README 安装和使用说明，改为使用 `uv` / `uv tool`
- `17ebf12` 添加 toolchain 检测功能，版本到 `0.0.2`
- `893f42e` 添加 PyPI 发布相关文件
- `d60b678` 添加 MIT license 并 bump 到 `0.0.1`

较早的结构性重构包括：

- Pydantic config/state models
- command-level `services.py`
- thin Typer shell in `cli.py`

## 仓库结构

- `src/fastvex/cli.py`
  - Typer 命令壳：解析参数、调用 service、打印输出、映射退出码。
- `src/fastvex/services.py`
  - 命令级 Python API：`validate_project`、`plan_deploy`、`deploy_slots`、`get_history`、`clean_history`、`migrate_project`、`show_toolchain` 等。
  - 加载 state 时会把遗留的 running active execution 恢复为 interrupted history。
- `src/fastvex/project.py`
  - 项目根目录、配置文件、状态文件路径解析。
  - 配置文件所在目录定义机器人项目根目录。
- `src/fastvex/models.py`
  - Pydantic 配置模型。
  - 内部字段使用 snake_case，YAML alias 保持 camelCase。
- `src/fastvex/state_model.py`
  - Pydantic state/history/execution 模型。
  - 包含 `activeExecution`、`history`、`currentSlots`、`lastBuildSignature` 等运行状态。
- `src/fastvex/executor.py`
  - build/upload 执行逻辑和 `CommandRunner`。
  - 记录命令、耗时、返回码、输出和错误。
  - 支持 checkpoint callback，让 service 层持久化步骤进度。
- `src/fastvex/storage.py`
  - YAML/JSON 读写。
  - `save_state()` 使用同目录临时文件、flush/fsync、`os.replace()` 原子替换。
- `src/fastvex/toolchain.py`
  - PROS 发现与缓存逻辑。
  - 全局缓存路径：`~/.fastvex/toolchain.json`。
- `src/fastvex/display.py`
  - Rich 输出辅助。
- `src/fastvex/config_edit.py`
  - 保留文本格式的 YAML 更新辅助。
- `tests/`
  - CLI、executor、services、toolchain 测试，含 fake PROS/make 工具链。
- `scripts/check.ps1`
  - 本地完整检查脚本。

## 需要保持的设计决策

- Python 包独立于机器人仓库。
- 机器人仓库只保存项目配置，例如 `fastvex.yaml`。
- 本机运行状态放在机器人仓库的 `.fastvex/state.json`，机器人仓库不应提交 `.fastvex/`。
- 旧配置名 `vex_upload_config.yaml` 仍可读取，但最终应迁移到 `fastvex.yaml`。
- 配置 `slots` 必须显式定义全部 V5 Brain 槽位 `1..8`。
- 内部 slot key 应保持为整数，即使 JSON 写出时对象 key 会变成字符串。
- CLI 必须保持薄层；可复用行为放在 `services.py`。
- 公共 Python API 应是命令级 service，而不是把低层逻辑散给外部组合。
- YAML/JSON 边界使用 Pydantic v2，不要把所有内部 helper 都强行模型化。
- 本地开发和验证使用 `uv`。
- 正在运行的 deploy 状态放在 `activeExecution`；完成或恢复后的记录放进 `history`。
- 只有命令成功返回后，才能信任对应外部副作用：
  - build 成功后才能更新 `lastBuildSignature`
  - upload 成功后才能更新 `currentSlots`
- `state.json` 写入必须保持原子写，不要改回直接覆盖写。

## 常用命令

开发环境：

```powershell
uv sync
```

本地完整验证：

```powershell
uv run ruff check .
uv run pytest
.\scripts\check.ps1
```

针对部署中断保护的测试：

```powershell
uv run pytest tests\test_executor.py tests\test_services.py
```

工具链相关测试：

```powershell
uv run pytest tests\test_toolchain.py
```

针对 VEX 机器人仓库的 smoke test：

```powershell
uv run --project D:\100Code\VEX\fastvex --directory D:\100Code\VEX\VEX-PushBack-Linyun fastvex validate
uv run --project D:\100Code\VEX\fastvex --directory D:\100Code\VEX\VEX-PushBack-Linyun fastvex show
uv run --project D:\100Code\VEX\fastvex --directory D:\100Code\VEX\VEX-PushBack-Linyun fastvex deploy --slots 3 --dry-run --state $env:TEMP\fastvex-test-state.json
```

工具链检查：

```powershell
uv run fastvex toolchain
uv run fastvex toolchain --rescan
```

## 当前功能说明

工具链检测：

- `fastvex toolchain` 报告缓存或发现到的 PROS 路径。
- `fastvex toolchain --rescan` 清空缓存并重新发现。
- upload service 调用 `resolve_toolchain()`，并向 executor 传入 PATH override。
- 缓存文件：`~/.fastvex/toolchain.json`。

部署中断保护：

- deploy 开始时先保存 `activeExecution`，状态为 `running`。
- build/upload 每个步骤完成后 checkpoint。
- 成功 build 会保存 `lastBuildSignature`。
- 成功 upload 会保存对应 slot 的 `currentSlots`。
- 正常结束后清空 `activeExecution`，并把完整 execution 放入 `history`。
- 异常中断后，下次读取 state 会把遗留 running execution 标记为 `interrupted` 并放入 `history`。
- `state.json` 通过原子替换写入，减少半写文件风险。

发布/文档相关：

- `LICENSE`
- `CONTRIBUTING.md`
- `CHANGELOG.md`
- `.github/workflows/publish.yml`
- README 推荐 `uvx fastvex` 和 `uv tool install fastvex`

## 下一步检查

1. 任何代码改动后跑完整检查：

   ```powershell
   .\scripts\check.ps1
   ```

   最近一次检查结果：

   - `uv run ruff check .` 通过
   - `uv run pytest` 通过
   - `43 passed`

2. 如果改动 state 持久化、executor checkpoint 或 history 恢复逻辑，重点跑：

   ```powershell
   uv run pytest tests\test_executor.py tests\test_services.py
   ```

3. 如果改动命令执行、PATH、PROS 发现或工具链缓存，重点跑：

   ```powershell
   uv run pytest tests\test_toolchain.py
   ```

4. 小心 GitHub workflow 文件。之前 push workflow 文件时遇到过 token 缺少 `workflow` scope 的问题；如果编辑 `.github/workflows/*`，推送前确认认证 token 权限。

5. `D:\100Code\VEX\VEX-PushBack-Linyun` 机器人仓库可能仍有旧版 `vex_upload_config.yaml`。在假设它已迁移前，先检查当前文件状态。

6. 不要把测试 state 写进机器人仓库。smoke test 优先使用：

   ```powershell
   --state $env:TEMP\fastvex-test-state.json
   ```

## 协作习惯

- 提交时优先小提交，使用 Conventional Commit 风格。
- README 默认保持中文，除非用户明确要求英文。
- 不要把机器人特定行为塞进 `fastvex` 包；它应保持通用 VEX/PROS 部署助手。
- 不确定某个行为应该放 CLI 还是 services 时，优先放 services，让 CLI 只负责展示和参数转接。
