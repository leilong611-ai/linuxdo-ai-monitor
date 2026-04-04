#!/bin/bash
# Linux.do AI 日报 - 每日定时任务
cd "$(dirname "$0")"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始生成日报..."

# 运行监控脚本生成 HTML + briefing
python3 monitor.py

# 通过 lark-cli 发送飞书日报
python3 -c "
import monitor as m
import json, subprocess

config = m.load_config()
raw = m.fetch_all(config)
posts = m.deduplicate(raw)
posts = m.analyze_posts(posts)
briefing = m.build_briefing(posts)

from datetime import datetime, timezone, timedelta
tz = timezone(timedelta(hours=8))
now_str = datetime.now(tz).strftime('%Y-%m-%d')

lines = [f'## Linux.do AI 日报 | {now_str}',
         f'共 {briefing[\"total\"]} 条，Claude {briefing[\"claude_total\"]} 条\n']

if briefing['claude_alerts']:
    lines.append('### ⚠️ Claude 异常/值得关注')
    for p in briefing['claude_alerts']:
        dt = m.parse_rfc2822(p['pub_date'])
        lines.append(f'- [{p[\"title\"]}]({p[\"url\"]}) \x60{m.time_ago(dt)}\x60 💬{p[\"reply_count\"]}')
        if p.get('excerpt'):
            lines.append(f'  > {p[\"excerpt\"][:80]}')
    lines.append('')

if briefing['claude_new']:
    lines.append('### 🆕 Claude 全新动态')
    for p in briefing['claude_new']:
        dt = m.parse_rfc2822(p['pub_date'])
        lines.append(f'- [{p[\"title\"]}]({p[\"url\"]}) \x60{m.time_ago(dt)}\x60 💬{p[\"reply_count\"]}')
    lines.append('')

if briefing['claude_hot']:
    lines.append('### 🔥 Claude 高热度讨论')
    for p in briefing['claude_hot']:
        dt = m.parse_rfc2822(p['pub_date'])
        lines.append(f'- [{p[\"title\"]}]({p[\"url\"]}) \x60{m.time_ago(dt)}\x60 💬{p[\"reply_count\"]}')
    lines.append('')

if briefing['other_notable']:
    lines.append('### 📡 其他 AI 热点')
    for p in briefing['other_notable']:
        dt = m.parse_rfc2822(p['pub_date'])
        cat_e = {'alert':'⚠️','new':'🆕','hot':'🔥'}.get(p['category'],'')
        lines.append(f'- {cat_e} [{p[\"title\"]}]({p[\"url\"]}) \x60{m.time_ago(dt)}\x60 💬{p[\"reply_count\"]}')
    lines.append('')

lines.append('---')
lines.append('完整报告: https://leilong611-ai.github.io/linuxdo-ai-monitor/')

md = '\n'.join(lines)
result = subprocess.run(
    ['lark-cli', '--as', 'bot', 'im', '+messages-send',
     '--user-id', 'ou_d21370c042c46fd2ba6b28ba58a61fbe',
     '--markdown', md],
    capture_output=True, text=True, timeout=30
)
if result.returncode == 0:
    print('飞书推送成功')
else:
    print(f'飞书推送失败: {result.stderr[:200]}')
"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 日报完成"
