"""HTML 报告渲染 - V3"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

from jinja2 import Environment, FileSystemLoader

from models import Briefing, Post, SourceStatus
from classifier import CATEGORY_KEYWORDS, get_category_info

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_HTML = OUTPUT_DIR / "index.html"
OUTPUT_JSON = OUTPUT_DIR / "briefing.json"

TZ_CN = timezone(timedelta(hours=8))


def time_ago(dt):
    """相对时间显示"""
    if not dt or dt.year < 2000:
        return "未知"
    now = datetime.now(timezone.utc)
    seconds = int((now - dt).total_seconds())
    if seconds < 0:
        return "刚刚"
    if seconds < 60:
        return "刚刚"
    if seconds < 3600:
        return f"{seconds // 60}分钟前"
    if seconds < 86400:
        return f"{seconds // 3600}小时前"
    if seconds < 604800:
        return f"{seconds // 86400}天前"
    return dt.astimezone(TZ_CN).strftime("%m-%d")


def build_briefing(posts, source_statuses):
    """从分类后的帖子构建简报"""
    now = datetime.now(TZ_CN)
    date_str = now.strftime("%Y-%m-%d")

    # 按时间过滤（48小时内）
    utc_now = datetime.now(timezone.utc)
    recent = [p for p in posts if p.published_at and p.published_at.year >= 2000
              and (utc_now - p.published_at).total_seconds() < 172800]

    briefing = Briefing(
        date=date_str,
        total=len(recent),
        source_statuses=source_statuses,
        all_posts=recent,
    )

    return briefing


def render_report(briefing):
    """渲染 HTML 报告"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 准备模板数据
    now_str = datetime.now(TZ_CN).strftime("%Y-%m-%d %H:%M:%S")

    # 构建各板块的帖子
    sections = {}
    for cat_id, cat_info in sorted(CATEGORY_KEYWORDS.items(), key=lambda x: x[1]["priority"]):
        cat_posts = [p for p in briefing.all_posts if p.category == cat_id]
        if cat_posts:
            cat_posts.sort(key=lambda p: p.engagement_score, reverse=True)
            sections[cat_id] = cat_posts

    # 为帖子添加 time_ago 显示
    for cat_posts in sections.values():
        for p in cat_posts:
            p_dict = p.to_dict()
            p.time_ago = time_ago(p.published_at)
            p_dict["time_ago"] = p.time_ago

    # 准备模板上下文
    context = {
        "report_title": "AI 情报雷达",
        "now_str": now_str,
        "total": briefing.total,
        "source_count": len(briefing.source_statuses),
        "source_statuses": [
            {"name": s.source_name, "success": s.success, "count": s.post_count, "error": s.error}
            for s in briefing.source_statuses
        ],
        "categories": CATEGORY_KEYWORDS,
        "sections": sections,
    }

    # Jinja2 渲染
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    template = env.get_template("report.html")
    html = template.render(**context)

    # 写入文件
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    # 保存 JSON 数据
    briefing_data = briefing.to_dict()
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(briefing_data, f, ensure_ascii=False, indent=2, default=str)

    print(f"   ✅ {OUTPUT_HTML}")
    return html
