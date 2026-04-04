#!/usr/bin/env python3
"""
linux.do AI 日报 v2
每日抓取 → 智能分类 → 生成简报 → 飞书推送 + GitHub Pages 展示
"""

import json
import sys
import time
import re
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from html import escape, unescape
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import requests

# ── 常量 ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_HTML = OUTPUT_DIR / "index.html"

NS = {"dc": "http://purl.org/dc/elements/1.1/", "discourse": "http://www.discourse.org/"}
TZ_CN = timezone(timedelta(hours=8))

# ── 分类关键词 ────────────────────────────────────────
CLAUDE_KEYWORDS = [
    "claude", "opus", "sonnet", "haiku", "anthropic", "claude code",
    "claude pro", "claude max", "claude team", "claude api",
]

NEW_KEYWORDS = [
    "发布", "更新", "上线", "新版", "v2", "v3", "正式", "推出",
    "announce", "release", "launch", "新品", "开放", "公测",
    "升级", "改版", "来了", "全新", "first", "finally",
]

ALERT_KEYWORDS = [
    "故障", "封号", "封禁", "异常", "下线", "涨价", "停服",
    "暂停", "跑路", "骗局", "风险", "警告", "安全", "泄露",
    "banned", "down", "outage", "涨价", "崩了", "挂了", "炸了",
    "被封", "限制", "收紧", "审核", "严查",
]

# ── 工具函数 ──────────────────────────────────────────
def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    fw = os.environ.get("FEISHU_WEBHOOK", "")
    if fw and not cfg["push"]["feishu"].get("webhook_url"):
        cfg["push"]["feishu"]["enabled"] = True
        cfg["push"]["feishu"]["webhook_url"] = fw
    return cfg

def strip_html(html_str):
    text = re.sub(r"<[^>]+>", "", html_str)
    text = unescape(re.sub(r"\s+", " ", text).strip())
    return text

def parse_rfc2822(t_str):
    if not t_str:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return parsedate_to_datetime(t_str)
    except (ValueError, TypeError):
        return datetime.min.replace(tzinfo=timezone.utc)

def time_ago(dt):
    seconds = int((datetime.now(timezone.utc) - dt).total_seconds())
    if seconds < 60: return "刚刚"
    if seconds < 3600: return f"{seconds // 60}分钟前"
    if seconds < 86400: return f"{seconds // 3600}小时前"
    if seconds < 604800: return f"{seconds // 86400}天前"
    return dt.astimezone(TZ_CN).strftime("%m-%d")

def is_claude_related(text):
    t = text.lower()
    return any(kw in t for kw in CLAUDE_KEYWORDS)

def extract_engagement(desc_html):
    m = re.search(r"(\d+)\s*个帖子\s*-\s*(\d+)\s*位参与者", desc_html)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 1, 1

def classify_post(post):
    title = post["title"]
    desc = post.get("excerpt", "")
    combined = f"{title} {desc}".lower()

    is_claude = is_claude_related(combined)
    is_alert = any(kw in combined for kw in ALERT_KEYWORDS)
    is_new = any(kw in combined for kw in NEW_KEYWORDS)
    score = post.get("reply_count", 1) * 2 + post.get("participant_count", 1) * 3

    if is_alert:
        category = "alert"
    elif is_new:
        category = "new"
    elif score >= 20:
        category = "hot"
    else:
        category = "normal"

    return {
        "claude": is_claude, "alert": is_alert, "new": is_new,
        "hot": category == "hot", "category": category, "score": score,
    }

# ── RSS 抓取 ─────────────────────────────────────────
def fetch_rss(url, timeout=15):
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            return ElementTree.fromstring(resp.content)
        print(f"  ⚠️ HTTP {resp.status_code}: {url}")
    except Exception as e:
        print(f"  ⚠️ 失败: {e}")
    return None

