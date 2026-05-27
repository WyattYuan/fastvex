# fastvex

在 VEX V5 机器人竞赛中，Brain 拥有 **8 个程序槽位**，但在实际研发与赛场调试中，开发者常常面临极大的部署痛点：
* **多维度的编译组合**：需要在红方联队、蓝方联队、技能赛等不同颜色间切换；每种颜色还需要细分左侧、右侧、调试或比赛模式。
* **低效且易错的手动部署**：每次切换逻辑，都需要修改代码、手动执行编译、并指定槽位进行 `pros upload --slot X`，极易在赛前紧张环境下出错。
* **增量编译的不安全**：在切换如 `kIsRed` 等编译期宏常量时，GCC 编译器（包含 `make`）通常无法自动感知这类无代码字符变动的宏修改，导致局部未重新编译，最终部署了带有旧逻辑的“半红半蓝”程序。

`fastvex`（短命令 `fvx`）正是为此而生的 **VEX V5 / PROS 槽位部署自动化管理器**。它通过一份直观易懂的声明式配置文件 `fastvex.yaml`，统一管理 8 个槽位的编译与部署，实现一键编译、槽位分发、智能增量安全 touch 以及断点保护部署。

## Features

fastvex 用一个 `fastvex.yaml` 配置文件管理 VEX V5 机器人的全部构建和部署流程。

### 从代码到上手

**写 C++ 代码时** — 在代码中使用编译时常量 `kIsRed`、`kIsBlue`、`kIsSkill`、`kRoute` 等区分颜色和路线，同一份代码编译出不同行为的程序。

**编辑 `fastvex.yaml` 时** — 用三层结构描述你的部署计划：

- **Alliance（联队颜色）** — 定义红方、蓝方、技能赛等路线集合，每条路线携带编译参数
- **Profile（配置）** — 定义可构建的程序类型（如 `redComp`、`blueDebug`），关联联盟并设置 `MODE` 等参数
- **Slot（槽位）** — 把 profile + route 绑定到 Brain 的 1-8 号槽位

```yaml
schemaVersion: 2
robot:
  name: Sparkle
  team: HITSZ1
programName:
  template: "{profile}-{route}-{robot}"
alliances:
  red:
    routes:
      left:  { buildArgs: { ROUTE: 1 } }
      right: { buildArgs: { ROUTE: 2 } }
  blue:
    routes:
      left:  { buildArgs: { ROUTE: 1 } }
      right: { buildArgs: { ROUTE: 2 } }
  skill:
    routes:
      main:  { buildArgs: { ROUTE: 0 } }
profiles:
  redComp:    { alliance: red,   buildArgs: { MODE: RED_COMP } }
  blueComp:   { alliance: blue,  buildArgs: { MODE: BLUE_COMP } }
  skillComp:  { alliance: skill, buildArgs: { MODE: SKILL_COMP } }
  redDebug:   { alliance: red,   buildArgs: { MODE: RED_DEBUG } }
  blueDebug:  { alliance: blue,  buildArgs: { MODE: BLUE_DEBUG } }
slots:
  1: { profile: redComp,   route: left }
  2: { profile: blueComp,  route: right }
  3: { profile: skillComp, route: main }
  4: { profile: redDebug,  route: left }
  5: { profile: blueDebug, route: right }
  6: empty
  7: empty
  8: empty
slotGroups:
  all: [1, 2, 3, 4, 5, 6, 7, 8]
```

**使用 CLI 时** — 直接运行 `fastvex` 进入交互式面板，输入槽位号或分组名即可部署：

```
  fastvex  Sparkle

  1  redComp     left     redComp-left-Sparkle
  2  blueComp    right    blueComp-right-Sparkle
  3  skillComp   main     skillComp-main-Sparkle
  4  redDebug    left     redDebug-left-Sparkle
  5  blueDebug   right    blueDebug-right-Sparkle
  6  empty
  7  empty
  8  empty

  Slots or group> 1,3
```

fastvex 会自动调用 PROS 构建、上传到主控，相同构建参数的槽位只编译一次。切换联队颜色时自动 `touch` 依赖编译时常量的 `.cpp` 文件，确保增量编译正确。

### CLI 命令

| 命令 | 说明 |
|------|------|
| `fastvex` | 交互式面板：查看槽位 → 选择目标 → 确认部署 |
| `fastvex init` | 初始化 `fastvex.yaml` 和 `.fastvex/` 本机文件 |
| `fastvex validate` | 校验配置，输出警告信息 |
| `fastvex show` | 展示解析后的 8 槽部署计划 |
| `fastvex status` | 展示本机记录的 Brain 槽位快照 |
| `fastvex deploy --slots 1,3` | 构建并上传指定槽位 |
| `fastvex deploy --group all` | 按配置中的分组批量部署 |
| `fastvex deploy --slots 3 --dry-run` | 预览部署计划，不执行构建 |
| `fastvex migrate` | 从旧版 `vex_upload_config.yaml` 迁移到 v2 配置 |
| `fastvex toolchain` | 查看 PROS 工具链路径 |
| `fastvex history show` | 查看部署历史 |
| `fastvex history clean --keep 5` | 清理旧的部署记录 |

