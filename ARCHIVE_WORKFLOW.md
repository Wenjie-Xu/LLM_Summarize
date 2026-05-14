# 文档归档流程

## 触发时机

对话结束时，Claude 会自动检测当前项目的 `docs/` 目录是否有未提交变更。

## 检测逻辑

1. 检查当前工作目录（如 `/home/xuwenjie/Documents/uco-starrocks`）
2. 检查该目录下 `docs/` 是否有修改或未跟踪的文件
3. 如有变更，询问用户是否归档到本仓库

## 归档路径映射

| 来源项目目录关键字 | 归档目标路径 |
|-------------------|-------------|
| `uco-starrocks` | `docs/starrocks/` |
| `dbt` | `docs/dbt/` |
| `trino` | `docs/trino/` |
| 其他 | `docs/others/` |

## 归档步骤

1. 复制变更的文档文件到对应分类目录
2. 更新 `docs/README.md` 索引
3. `git add && git commit && git push`

## 手动触发

如自动检测未触发，用户可直接说：
- "归档文档"
- "结束对话，归档"