def parse_items(root, source_tag):
    posts = []
    if root is None:
        return posts
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = item.findtext("pubDate") or ""
        desc_html = item.findtext("description") or ""
        category = item.findtext("category") or ""
        author = item.findtext("dc:creator", namespaces=NS) or ""
        pinned_el = item.find("discourse:topicPinned", NS)
        pinned = (pinned_el.text == "Yes") if pinned_el is not None else False

        topic_id = 0
        m = re.search(r"/(\d+)(?:$|/|\?)", link)
        if m:
            topic_id = int(m.group(1))

        excerpt = strip_html(desc_html)[:200]
        reply_count, participant_count = extract_engagement(desc_html)

        posts.append({
            "id": topic_id, "title": title, "url": link,
            "pub_date": pub_date, "category_name": category, "author": author,
            "excerpt": excerpt, "raw_desc": desc_html, "pinned": pinned,
            "source_tag": source_tag,
            "reply_count": reply_count, "participant_count": participant_count,
        })
    return posts

def fetch_all(config):
    all_posts = []
    site = config["site"]
    delay = config["request"]["delay_seconds"]

    claude_tags = ["Claude", "人工智能"]
    for tag in claude_tags:
        url = f"{site}/tag/{tag}.rss"
        print(f"  📥 {tag}")
        root = fetch_rss(url)
        items = parse_items(root, tag)
        print(f"     → {len(items)} 条")
        all_posts.extend(items)
        time.sleep(delay)

    other_tags = [t for t in config["tags"] if t not in claude_tags]
    for tag in other_tags:
        url = f"{site}/tag/{tag}.rss"
        print(f"  📥 {tag}")
        root = fetch_rss(url)
        items = parse_items(root, tag)
        print(f"     → {len(items)} 条")
        all_posts.extend(items)
        time.sleep(delay)

    url = f"{site}/c/news/34.rss"
    print(f"  📥 前沿快讯")
    root = fetch_rss(url)
    items = parse_items(root, "前沿快讯")
    print(f"     → {len(items)} 条")
    all_posts.extend(items)
    return all_posts

# ── 去重 + 分析 ──────────────────────────────────────
def deduplicate(posts):
    seen = {}
    for p in posts:
        pid = p["id"] or hash(p["url"])
        if pid in seen:
            existing = seen[pid]
            if p["source_tag"] not in existing["_tags"]:
                existing["_tags"].append(p["source_tag"])
            if p["reply_count"] > existing["reply_count"]:
                existing["reply_count"] = p["reply_count"]
                existing["participant_count"] = p["participant_count"]
        else:
            p["_tags"] = [p["source_tag"]]
            seen[pid] = p
    return list(seen.values())

def analyze_posts(posts):
    for p in posts:
        analysis = classify_post(p)
        p.update(analysis)
    return posts

def build_briefing(posts):
    now = datetime.now(timezone.utc)
    recent = [p for p in posts if (now - parse_rfc2822(p["pub_date"])).total_seconds() < 172800]

    claude_posts = [p for p in recent if p["claude"]]
    other_posts = [p for p in recent if not p["claude"]]

    claude_alerts = sorted([p for p in claude_posts if p["category"] == "alert"], key=lambda x: -x["score"])
    claude_new = sorted([p for p in claude_posts if p["category"] == "new"], key=lambda x: -x["score"])
    claude_hot = sorted([p for p in claude_posts if p["category"] == "hot"], key=lambda x: -x["score"])
    claude_normal = sorted([p for p in claude_posts if p["category"] == "normal"], key=lambda x: -x["score"])

    other_notable = sorted(
        [p for p in other_posts if p["category"] in ("alert", "new", "hot")],
        key=lambda x: -x["score"]
    )

    return {
        "total": len(recent), "claude_total": len(claude_posts),
        "claude_alerts": claude_alerts[:5], "claude_new": claude_new[:8],
        "claude_hot": claude_hot[:5], "claude_normal": claude_normal[:10],
        "other_notable": other_notable[:8],
        "all_posts": sorted(recent, key=lambda p: parse_rfc2822(p["pub_date"]), reverse=True),
    }