安装后可使用短命令 `fvx`，与 `fastvex` 完全等价。

## C++ 项目集成最佳实践

`fastvex` 的强大之处在于能够将 `fastvex.yaml` 中配置的 `buildArgs` 优雅地注入到您的 C++ 项目中。推荐采用 **类型安全的编译期常量（static constexpr）** 结合 **Makefile 变量** 的模式进行集成，从而获得完整的 IDE 自动补全、类型检查以及编译器死代码消除（Dead Code Elimination）支持。

### 1. 在 Makefile 中接收并配置宏

在您的 PROS 项目根目录的 `Makefile` 中，接收并处理 `fastvex` 传入的命令行编译参数（如 `MODE` 和 `ROUTE`），并通过追加 `EXTRA_CXXFLAGS` 将它们转换为预处理器宏定义：

```makefile
# ---------------- [Start of Custom Config] ----------------
# 默认模式为 RED_DEBUG，避免意外覆盖
MODE ?= RED_DEBUG

# 根据 MODE 变量自动追加宏定义
ifeq ($(MODE),RED_COMP)
    EXTRA_CXXFLAGS += -DBUILD_RED -DBUILD_COMP
endif
ifeq ($(MODE),BLUE_COMP)
    EXTRA_CXXFLAGS += -DBUILD_BLUE -DBUILD_COMP
endif
ifeq ($(MODE),SKILL_COMP)
    EXTRA_CXXFLAGS += -DBUILD_SKILL -DBUILD_COMP
endif
ifeq ($(MODE),RED_DEBUG)
    EXTRA_CXXFLAGS += -DBUILD_RED -DBUILD_DEBUG
endif
ifeq ($(MODE),BLUE_DEBUG)
    EXTRA_CXXFLAGS += -DBUILD_BLUE -DBUILD_DEBUG
endif

# 自动路线编号：通过 ROUTE=N 传入，编译为 -DBUILD_ROUTE=N
ROUTE ?= 0
EXTRA_CXXFLAGS += -DBUILD_ROUTE=$(ROUTE)
# ---------------- [End of Custom Config] ----------------
```

### 2. 在 C++ 中声明编译期类型安全常量

在项目中创建并维护一个公共的配置头文件（例如 `include/config/config.hpp`），将 `Makefile` 传入的预处理器宏转换为 C++ 类型安全的常变量：

```cpp
#pragma once

namespace config {

#ifdef BUILD_DEBUG
static constexpr bool kIsDebug = true;
#else
static constexpr bool kIsDebug = false;
#endif

#ifdef BUILD_COMP
static constexpr bool kIsCompetition = true;
#else
static constexpr bool kIsCompetition = false;
#endif

#ifdef BUILD_RED
static constexpr bool kIsRed = true;
static constexpr bool kIsBlue = false;
static constexpr bool kIsSkill = false;
#elif defined(BUILD_BLUE)
static constexpr bool kIsRed = false;
static constexpr bool kIsBlue = true;
static constexpr bool kIsSkill = false;
#elif defined(BUILD_SKILL)
static constexpr bool kIsRed = false;
static constexpr bool kIsBlue = false;
static constexpr bool kIsSkill = true;
#else
static constexpr bool kIsRed = true;
static constexpr bool kIsBlue = false;
static constexpr bool kIsSkill = false;
#endif

// 接收 ROUTE 编号
#ifdef BUILD_ROUTE
static constexpr int kRoute = BUILD_ROUTE;
#else
static constexpr int kRoute = 0;
#endif

} // namespace config
```

### 3. 在业务代码中使用进行条件分支控制

在您的自动赛代码中，直接使用 `if constexpr` 引用这些编译期常量。编译器将进行静态类型诊断，并自动将不符合当前槽位条件的分支代码从最终的二进制包中彻底剔除，完全不占用 Brain 宝贵的内存空间：

```cpp
#include "config/config.hpp"

void autonomous() {
    if constexpr (config::kIsSkill) {
        // 执行技能赛自动程序
        run_skill_auton();
    } else {
        // 联队比赛路线
        if constexpr (config::kIsRed) {
            if constexpr (config::kRoute == 1) {
                // 红方左侧自动路线
                red_left_auton();
            } else if constexpr (config::kRoute == 2) {
                // 红方右侧自动路线
                red_right_auton();
            }
        } else if constexpr (config::kIsBlue) {
            if constexpr (config::kRoute == 1) {
                // 蓝方左侧自动路线
                blue_left_auton();
            }
        }
    }
}
```

## QuickStart

### 1. 安装 fastvex

```powershell
uv tool install fastvex
```

### 2. 在 PROS 项目中初始化

