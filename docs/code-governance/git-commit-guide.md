# Git commit 规范

格式：`类型(范围): 英文动词原形开头的简短说明`。一次提交只写一件事。

- **范围**：功能改动用对应编号 `FEAT-01` 至 `FEAT-06`；全仓库改动用 `repo`。
- **类型**：`feat` 新功能、`fix` 修复、`test` 测试、`docs` 文档、`refactor` 重构、`ci` 持续集成。

同一功能的文档、测试和实现沿用同一个编号，例如：

```text
docs(FEAT-04): specify token warning threshold
test(FEAT-04): cover the first threshold crossing
feat(FEAT-04): warn when token usage exceeds the threshold
```
