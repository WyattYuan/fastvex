# 发布新包

本文档描述 fastvex 的版本发布流程。

## 发布步骤

### 1. 更新版本号

```bash
# 自动更新 patch 版本（如 0.1.0 -> 0.1.1）
uv version --bump patch

# 或手动指定版本
uv version 0.2.0
```

### 2. 提交版本变更

```bash
git add pyproject.toml uv.lock
git commit -m "chore(release): bump version to X.Y.Z"
```

### 3. 创建 Git 标签

```bash
git tag vX.Y.Z
```

### 4. 推送到远程仓库

```bash
git push
git push origin vX.Y.Z
```

推送后，GitHub Actions 会自动触发 PyPI 发布流程。

## 版本号规范

fastvex 遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范：

- **MAJOR** (主版本号): 不兼容的 API 变更
- **MINOR** (次版本号): 向后兼容的功能性新增
- **PATCH** (修订号): 向后兼容的问题修正

## 本地测试发布

在正式发布前，建议先在本地测试安装：

```bash
# 构建 wheel 包
uv build --wheel --no-sources

# 本地安装测试
uv tool install dist/fastvex-X.Y.Z-py3-none-any.whl

# 验证安装
fastvex --version
```

## 发布检查清单

- [ ] 所有测试通过 (`uv run pytest`)
- [ ] 代码风格检查通过 (`uv run ruff check .`)
- [ ] CHANGELOG.md 已更新
- [ ] 版本号已正确更新
- [ ] 本地安装测试成功
