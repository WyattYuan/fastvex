# 贡献指南

我们非常欢迎社区的贡献！如果您希望参与 `fastvex` 的开发、修复 Bug 或添加新特性，请遵循以下流程。

## 本地开发与环境配置

本项目使用现代高效的 Python 包管理器 [uv](https://docs.astral.sh/uv/)。

### 1. 克隆仓库并同步虚拟环境

```bash
git clone https://github.com/WyattYuan/fastvex.git
cd fastvex
uv sync
```

### 2. 运行代码风格检查（Lint）

`fastvex` 使用 Ruff 进行极其严苛的代码风格与质量管控：

```bash
uv run ruff check .
```

### 3. 运行单元测试与集成测试

```bash
uv run pytest
```

### 4. 一键完整性校验

在提交代码前，请务必执行本地一键检查脚本，确保 Lint 和全量测试 100% 通过：

```powershell
.\scripts\check.ps1
```

## 本地测试安装

构建并本地安装测试：

```bash
# 构建 wheel 包
uv build --wheel --no-sources

# 本地安装测试
uv tool install dist/fastvex-X.Y.Z-py3-none-any.whl
```

## 提交规范

为了保持项目历史的清晰度与可回溯性，请遵循 **Conventional Commits（约定式提交）** 规范。提交信息的格式建议为：

```
<type>(<scope>): <subject>

[optional body]
```

### 提交类型

- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `refactor`: 代码重构
- `test`: 增加测试
- `chore`: 构建过程或辅助工具的变动
- `perf`: 性能优化
- `style`: 代码风格调整（不影响代码运行的变动）

### 示例

```
feat(build): 添加并行编译支持
fix(upload): 修复多槽位上传时的进度显示问题
docs(readme): 更新快速开始指南
```

## Pull Request 流程

1. Fork 本仓库
2. 创建您的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交您的更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建一个 Pull Request

## 发布新包

发布流程请参考 [发布指南](docs/PUBLISH.md)。

## 问题反馈

如果您遇到任何问题或有建议，请通过 [GitHub Issues](https://github.com/WyattYuan/fastvex/issues) 提交。
