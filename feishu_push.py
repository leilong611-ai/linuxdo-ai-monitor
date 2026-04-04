#!/usr/bin/env python3
"""
飞书推送模块 - 通过 lark-cli 发送 AI 日报
"""
import json
import subprocess
import sys

USER_ID = "ou_d21370c042c46fd2ba6b28ba58a61fbe"

def push_daily_briefing(briefing):
    """通过 lark-cli 发送每日 AI 日报"""
    from monitor import parse_rfc2822, time_ago, TZ_CN
    from datetime import datetime, timezone, timedelta

    now_str = datetime.now(TZ_CN).strftime("%Y-%m-%d")

    # 构建 Markdown 内容
    lines = [
        f"## Linux.do AI 日报 | {now_str}",
        f"**数据概览**: 共 {briefing['total']} 条动态，Claude 相关 {briefing['claude_total']} 条\n",
    ]

    if briefing["claude_alerts"]:
        lines.append("### ⚠️ Claude 异常/值得关注")
        for p in briefing["claude_alerts"]:
            dt = parse_rfc2822(p["pub_date"])
            lines.append(f"- [{p['title']}]({p['url']}) `{time_ago(dt)}` 💬{p['reply_count']}")
            if p.get("excerpt"):
                lines.append(f"  > {p['excerpt'][:80]}")
        lines.append("")

    if briefing["claude_new"]:
        lines.append("### 🆕 Claude 全新动态")
        for p in briefing["claude_new"]:
            dt = parse_rfc2822(p["pub_date"])
            lines.append(f"- [{p['title']}]({p['url']}) `{time_ago(dt)}` 💬{p['reply_count']}")
        lines.append("")

    if briefing["claude_hot"]:
        lines.append("### 🔥 Claude 高热度讨论")
        for p in briefing["claude_hot"]:
            dt = parse_rfc2822(p["pub_date"])
            lines.append(f"- [{p['title']}]({p['url']}) `{time_ago(dt)}` 💬{p['reply_count']}")
        lines.append("")

    if briefing["other_notable"]:
        lines.append("### 📡 其他 AI 热点")
        for p in briefing["other_notable"]:
            dt = parse_rfc2822(p["pub_date"])
            cat_emoji = {"alert": "⚠️", "new": "🆕", "hot": "🔥"}.get(p["category"], "")
            lines.append(f"- {cat_emoji} [{p['title']}]({p['url']}) `{time_ago(dt)}` 💬{p['reply_count']}")
        lines.append("")

    lines.append("---")
    lines.append("完整报告: https://leilong611-ai.github.io/linuxdo-ai-monitor/")

    md_content = "\n".join(lines)

    cmd = [
        "lark-cli", "--as", "bot", "im", "+messages-send",
        "--user-id", USER_ID,
        "--markdown", md_content,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"  🐦 飞书推送成功")
        else:
            print(f"  ⚠️ 飞书推送失败: {result.stderr[:200]}")
    except Exception as e:
        print(f"  ⚠️ 飞书推送异常: {e}")

if __name__ == "__main__":
    # 独立测试：读取 briefing 数据并推送
    data_path = sys.argv[1] if len(sys.argv) > 1 else "output/briefing.json"
    with open(data_path, "r") as f:
        briefing = json.load(f)
    push_daily_briefing(briefing)
