# linuxdo-ai-monitor

自动监控 [linux.do](https://linux.do) 社区的 AI 相关动态，生成 HTML 报告并通过 GitHub Pages 展示，可选推送到手机。

## 功能

- 按标签抓取: 人工智能、Claude、ChatGPT、OpenAI、DeepSeek、Cursor、Copilot、Gemini 等 16 个 AI 标签
- 按关键词搜索: AI 账号、Claude 订阅、Claude Code、AI 中转等
- 自动去重合并，按时间排序
- 生成暗色主题的 HTML 报告，支持搜索和排序
- GitHub Pages 在线访问
- 可选 Bark (iPhone) / 飞书 推送通知
- 每 4 小时自动运行

## 部署步骤（从零开始）

### 1. 创建 GitHub 仓库

```bash
# 进入项目目录
cd ~/Documents/linuxdo-ai-monitor

# 初始化 Git
git init
git add .
git commit -m "feat: init linuxdo-ai-monitor"

# 在 GitHub 创建仓库（需要 gh CLI）
gh repo create linuxdo-ai-monitor --public --source=. --push
```

### 2. 启用 GitHub Pages

1. 打开你的仓库页面 `https://github.com/你的用户名/linuxdo-ai-monitor`
2. 点击 **Settings** → **Pages**
3. Source 选择 **Deploy from a branch**
4. Branch 选择 **gh-pages** → **/ (root)** → **Save**

### 3. 配置推送通知（可选）

#### Bark（iPhone 推送）

1. App Store 下载 **Bark** 应用
2. 打开 App，复制你的 Key（URL 中 `/你的key/` 那部分）
3. 在 GitHub 仓库中: **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
   - Name: `BARK_KEY`
   - Value: 你的 Bark Key

#### 飞书 Webhook

1. 飞书群 → 群设置 → 群机器人 → 添加自定义机器人
2. 复制 Webhook URL
3. 添加 GitHub Secret:
   - Name: `FEISHU_WEBHOOK`
   - Value: 你的 Webhook URL

### 4. 验证运行

1. 打开仓库页面 → **Actions** 标签
2. 左侧选择 **Linux.do AI Monitor**
3. 点击 **Run workflow** → **Run workflow** 手动触发一次
4. 等待约 2 分钟完成
5. 访问 `https://你的用户名.github.io/linuxdo-ai-monitor/` 查看报告

### 5. 自动运行

脚本已配置每 4 小时自动运行（北京时间 9,13,17,21,1,5 点），无需手动操作。

## 本地运行

```bash
cd ~/Documents/linuxdo-ai-monitor
pip install -r requirements.txt
python monitor.py
# 报告生成在 output/index.html
open output/index.html
```

## 自定义

编辑 `config.json`:

```json
{
  "tags": ["人工智能", "Claude", ...],      // 监控的标签
  "search_queries": ["AI 账号", ...],       // 搜索关键词
  "push": {
    "bark": { "enabled": true, "key": "..." },
    "feishu": { "enabled": true, "webhook_url": "..." }
  }
}
```

## 费用

全部免费:
- GitHub Actions: 免费账户每月 2000 分钟（本脚本每次约 2-3 分钟）
- GitHub Pages: 免费
- Bark 推送: 免费
- 飞书 Webhook: 免费
