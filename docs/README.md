# 归档文档索引

自动归类来自各项目的对话文档。

## 目录结构

```
docs/
├── README.md               # 本索引
├── <repo-name>/           # 按来源 git 仓库名自动创建
│   └── xxx.md
└── ...
```

**分类规则**：根据来源项目的 git 仓库名自动创建目录，目录不存在则自动创建。

## 归档记录

| 日期 | 来源项目 | 文档名 | 路径 |
|------|----------|--------|------|
| 2026-04-30 | uco-starrocks | starrocks-deployment-notes.md | docs/starrocks/ |
| 2026-04-30 | uco-starrocks | uco-dw-access.md | docs/starrocks/ |
