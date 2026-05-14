# 文档归档流程

## 触发时机

对话结束时，Claude 会自动检测当前项目的 `docs/` 目录是否有未提交变更。

## 检测逻辑

1. 检查当前工作目录（如 `/home/xuwenjie/Documents/uco-starrocks`）
2. 检查该目录下 `docs/` 是否有修改或未跟踪的文件
3. 如有变更，询问用户是否归档到本仓库

## 归档路径映射

自动根据来源项目的 **git 仓库名** 创建对应目录，目录不存在则自动创建。

| 来源项目示例 | 归档目标路径 |
|-------------|-------------|
| `/home/xuwenjie/Documents/uco-starrocks` → 仓库名 `uco-starrocks` | `docs/uco-starrocks/` |
| `/home/xuwenjie/Documents/uco-dbt` → 仓库名 `uco-dbt` | `docs/uco-dbt/` |
| `/home/xuwenjie/Documents/my-project` → 仓库名 `my-project` | `docs/my-project/` |

**规则**：
1. 读取当前工作目录的 git remote origin URL，提取仓库名作为分类名
2. 目录不存在时自动 `mkdir -p docs/<repo-name>/`
3. 同一项目的所有文档集中在一个目录下，不分散到 others

## 归档步骤

1. 复制变更的文档文件到对应分类目录
2. 更新 `docs/README.md` 索引
3. `git add && git commit && git push`

## 手动触发

如自动检测未触发，用户可直接说：
- "归档文档"
- "结束对话，归档"