# ── 飞书推送 ──────────────────────────────────────────
def format_feishu_card(briefing):
    now_str = datetime.now(TZ_CN).strftime("%Y-%m-%d %H:%M")
    elements = []

    elements.append({"tag": "markdown", "content": f"**数据概览** | 共 {briefing['total']} 条动态，Claude 相关 {briefing['claude_total']} 条"})
    elements.append({"tag": "hr"})

    if briefing["claude_alerts"]:
        lines = ["**⚠️ Claude 异常/值得关注**\n"]
        for p in briefing["claude_alerts"]:
            dt = parse_rfc2822(p["pub_date"])
            lines.append(f"- [{p['title']}]({p['url']})  `{time_ago(dt)}` 💬{p['reply_count']}")
            if p["excerpt"]:
                lines.append(f"  > {p['excerpt'][:80]}")
        elements.append({"tag": "markdown", "content": "\n".join(lines)})
        elements.append({"tag": "hr"})

    if briefing["claude_new"]:
        lines = ["**🆕 Claude 全新动态**\n"]
        for p in briefing["claude_new"]:
            dt = parse_rfc2822(p["pub_date"])
            lines.append(f"- [{p['title']}]({p['url']})  `{time_ago(dt)}` 💬{p['reply_count']}")
            if p["excerpt"]:
                lines.append(f"  > {p['excerpt'][:80]}")
        elements.append({"tag": "markdown", "content": "\n".join(lines)})
        elements.append({"tag": "hr"})

    if briefing["claude_hot"]:
        lines = ["**🔥 Claude 高热度讨论**\n"]
        for p in briefing["claude_hot"]:
            dt = parse_rfc2822(p["pub_date"])
            lines.append(f"- [{p['title']}]({p['url']})  `{time_ago(dt)}` 💬{p['reply_count']}")
        elements.append({"tag": "markdown", "content": "\n".join(lines)})
        elements.append({"tag": "hr"})

    if briefing["other_notable"]:
        lines = ["**📡 其他 AI 热点**\n"]
        for p in briefing["other_notable"]:
            dt = parse_rfc2822(p["pub_date"])
            cat_emoji = {"alert": "⚠️", "new": "🆕", "hot": "🔥"}.get(p["category"], "")
            lines.append(f"- {cat_emoji} [{p['title']}]({p['url']})  `{time_ago(dt)}` 💬{p['reply_count']}")
        elements.append({"tag": "markdown", "content": "\n".join(lines)})
        elements.append({"tag": "hr"})

    elements.append({"tag": "markdown", "content": f"完整报告: [GitHub Pages](https://leilong611-ai.github.io/linuxdo-ai-monitor/) | 更新于 {now_str}"})

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"Linux.do AI 日报 | {now_str}"},
                "template": "blue"
            },
            "elements": elements
        }
    }

def push_feishu(config, briefing):
    feishu = config.get("push", {}).get("feishu", {})
    if not feishu.get("enabled") or not feishu.get("webhook_url"):
        print("  ℹ️ 飞书未配置，跳过推送")
        return
    card = format_feishu_card(briefing)
    try:
        resp = requests.post(feishu["webhook_url"], json=card, timeout=10)
        print(f"  🐦 飞书推送: {resp.status_code} {resp.text[:100]}")
    except Exception as e:
        print(f"  ⚠️ 飞书推送失败: {e}")