```powershell
cd 你的PROS项目目录
fastvex init
```

这会生成 `fastvex.yaml`（部署配置）和 `.fastvex/`（本机状态目录）。

### 3. 编辑 fastvex.yaml

根据你的队伍需求修改配置和槽位绑定。运行校验确认配置无误：

```powershell
fastvex validate
```

### 4. 部署到 Brain

```powershell
# 交互式部署
fastvex

# 或直接指定槽位
fastvex deploy --slots 1,3 -y

# 先预览再部署
fastvex deploy --slots 1,3 --dry-run
```

## Installation

需要 Python 3.11+ 和 [uv](https://docs.astral.sh/uv/)。

```powershell
# 安装
uv tool install fastvex

# 临时运行（不安装）
uvx fastvex validate

# 更新
uv tool install --upgrade fastvex
```

## FAQ

#### Q: 什么是 "Touch 增量编译保障" 机制？为什么它很重要？
**A:** 在 C++ 增量构建中，如果您仅修改了 `fastvex.yaml` 中的编译参数（例如把某个槽位从 `redComp` 切换成了 `blueComp`），由于代码文件（`.cpp`）本身的物理内容和修改时间并没有改变，标准的 `make` 工具会认为代码没有任何更新，从而跳过编译直接打包。这会导致您下载进 Brain 的程序依然保留上一次构建的逻辑！
为了解决这一致命问题，`fastvex` 会在部署前智能扫描您的 `src/` 目录，一旦发现有代码文件使用了 `kIsRed`、`kIsBlue`、`kIsSkill`、`kIsDebug`、`kIsCompetition` 或 `kRoute` 等编译期宏常量，并且当前构建的参数签名与上次构建不同，就会**自动 `touch`（更新修改时间）**这些受影响的代码文件，强制 `make` 进行正确的增量重新编译，确保部署程序的 100% 准确性。

#### Q: 配置槽位时，为什么必须显式定义全部 8 个槽位？
**A:** VEX V5 Brain 物理上严格拥有且仅有 8 个程序存储槽位。强制要求显式声明全部槽位（对于不用的槽位绑定为 `empty`），可以引导开发者始终以**全局视角**规划机器人 Brain 上的程序分布，避免在赛场上因遗忘或覆盖其他重要槽位的旧程序而造成重大失误。

#### Q: 部署过程中如果中途拔掉 USB 线或者断开连接，会发生什么？
**A:** `fastvex` 具有极佳的**部署中断保护（Interruption Protection）**机制：
1. 所有的状态文件（`state.json`）写入都采用**临时文件 + 原子替换**的形式，即使进程在写入时中断，原状态文件也绝不会损坏。
2. 部署开始时，会在 `activeExecution` 字段下记录当前部署的详细参数。每当一个槽位成功 build 或成功 upload 后，都会立即进行 **Step-level checkpoint** 持久化。
3. 如果部署被异常中断，下次启动或读取状态时，`fastvex` 会自动识别出残留的 `running` 执行，并安全地将其转换为 `interrupted` 历史记录进行归档，您可以随时在部署历史（`fastvex history show`）中追溯问题所在。

#### Q: `fastvex` 可以在哪些操作系统上运行？
**A:** `fastvex` 是基于 Python `>=3.11` 编写的通用跨平台包，完全支持 Windows、macOS 和 Linux，只要您的系统上已正确安装并配置好 [uv](https://docs.astral.sh/uv/) 及 PROS CLI。

## 贡献指南

我们非常欢迎社区的贡献！如果您希望参与 `fastvex` 的开发、修复 Bug 或添加新特性，请遵循以下流程：

### 本地开发与环境配置

本项目使用现代高效的 Python 包管理器 [uv](https://docs.astral.sh/uv/)。

1. **克隆仓库并同步虚拟环境**：
   ```powershell
   git clone https://github.com/WyattYuan/fastvex.git
   cd fastvex
   uv sync
   ```
2. **运行代码风格检查（Lint）**：
   `fastvex` 使用 Ruff 进行极其严苛的代码风格与质量管控：
   ```powershell
   uv run ruff check .
   ```
3. **运行单元测试与集成测试**：
   ```powershell
   uv run pytest
   ```
4. **一键完整性校验**：
   在提交代码前，请务必执行本地一键检查脚本，确保 Lint 和全量测试 100% 通过：
   ```powershell
   .\scripts\check.ps1
   ```

### 提交规范

为了保持项目历史的清晰度与可回溯性，请遵循 **Conventional Commits（约定式提交）** 规范。提交信息的格式建议为：
```
<type>(<scope>): <subject>

[optional body]
```
* 常见类型包括：`feat`（新功能）、`fix`（Bug 修复）、`docs`（文档更新）、`refactor`（代码重构）、`test`（增加测试）等。

## License

[MIT](LICENSE)

## 更新日志

详见 [CHANGELOG.md](CHANGELOG.md)。
