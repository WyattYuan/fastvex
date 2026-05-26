# 更新日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 格式。

## [0.1.0] - Unreleased

### 新增

- `fvx` 短命令，与 `fastvex` 完全等价
- `--version` / `-v` 标志，输出版本号
- dashboard 中根据 profile 名称自动以红/蓝/黄/青色显示
- 紧凑版 dashboard 面板，每槽一行
- 构建签名缓存：相同 profile + route + buildArgs 的槽位只编译一次
- 增量编译优化：切换构建参数时自动 `touch` 依赖编译时常量（`kIsRed`、`kIsBlue` 等）的 `.cpp` 文件
- 部署运行中记录：`deploy` 会保存 `activeExecution`，中断后下次读取状态时自动转为 `interrupted` 历史记录
- 部署步骤级 checkpoint：build/upload 每步完成后即时保存已确认的构建签名、槽位状态和执行记录

### 变更

- [BREAKING] 配置文件升级为 schema v2，结构完全重写：
  - `roles` → `profiles`，`mode` 变为 buildArg `MODE`
  - `routes`（路由集合）→ `alliances`（联队颜色），每条路线携带 `buildArgs`
  - `activeRoute` 移除，每个槽位显式声明 `profile` + `route`
  - `defaults.robotName` → `robot.name`
  - `groups` → `slotGroups`
  - 新增 `programName` 模板，支持 `{robot}`、`{team}`、`{profile}`、`{alliance}`、`{route}`、`{slot}` 占位符
  - 必须显式定义全部 8 个槽位
  - 旧版 `vex_upload_config.yaml` 需通过 `fastvex migrate` 迁移

### 修复

- CLI 无效参数的错误处理
- Rich 控制台输出清理
- Pydantic V2 `to_camel` alias_generator 修正状态序列化问题
- `state.json` 改为原子写入，降低进程中断时状态文件损坏风险

## [0.0.2] - 2026-05-25

### 新增

- PROS 工具链自动检测，缓存路径至 `~/.fastvex/toolchain.json`
- `fastvex toolchain` 和 `fastvex toolchain --rescan` 命令

## [0.0.1] - 2026-05-25

### 新增

- `fastvex init`：初始化项目配置和本机状态目录
- `fastvex validate`：校验配置文件
- `fastvex show`：展示槽位部署计划
- `fastvex status`：展示本机记录的 Brain 槽位快照
- `fastvex deploy`：构建并上传程序到 VEX Brain，支持 `--slots`、`--group`、`--dry-run`、`--clean`、`--port`、`-y`
- `fastvex history show` / `fastvex history clean`：部署历史管理
- `fastvex migrate`：从旧版 `vex_upload_config.yaml` 迁移
- 交互式面板：运行 `fastvex` 进入交互模式，输入槽位号或分组名部署
