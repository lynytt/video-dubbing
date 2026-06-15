# 贡献指南

感谢你考虑为 Video Dubbing 做贡献！

## 开发指南

### 环境设置

```bash
git clone https://github.com/lynytt/video-dubbing.git
cd video-dubbing
pip install -r requirements.txt
```

### 代码规范

- Python 代码遵循 PEP 8
- 变量名使用蛇形命名法（snake_case）
- 函数/方法添加类型注解和 docstring

### 提交 PR

1. Fork 本仓库
2. 创建特性分支: `git checkout -b feat/your-feature`
3. 提交更改: `git commit -m "feat: add your feature"`
4. 推送到分支: `git push origin feat/your-feature`
5. 创建 Pull Request

### 角色关键词扩展

如需添加新的角色或关键词匹配规则，编辑 `scripts/dub_video.py` 中的 `SPEAKER_RULES` 列表：

```python
SPEAKER_RULES = [
    ("你的角色名", ["关键词1", "关键词2", ...]),
]
```

### 翻译词典扩展

在 `scripts/dub_video.py` 的 `BUILTIN_TRANSLATIONS` 字典中添加新条目。
