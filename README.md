# AI 情报雷达

> LinuxDo AI 社区情报监控与交互平台

## 版本

**当前版本：V4（2026-04-06）**

这是持续迭代版本，后续会不断更新优化。

## 功能

| 功能 | 状态 | 说明 |
|------|------|------|
| 多源 RSS 抓取 | ✅ | 14 个 AI 信息源（linux.do, HN, Reddit, 36kr 等） |
| AI 三层评论 | ✅ | brief_comment / deep_comment / industry_impact |
| SQLite 数据库 | ✅ | 6 张表，持久化存储 |
| 交互式 Web 界面 | ✅ | Apple 风格暗色设计 |
| 用户评论 + 评分 + 立场 | ✅ | 浏览器端交互 |
| AI 自动回应 | ⚠️ | 功能完整，LaunchAgent 下 BigModel API 报 401（终端直跑正常） |
| 双流推荐 | ✅ | 「我的视角」vs「大众视角」 |
| 用户兴趣画像 | ✅ | 自动从评论构建 |
| 飞书推送 | ✅ | Bot 消息推送 |
| GitHub Actions 定时抓取 | ✅ | 每天 UTC 0:00 / 6:00 / 12:00 / 18:00 |
| Cloudflare Tunnel 外网访问 | ✅ | 临时地址，可选 |

## 文件结构

```
linuxdo-ai-monitor/
├── web_app.py              # Flask Web 应用（交互版）
├── monitor.py              # 主监控脚本
├── database.py             # SQLite 数据库层
├── ai_analyzer.py          # AI 分析模块（三层评论）
├── report.py               # 报告生成
├── models.py               # 数据模型
├── scorer.py               # 评分算法
├── feishu_push.py           # 飞书推送
├── config.json             # 数据源配置
├── requirements.txt        # Python 依赖
├── templates/
│   ├── interactive.html    # 交互版 Web 界面（V4）
│   └── report.html         # 静态报告模板
├── scripts/
│   └── start-tunnel.sh     # Cloudflare Tunnel 外网访问
├── data/
│   └── radar.db            # SQLite 数据库
├── output/                 # 生成的静态报告 + GitHub Pages
└── ~/Library/LaunchAgents/
    └── com.user.radar-web.plist   # Flask 开机自启
```

## 快速启动

### 启动 Web 服务

```bash
# 方式一：终端直接运行（推荐，AI 回应正常）
cd ~/Documents/linuxdo-ai-monitor
python3 web_app.py
# 打开 http://localhost:5001

# 方式二：LaunchAgent 后台运行（已配置，开机自启）
# 直接打开 http://localhost:5001
```

### 外网访问（可选）

```bash
bash ~/Documents/linuxdo-ai-monitor/scripts/start-tunnel.sh
# 输出 https://xxx.trycloudflare.com 临时地址
```

### 手动抓取数据

```bash
cd ~/Documents/linuxdo-ai-monitor
python3 monitor.py
```

## 技术栈

- **后端**：Python 3.13 + Flask + SQLite
- **AI**：GLM-5.1（via BigModel API / Anthropic 兼容接口）
- **前端**：原生 HTML/CSS/JS，Apple Design 风格
- **推送**：飞书 Bot
- **定时任务**：GitHub Actions + macOS LaunchAgent
- **外网穿透**：Cloudflare Tunnel

## 已知问题

1. **AI 回应 401**：从 LaunchAgent 进程调用 BigModel API 返回 401，终端直接运行正常。建议终端 `python3 web_app.py` 方式使用。
2. **Cloudflare Tunnel 临时地址**：每次重启会变。固定地址需 Cloudflare 账号 + 域名。
3. **Reddit RSS 本地 403**：需要代理，GitHub Actions 环境正常。

## 更新日志

### V4 (2026-04-06)
- 新增交互式 Web 界面（Apple 风格暗色设计）
- 用户评论、评分、立场选择
- AI 自动回应（异步 + 轮询）
- 双流推荐（个性化 + 大众）
- 用户兴趣画像自动构建
- Cloudflare Tunnel 外网访问
- 飞书 Bot 推送

### V3 (2026-04-03)
- 多源 AI 情报雷达（14 个数据源）
- AI 三层评论体系
- SQLite 持久化数据库
- 飞书推送集成
- GitHub Pages 自动部署

### V2
- HTML 暗色报告 + 搜索排序
- 多标签监控
- Bark / 飞书推送

---

*此项目持续迭代中，欢迎随时更新优化。*
