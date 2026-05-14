# GitHub Trending Daily Bot

每日自动推送 GitHub Trending Top 10 到企业微信。

## 部署步骤

### 1. Push 代码到仓库

```bash
cd /home/xuwenjie/Documents/github-trending-bot
git init
git remote add origin https://github.com/Wenjie-Xu/LLM_Summarize.git
git add .
git commit -m "init: daily github trending bot"
git push -u origin main
```

### 2. 配置 Webhook Secret（关键）

> **安全提醒**：不要在代码中直接填写 Webhook 地址，必须通过 GitHub Secrets 配置。

1. 打开 GitHub 仓库页面
2. 进入 **Settings → Secrets and variables → Actions**
3. 点击 **New repository secret**
   - Name: `QYWX_WEBHOOK`
   - Value: 你的企业微信机器人 Webhook 完整地址
4. 保存

### 3. 启用 Actions

进入仓库 **Actions** 页面：
- 如果提示 workflows 未启用，点击 **I understand my workflows, go ahead and enable them**

### 4. 手动测试

进入 Actions 页面 → 选择 **Daily GitHub Trending** → 点击右侧 **Run workflow** → 再次点击 **Run workflow**。

等待 1-2 分钟，查看企业微信群是否收到消息。

### 5. 定时任务

已配置每天北京时间 **09:00** 自动执行（UTC 01:00）。

如需修改时间，编辑 `.github/workflows/daily-trending.yml` 中的 `cron` 表达式。

## 文件说明

| 文件 | 说明 |
|------|------|
| `.github/workflows/daily-trending.yml` | GitHub Actions 定时配置 |
| `main.py` | 爬取 Trending 并推送的脚本 |
| `requirements.txt` | Python 依赖 |
