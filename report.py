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
HISTORY_DIR = OUTPUT_DIR / "history"
API_DIR = OUTPUT_DIR / "api"

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


def load_ai_analysis():
    """从 API 数据中加载已有的 AI 分析结果"""
    api_path = API_DIR / "posts.json"
    if not api_path.exists():
        return {}
    try:
        with open(api_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            p.get("uid", ""): {"rating": p.get("ai_rating"), "comment": p.get("ai_comment", "")}
            for p in data.get("posts", [])
            if p.get("ai_rating")
        }
    except Exception:
        return {}


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

    # 加载已有的 AI 分析结果
    ai_data = load_ai_analysis()

    # 构建各板块的帖子
    sections = {}
    for cat_id, cat_info in sorted(CATEGORY_KEYWORDS.items(), key=lambda x: x[1]["priority"]):
        cat_posts = [p for p in briefing.all_posts if p.category == cat_id]
        if cat_posts:
            cat_posts.sort(key=lambda p: p.engagement_score, reverse=True)
            sections[cat_id] = cat_posts

    # 为帖子添加显示属性
    for cat_posts in sections.values():
        for p in cat_posts:
            p.time_ago = time_ago(p.published_at)
            # 注入 AI 分析数据
            ai = ai_data.get(p.uid, {})
            p.ai_rating = ai.get("rating")
            p.ai_comment = ai.get("comment", "")

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

    # ── 历史存档 ──
    archive_daily(briefing)

    print(f"   ✅ {OUTPUT_HTML}")
    return html


def archive_daily(briefing):
    """保存每日快照到 history/ 和 api/ 目录"""
    date_str = briefing.date or datetime.now(TZ_CN).strftime("%Y-%m-%d")

    # 1) 历史快照: history/2026-04-04.json
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_path = HISTORY_DIR / f"{date_str}.json"
    briefing_data = briefing.to_dict()
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(briefing_data, f, ensure_ascii=False, indent=2, default=str)
    print(f"   📦 历史快照: {snapshot_path}")

    # 2) API 数据接口: api/posts.json (供 AI 读取)
    API_DIR.mkdir(parents=True, exist_ok=True)
    # 保留已有的 AI 分析结果
    existing_ai = {}
    api_path = API_DIR / "posts.json"
    if api_path.exists():
        try:
            with open(api_path, "r") as f:
                old = json.load(f)
            for p in old.get("posts", []):
                if p.get("ai_rating"):
                    existing_ai[p.get("uid", "")] = {
                        "ai_rating": p["ai_rating"],
                        "ai_comment": p.get("ai_comment", ""),
                    }
        except Exception:
            pass

    api_data = {
        "date": date_str,
        "total": briefing.total,
        "updated_at": datetime.now(TZ_CN).isoformat(),
        "api_version": 1,
        "description": "AI 情报雷达 - 每日新闻数据接口，供 AI 分析使用",
        "posts": [],
    }
    for p in briefing.all_posts:
        ai = existing_ai.get(p.uid, {})
        api_data["posts"].append({
            "uid": p.uid,
            "title": p.title,
            "url": p.url,
            "summary": p.summary,
            "source": p.sources,
            "category": p.category,
            "is_claude": p.is_claude,
            "is_alert": p.is_alert,
            "is_new": p.is_new,
            "engagement_score": p.engagement_score,
            "author": p.author,
            "excerpt": p.excerpt,
            "published_at": p.published_at.isoformat() if p.published_at else "",
            "ai_rating": ai.get("ai_rating"),
            "ai_comment": ai.get("ai_comment", ""),
        })
    with open(api_path, "w", encoding="utf-8") as f:
        json.dump(api_data, f, ensure_ascii=False, indent=2, default=str)
    print(f"   🔌 API 接口: {api_path}")

    # 3) 历史索引页
    generate_history_index()


def generate_history_index():
    """生成历史报告索引页"""
    if not HISTORY_DIR.exists():
        return

    snapshots = sorted(HISTORY_DIR.glob("*.json"), reverse=True)
    rows = ""
    for snap in snapshots:
        date_str = snap.stem
        try:
            with open(snap, "r", encoding="utf-8") as f:
                data = json.load(f)
            total = data.get("total", 0)
            sections = data.get("sections", {})
            cat_summary = " · ".join(
                f"{k}:{len(v)}" for k, v in sections.items() if v
            )
        except Exception:
            total = "?"
            cat_summary = ""

        rows += f"""
      <a href="{snap.name}" class="history-row">
        <span class="date">{date_str}</span>
        <span class="total">{total} 条</span>
        <span class="cats">{cat_summary}</span>
        <span class="arrow">→</span>
      </a>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI 情报雷达 - 历史存档</title>
<style>
:root{{--bg:#0a0e17;--card:#131a2b;--border:#1e2d45;--text:#e2e8f0;--text2:#8892a4;--accent:#60a5fa}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",sans-serif;line-height:1.6;padding:20px;max-width:800px;margin:0 auto}}
h1{{font-size:22px;font-weight:700;margin-bottom:8px;background:linear-gradient(135deg,var(--accent),#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}}
.back{{color:var(--text2);font-size:13px;margin-bottom:20px;display:inline-block;text-decoration:none}}
.back:hover{{color:var(--accent)}}
.history-row{{display:grid;grid-template-columns:110px 70px 1fr 30px;gap:8px;align-items:center;background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px 16px;margin-bottom:8px;text-decoration:none;color:var(--text);transition:all .2s}}
.history-row:hover{{border-color:var(--accent);transform:translateX(2px)}}
.date{{font-weight:600;color:var(--accent)}}
.total{{color:var(--text2);font-size:13px}}
.cats{{color:var(--text2);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.arrow{{color:var(--text2);text-align:right}}
@media(max-width:600px){{.history-row{{grid-template-columns:90px 60px 1fr 24px}}.cats{{display:none}}}}
</style>
</head>
<body>
<a href="../index.html" class="back">← 返回今日报告</a>
<h1>历史存档</h1>
{rows}
</body>
</html>"""

    with open(HISTORY_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"   📅 历史索引: {HISTORY_DIR / 'index.html'}")