# ── HTML 报告 ─────────────────────────────────────────
def generate_html(briefing, config):
    now_str = datetime.now(TZ_CN).strftime("%Y-%m-%d %H:%M:%S")
    all_posts = briefing["all_posts"]

    tag_stats = {}
    for p in all_posts:
        for tag in p.get("_tags", []):
            tag_stats[tag] = tag_stats.get(tag, 0) + 1

    cat_counts = {"alert": 0, "new": 0, "hot": 0, "normal": 0}
    for p in all_posts:
        cat_counts[p["category"]] = cat_counts.get(p["category"], 0) + 1

    def section_html(title, emoji, posts, max_items=20):
        if not posts:
            return ""
        items = ""
        for p in posts[:max_items]:
            dt = parse_rfc2822(p["pub_date"])
            tags_str = " · ".join(p["_tags"][:3])
            cat_badge = {"alert": " ⚠️", "new": " 🆕", "hot": " 🔥"}.get(p["category"], "")
            claude_cls = " claude-card" if p["claude"] else ""
            claude_tag = '<span class="meta-item claude-badge">Claude</span>' if p["claude"] else ""
            items += f"""
            <div class="post-card{claude_cls}" data-tags="{escape(','.join(p['_tags']))}" data-time="{dt.isoformat()}" data-score="{p['score']}" data-claude="{p['claude']}" data-cat="{p['category']}">
              <div class="post-header">
                <a href="{p['url']}" target="_blank" rel="noopener" class="post-title">{escape(p['title'])}{cat_badge}</a>
              </div>
              <div class="post-meta">
                <span class="meta-item">🏷️ {escape(tags_str)}</span>
                {claude_tag}
                <span class="meta-item">👤 {escape(p['author'])}</span>
                <span class="meta-item">🕐 {time_ago(dt)}</span>
                <span class="meta-item">💬 {p['reply_count']}</span>
              </div>
            </div>"""
        return f'<h2 class="section-title">{emoji} {title}</h2>{items}'

    html_sections = ""
    html_sections += section_html("Claude 异常/值得关注", "⚠️", briefing["claude_alerts"])
    html_sections += section_html("Claude 全新动态", "🆕", briefing["claude_new"])
    html_sections += section_html("Claude 高热度讨论", "🔥", briefing["claude_hot"])
    html_sections += section_html("Claude 其他动态", "📋", briefing["claude_normal"])
    html_sections += section_html("其他 AI 热点", "📡", briefing["other_notable"])

    tags_bar = ""
    for tag, count in sorted(tag_stats.items(), key=lambda x: -x[1])[:12]:
        tags_bar += f'<div class="tag-stat"><span class="tag-name">{escape(tag)}</span><span class="tag-count">{count}</span></div>'

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Linux.do AI 日报</title>
<style>
:root{{--bg:#0d1117;--card:#161b22;--border:#30363d;--text:#e6edf3;--text2:#8b949e;--accent:#58a6ff;--tag-bg:#1f2937;--claude:#d97706;--alert:#f85149;--new:#3fb950;--hot:#f0883e}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",sans-serif;line-height:1.6;padding:0 16px 40px;max-width:900px;margin:0 auto}}
.header{{padding:24px 0;border-bottom:1px solid var(--border);margin-bottom:20px}}
.header h1{{font-size:22px;font-weight:600;color:var(--accent);margin-bottom:4px}}
.header .subtitle{{color:var(--text2);font-size:13px}}
.stats{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}}
.stat-box{{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:12px 16px;min-width:100px}}
.stat-box .num{{font-size:22px;font-weight:700;color:var(--accent)}}
.stat-box .label{{font-size:12px;color:var(--text2)}}
.stat-box.alert .num{{color:var(--alert)}}
.stat-box.new .num{{color:var(--new)}}
.stat-box.hot .num{{color:var(--hot)}}
.controls{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px;align-items:center}}
.controls input{{flex:1;min-width:200px;background:var(--card);border:1px solid var(--border);border-radius:6px;padding:8px 12px;color:var(--text);font-size:14px;outline:none}}
.controls input:focus{{border-color:var(--accent)}}
.controls select{{background:var(--card);border:1px solid var(--border);border-radius:6px;padding:8px 12px;color:var(--text);font-size:14px;outline:none;cursor:pointer}}
.tags-bar{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px}}
.tag-stat{{display:flex;align-items:center;gap:4px;background:var(--tag-bg);border-radius:12px;padding:4px 10px;font-size:12px}}
.tag-stat .tag-name{{color:var(--accent)}}
.tag-stat .tag-count{{color:var(--text2)}}
.section-title{{font-size:16px;font-weight:600;margin:20px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--border);color:var(--text)}}
.post-card{{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:12px 16px;margin-bottom:8px;transition:border-color .2s}}
.post-card:hover{{border-color:var(--accent)}}
.post-card.claude-card{{border-left:3px solid var(--claude)}}
.post-header{{margin-bottom:4px}}
.post-title{{color:var(--text);text-decoration:none;font-size:15px;font-weight:500;line-height:1.4}}
.post-title:hover{{color:var(--accent);text-decoration:underline}}
.post-meta{{display:flex;gap:10px;flex-wrap:wrap;font-size:12px;color:var(--text2)}}
.meta-item{{white-space:nowrap}}
.claude-badge{{background:#d9770633;color:#d97706;padding:0 4px;border-radius:3px}}
.footer{{margin-top:32px;padding-top:16px;border-top:1px solid var(--border);color:var(--text2);font-size:12px;text-align:center}}
@media(max-width:600px){{.stats{{flex-direction:column}}.controls{{flex-direction:column}}.post-meta{{font-size:11px;gap:6px}}}}
</style>
</head>
<body>
<div class="header">
  <h1>Linux.do AI 日报</h1>
  <div class="subtitle">更新: {now_str} (CST) · 共 {briefing["total"]} 条 · Claude {briefing["claude_total"]} 条</div>
</div>
<div class="stats">
  <div class="stat-box"><div class="num">{briefing["total"]}</div><div class="label">全部动态</div></div>
  <div class="stat-box"><div class="num">{briefing["claude_total"]}</div><div class="label">Claude</div></div>
  <div class="stat-box alert"><div class="num">{cat_counts["alert"]}</div><div class="label">⚠️ 异常</div></div>
  <div class="stat-box new"><div class="num">{cat_counts["new"]}</div><div class="label">🆕 新动态</div></div>
  <div class="stat-box hot"><div class="num">{cat_counts["hot"]}</div><div class="label">🔥 热门</div></div>
</div>
<div class="tags-bar">{tags_bar}</div>
<div class="controls">
  <input type="text" id="searchInput" placeholder="搜索标题、标签..." oninput="filterPosts()">
  <select id="filterSelect" onchange="filterPosts()">
    <option value="all">全部</option>
    <option value="claude">仅 Claude</option>
    <option value="alert">⚠️ 异常</option>
    <option value="new">🆕 新动态</option>
    <option value="hot">🔥 热门</option>
  </select>
  <select id="sortSelect" onchange="sortPosts()">
    <option value="time">按时间</option>
    <option value="score">按热度</option>
  </select>
</div>
{html_sections}
<div class="footer">linuxdo-ai-monitor v2 · GitHub Actions 每日自动运行 · 数据归 linux.do 社区所有</div>
<script>
function filterPosts(){{
  const q=document.getElementById('searchInput').value.toLowerCase();
  const f=document.getElementById('filterSelect').value;
  document.querySelectorAll('.post-card').forEach(c=>{{
    const t=c.querySelector('.post-title').textContent.toLowerCase();
    const g=c.dataset.tags.toLowerCase();
    const isC=c.dataset.claude==='true';
    const cat=c.dataset.cat;
    let show=true;
    if(q)show=t.includes(q)||g.includes(q);
    if(f==='claude')show=show&&isC;
    if(f==='alert')show=show&&cat==='alert';
    if(f==='new')show=show&&cat==='new';
    if(f==='hot')show=show&&cat==='hot';
    c.style.display=show?'':'none';
  }});
}}
function sortPosts(){{
  const ct=document.querySelector('body');
  const s=document.getElementById('sortSelect').value;
  const cards=Array.from(document.querySelectorAll('.post-card'));
  cards.sort((a,b)=>s==='time'?b.dataset.time.localeCompare(a.dataset.time):parseInt(b.dataset.score)-parseInt(a.dataset.score));
  cards.forEach(c=>c.parentNode.appendChild(c));
}}
</script>
</body>
</html>"""

# ── 主流程 ────────────────────────────────────────────
def main():
    print("=" * 50)
    print("  Linux.do AI 日报 v2")
    print("=" * 50)

    config = load_config()

    print("\n📥 抓取 RSS...")
    raw = fetch_all(config)
    print(f"\n   原始: {len(raw)} 条")

    posts = deduplicate(raw)
    print(f"   去重: {len(posts)} 条")

    posts = analyze_posts(posts)

    briefing = build_briefing(posts)
    print(f"\n📊 简报统计:")
    print(f"   Claude 相关: {briefing['claude_total']} 条")
    print(f"   ⚠️ 异常: {len(briefing['claude_alerts'])} 条")
    print(f"   🆕 新动态: {len(briefing['claude_new'])} 条")
    print(f"   🔥 热门: {len(briefing['claude_hot'])} 条")

    print("\n📄 生成报告...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    html = generate_html(briefing, config)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"   ✅ {OUTPUT_HTML}")

    print("\n📱 推送飞书日报...")
    push_feishu(config, briefing)

    print(f"\n✅ 完成")

if __name__ == "__main__":
    main()
