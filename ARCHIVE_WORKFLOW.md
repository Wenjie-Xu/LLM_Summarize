# 文档归档流程

## 触发时机

对话结束时，Claude 会自动检测当前项目的 `docs/` 目录是否有未提交变更。

## 检测逻辑

1. 检查当前工作目录（如 `/home/xuwenjie/Documents/uco-starrocks`）
2. 检查该目录下 `docs/` 是否有修改或未跟踪的文件
3. 如有变更，询问用户是否归档到本仓库

## 归档规则

所有文档直接放在 `docs/` 根目录下，**不按项目创建子目录**。

文件名格式：`{repo-name}-{original-name}.md`

| 来源项目示例 | 原文档名 | 归档后文件名 |
|-------------|----------|-------------|
| `uco-starrocks` | `starrocks-deployment-notes.md` | `uco-starrocks-starrocks-deployment-notes.md` |
| `uco-dbt` | `dbt-modeling-guide.md` | `uco-dbt-dbt-modeling-guide.md` |
| `my-project` | `setup.md` | `my-project-setup.md` |

**规则**：
1. 读取当前工作目录的 git remote origin URL，提取仓库名作为文件名前缀
2. 文档直接放入 `docs/` 根目录，不创建子文件夹
3. 同一项目的文档通过文件名前缀区分

## 归档步骤

1. 复制变更的文档文件到 `docs/` 根目录，按规则重命名
2. 更新 `docs/README.md` 索引
3. `git add && git commit && git push`

## 手动触发

如自动检测未触发，用户可直接说：
- "归档文档"
- "结束对话，归档"
