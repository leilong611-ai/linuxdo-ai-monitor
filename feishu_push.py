"""飞书推送模块 - V3 多源 AI 情报雷达"""

import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta

USER_ID = "ou_d21370c042c46fd2ba6b28ba58a61fbe"
TZ_CN = timezone(timedelta(hours=8))
PAGES_URL = "https://leilong611-ai.github.io/linuxdo-ai-monitor/"


def time_ago(dt):
    if not dt or dt.year < 2000:
        return ""
    now = datetime.now(timezone.utc)
    seconds = int((now - dt).total_seconds())
    if seconds < 60:
        return "刚刚"
    if seconds < 3600:
        return f"{seconds // 60}分钟前"
    if seconds < 86400:
        return f"{seconds // 3600}小时前"
    if seconds < 604800:
        return f"{seconds // 86400}天前"
    return dt.astimezone(TZ_CN).strftime("%m-%d")


def push_daily_briefing(briefing):
    """通过 lark-cli 发送每日 AI 情报雷达"""
    now_str = datetime.now(TZ_CN).strftime("%Y-%m-%d")

    lines = [
        f"## AI 情报雷达 | {now_str}",
        f"**数据概览**: 共 {briefing.total} 条动态，来自 {len(briefing.source_statuses)} 个源\n",
    ]

    # 各板块摘要
    section_emojis = {
        "claude": "🟠 Claude 专区",
        "openai": "🟢 OpenAI / GPT",
        "gemini": "🔵 Gemini",
        "xai": "🟣 xAI / Grok",
        "cn_llm": "🔴 国内大模型",
        "ai_tools": "🔧 AI 工具",
        "forum_tips": "💡 论坛技巧",
        "trending": "🔥 突发热点",
    }

    for cat_id, label in section_emojis.items():
        cat_posts = [p for p in briefing.all_posts if p.category == cat_id]
        if not cat_posts:
            continue

        # 取前 3 条
        top = sorted(cat_posts, key=lambda p: p.engagement_score, reverse=True)[:3]
        lines.append(f"### {label}")

        for p in top:
            src_str = "+".join(p.sources[:2])
            ta = time_ago(p.published_at)
            alert_flag = " ⚠️" if p.is_alert else ""
            new_flag = " 🆕" if p.is_new else ""

            # AI 评分标签
            ai_tag = ""
            if hasattr(p, 'ai_rating') and p.ai_rating:
                stars = "★" * p.ai_rating + "☆" * (5 - p.ai_rating)
                ai_tag = f" `{stars}`"
                if hasattr(p, 'ai_comment') and p.ai_comment:
                    ai_tag += f" _{p.ai_comment}_"

            lines.append(f"- [{p.title}]({p.url}) `{src_str}` `{ta}` ⭐{p.engagement_score}{ai_tag}{alert_flag}{new_flag}")

        lines.append("")

    lines.append("---")
    lines.append(f"完整报告: [GitHub Pages]({PAGES_URL})")

    md_content = "\n".join(lines)

    # 限制消息长度（飞书有 30KB 限制）
    if len(md_content) > 28000:
        md_content = md_content[:28000] + "\n\n... (内容过长，请查看完整报告)"

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
    data_path = sys.argv[1] if len(sys.argv) > 1 else "output/briefing.json"
    with open(data_path, "r") as f:
        data = json.load(f)

    # 重建 Briefing 对象
    from models import Briefing, Post, SourceStatus

    briefing = Briefing(
        date=data.get("date", ""),
        total=data.get("total", 0),
        source_statuses=[
            SourceStatus(
                source_id=s["id"],
                source_name=s["name"],
                success=s["success"],
                post_count=s["count"],
                error=s.get("error", ""),
            )
            for s in data.get("source_statuses", [])
        ],
        all_posts=[],
    )

    # 重建 Post 列表
    for section_posts in data.get("sections", {}).values():
        for pd in section_posts:
            post = Post(
                uid=pd["uid"],
                title=pd["title"],
                url=pd["url"],
                source_id=pd.get("source_id", ""),
                source_name=pd.get("source_name", ""),
                sources=pd.get("sources", []),
                engagement_score=pd.get("engagement_score", 0),
                category=pd.get("category", "trending"),
                is_claude=pd.get("is_claude", False),
                is_alert=pd.get("is_alert", False),
                is_new=pd.get("is_new", False),
                excerpt=pd.get("excerpt", ""),
                author=pd.get("author", ""),
                tags=pd.get("tags", []),
            )
            # 解析时间
            pub_str = pd.get("published_at", "")
            if pub_str:
                try:
                    from datetime import datetime
                    post.published_at = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass
            briefing.all_posts.append(post)

    push_daily_briefing(briefing)
