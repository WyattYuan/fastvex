# 贡献

## 发布新包

```bash
uv version --bump patch
git add pyproject.toml uv.lock
git commit -m "Bump version to 0.1.1"
git tag v0.1.1
git push
git push origin v0.1.1
```

## 本地测试

```bash
uv tool install dist/fastvex-0.1.0-py3-none-any.whl
```