# fastvex Agent Handoff

## 1. 是什么 (项目快照)

`fastvex` 是一个独立的 Python CLI/package，用于管理 VEX V5 / PROS 机器人项目的槽位构建和上传流程。机器人项目本身仅消费此工具，本仓库为 `fastvex` 的实现仓库。

- **包名 / 导入名 / 主命令**：`fastvex`
- **短命令**：`fvx`（与 `fastvex` 等价）
- **当前版本**：`0.1.3`
- **环境要求**：Python `>=3.11`
- **包管理器**：`uv`
- **远端仓库**：`https://github.com/WyattYuan/fastvex.git`
- **开发主分支**：`main`
- **推荐安装方式**：`uv tool install fastvex` 或 `uvx fastvex`

---

## 2. 在哪里 (仓库结构)

- `src/fastvex/cli.py`：Typer 命令行界面薄壳，负责参数转接、Rich 输出展现和退出码映射。
- `src/fastvex/services/`：核心业务逻辑服务层，所有外部公共 API 由 `services/__init__.py` 统一暴露。
  - `_project.py`：项目基础操作服务（init, show, validate, history, toolchain）。
  - `_deploy.py`：项目构建与部署编排服务（plan_deploy, deploy_slots）。
  - `_migrate.py`：配置版本迁移服务。
  - `_helpers.py`：内部公用辅助函数（如配置校验、容错性状态加载）。
- `src/fastvex/project.py`：机器人项目根目录及配置文件、本地状态目录路径的查找与解析。
- `src/fastvex/models.py`：`fastvex.yaml` 机器人项目配置对应的 Pydantic 数据模型。
- `src/fastvex/state_model.py`：内部本地运行状态（`.fastvex/state.json`）的 Pydantic 数据模型。
- `src/fastvex/executor.py`：底层命令行执行器，负责具体的 build/upload 命令调用及步骤级 checkpoint 回调。
- `src/fastvex/storage.py`：强鲁棒性 YAML/JSON 读写，采用临时文件写入 + fsync + 原子替换（os.replace）策略。
- `src/fastvex/toolchain.py`：PROS 工具链自动发现与定位逻辑，采用进程级缓存。
- `src/fastvex/display.py`：控制台输出的 Rich 渲染辅助组件。
- `src/fastvex/theme.py`：全局 Rich 控制台样式、高亮颜色主题和确认提示。
- `src/fastvex/templates.py`：项目初始化时使用的默认配置文件及本地 `.gitignore` 模板。
- `src/fastvex/errors.py`：自定义异常类型定义。
- `tests/`：完整的单元与集成测试组件，包含跨平台 fake PROS 虚拟环境。
- `scripts/check.ps1`：一键执行本地静态检查与测试的 PowerShell 脚本。

---

## 3. 怎么改 (核心设计决策/非谈判约束)

- **CLI 薄层原则**：`cli.py` 必须保持绝对薄，禁止包含任何业务逻辑。所有参数校验、逻辑分支以及流程调度必须在 `services/` 下实现。
- **公共 API 隔离**：高层业务必须通过且仅通过 `src/fastvex/services/__init__.py` 中暴露的公共 API 调用，不得直接导入 services 的私有子模块（如 `_deploy` 等）。
- **状态落盘原子化**：写入本地 `state.json` 时，必须使用 `storage.save_state` 提供的机制：先写入临时文件，执行 `flush` 和 `fsync`，最后使用 `os.replace` 原子替换，防止写入中断损坏文件。
- **配置与状态界限**：配置文件 `fastvex.yaml` 归属项目代码（需提交），运行状态目录 `.fastvex/` 属于本地缓存（应被 `.gitignore` 自动忽略并禁止提交）。
- **插槽结构约定**：配置文件中的插槽 `slots` 必须显式定义完整的 `1..8` 个槽位；内部保存的槽位主键必须为整型（JSON 导出的字符串形式在加载时应还原为整型）。
- **副作用滞后提交**：外部命令行副作用完全执行成功后，方可修改本地状态。即：build 成功才能更新 `lastBuildSignature`；upload 成功才能更新 `currentSlots` 的对应槽位状态。
- **中断恢复机制**：启动部署时必须先记录状态为 `running` 的 `activeExecution`；步骤完成时触发 checkpoint 保存；若读取状态时发现遗留的 `running` 记录，自动将其标记为 `interrupted` 并移至 `history`。
- **进程内工具链缓存**：`resolve_toolchain()` 在进程运行生命周期内通过全局变量 `_resolved_cache` 进行内存缓存，禁止产生本地物理缓存文件，避免冗余的注册表或磁盘路径扫描。

---

## 4. 怎么验证 (常用命令与验证步骤)

| 常用操作 / 命令 | 描述 |
| :--- | :--- |
| `uv sync` | 同步并更新开发环境虚拟空间 |
| `uv run ruff check .` | 执行 Ruff 静态代码扫描与排错 |
| `uv run pytest` | 运行全部测试套件 |
| `.\scripts\check.ps1` | 一键运行 Ruff 静态检查及全部 pytest（通过率为最终标准） |

> **Git Hooks**：仓库使用 `core.hooksPath` 指向 `scripts/hooks/`，pre-commit hook 会在每次提交前自动运行 `check.ps1`。克隆后需执行一次：
> ```powershell
> git config core.hooksPath scripts/hooks
> ```
| `uv run pytest tests\test_executor.py tests\test_services.py` | 运行涉及部署执行、断点 checkpoint 及服务层中断恢复的专项测试 |
| `uv run pytest tests\test_toolchain.py` | 运行工具链定位与解析逻辑的专项测试 |
| `uv run --project D:\100Code\VEX\fastvex --directory D:\100Code\VEX\VEX-PushBack-Linyun fastvex validate` | 在真实机器人项目中冒烟测试配置文件的校验表现 |
| `uv run --project D:\100Code\VEX\fastvex --directory D:\100Code\VEX\VEX-PushBack-Linyun fastvex show` | 在真实机器人项目中冒烟测试部署状态与槽位映射的控制台展示 |
| `uv run --project D:\100Code\VEX\fastvex --directory D:\100Code\VEX\VEX-PushBack-Linyun fastvex deploy --slots 3 --dry-run --state $env:TEMP\fastvex-test-state.json` | 真实仓库下的模拟部署冒烟测试。**必须使用独立的临时状态文件路径，防止污染真实项目目录。** |

---

## 5. 编码约定

- **提交规范**：严格遵循 [Conventional Commits](https://www.conventionalcommits.org/) 格式（例如 `feat(deploy): ...`, `fix(toolchain): ...`），保持 git 记录整洁。提交信息应为中文。
- **文档语言**：除非用户另有要求，所有面向使用者的文档（README.md 等）和状态更新默认保持中文。
- **架构解耦**：本仓库作为通用 VEX/PROS 管理工具，严禁侵入式硬编码任何特定机器人（如 PushBack-Linyun）仓库的专属非通用逻辑。
- **CHANGELOG 面向用户**：`CHANGELOG.md` 是给最终用户看的文档，只记录影响用户使用的变更（新命令、行为变化、Bug 修复）。内部开发工具链改动（如 pytest-cov、pyright、CI 配置、重构细节）不应出现在 CHANGELOG 中。