#!/usr/bin/env python3
"""
linux.do AI 动态监控脚本
通过 RSS 抓取 linux.do 的 AI 相关帖子，生成 HTML 报告并可选推送通知。
"""

import json
import os
import sys
import time
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from html import escape
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import requests

# ── 常量 ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_HTML = OUTPUT_DIR / "index.html"

NS = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "discourse": "http://www.discourse.org/",
    "atom": "http://www.w3.org/2005/Atom",
}

# ── 工具函数 ──────────────────────────────────────────
def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def strip_html(html_str):
    """去掉 HTML 标签，返回纯文本"""
    text = re.sub(r"<[^>]+>", "", html_str)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def parse_rfc2822(t_str):
    """解析 RFC 2822 时间 (RSS 默认格式)"""
    if not t_str:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return parsedate_to_datetime(t_str)
    except (ValueError, TypeError):
        return datetime.min.replace(tzinfo=timezone.utc)

def format_time_ago(dt):
    """相对时间描述"""
    now = datetime.now(timezone.utc)
    seconds = int((now - dt).total_seconds())
    if seconds < 60:
        return "刚刚"
    elif seconds < 3600:
        return f"{seconds // 60} 分钟前"
    elif seconds < 86400:
        return f"{seconds // 3600} 小时前"
    elif seconds < 604800:
        return f"{seconds // 86400} 天前"
    else:
        return dt.strftime("%m-%d %H:%M")

# ── RSS 抓取 ─────────────────────────────────────────
def fetch_rss(url, timeout=15):
    """抓取 RSS 并返回 XML 根节点"""
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            return ElementTree.fromstring(resp.content)
        else:
            print(f"  ⚠️ HTTP {resp.status_code}: {url}")
            return None
    except Exception as e:
        print(f"  ⚠️ 请求失败: {e}")
        return None

def parse_rss_posts(root, source_tag):
    """解析 RSS XML 中的帖子列表"""
    posts = []
    if root is None:
        return posts

    for item in root.findall(".//item"):
        title_el = item.find("title")
        link_el = item.find("link")
        pub_el = item.find("pubDate")
        desc_el = item.find("description")
        cat_el = item.find("category")
        creator_el = item.find("dc:creator", NS)
        pinned_el = item.find("discourse:topicPinned", NS)
        guid_el = item.find("guid")

        title = title_el.text if title_el is not None else ""
        link = link_el.text.strip() if link_el is not None else ""
        pub_date = pub_el.text if pub_el is not None else ""
        desc_html = desc_el.text if desc_el is not None else ""
        category = cat_el.text if cat_el is not None else ""
        creator = creator_el.text if creator_el is not None else ""
        pinned = (pinned_el.text == "Yes") if pinned_el is not None else False
        guid = guid_el.text if guid_el is not None else link

        # 从链接提取帖子 ID
        topic_id = 0
        id_match = re.search(r"/(\d+)(?:$|/|\?)", link)
        if id_match:
            topic_id = int(id_match.group(1))

        # 纯文本摘要（前 150 字符）
        excerpt = strip_html(desc_html)[:150]

        posts.append({
            "id": topic_id,
            "title": title,
            "url": link,
            "pub_date": pub_date,
            "category": category,
            "author": creator,
            "excerpt": excerpt,
            "pinned": pinned,
            "source_tag": source_tag,
        })

    return posts

def fetch_all_posts(config):
    """抓取所有标签的 RSS，合并返回"""
    all_posts = []
    site = config["site"]

    # 按标签抓取
    for tag in config["tags"]:
        url = f"{site}/tag/{tag}.rss"
        print(f"  📥 {tag}")
        root = fetch_rss(url)
        posts = parse_rss_posts(root, tag)
        print(f"     → {len(posts)} 条")
        all_posts.extend(posts)
        time.sleep(config["request"]["delay_seconds"])

    # 抓取"前沿快讯"分类
    url = f"{site}/c/news/34.rss"
    print(f"  📥 前沿快讯")
    root = fetch_rss(url)
    posts = parse_rss_posts(root, "前沿快讯")
    print(f"     → {len(posts)} 条")
    all_posts.extend(posts)

    return all_posts

# ── 去重 ─────────────────────────────────────────────
def deduplicate(posts):
    seen = {}
    for p in posts:
        pid = p["id"]
        if pid <= 0:
            # 用 URL 做 fallback key
            pid = hash(p["url"])
        if pid in seen:
            existing = seen[pid]
            tag = p["source_tag"]
            if tag not in existing["_tags"]:
                existing["_tags"].append(tag)
        else:
            p["_tags"] = [p["source_tag"]]
            seen[pid] = p
    return list(seen.values())

# ── HTML 报告 ─────────────────────────────────────────
def generate_html(posts, config):
    tz_cn = timezone(timedelta(hours=8))
    now_cn = datetime.now(tz_cn).strftime("%Y-%m-%d %H:%M:%S")

    # 按时间排序
    posts.sort(key=lambda p: parse_rfc2822(p["pub_date"]), reverse=True)

    # 标签统计
    tag_stats = {}
    for p in posts:
        for tag in p.get("_tags", []):
            tag_stats[tag] = tag_stats.get(tag, 0) + 1

    # 帖子卡片
    cards = ""
    for p in posts:
        dt = parse_rfc2822(p["pub_date"])
        time_ago = format_time_ago(dt)
        time_str = dt.astimezone(tz_cn).strftime("%m-%d %H:%M") if dt.year > 2000 else ""
        tags_str = " · ".join(p["_tags"])
        pinned = ' <span class="badge pinned">📌 置顶</span>' if p["pinned"] else ""
        cat = f'<span class="meta-item">📂 {escape(p["category"])}</span>' if p["category"] else ""
        author = f'<span class="meta-item">👤 {escape(p["author"])}</span>' if p["author"] else ""
        excerpt_html = f'<div class="excerpt">{escape(p["excerpt"])}</div>' if p["excerpt"] else ""

        cards += f"""
        <div class="post-card" data-tags="{escape(','.join(p['_tags']))}" data-time="{dt.isoformat()}">
          <div class="post-header">
            <a href="{p['url']}" target="_blank" rel="noopener" class="post-title">{escape(p['title'])}</a>{pinned}
          </div>
          {excerpt_html}
          <div class="post-meta">
            <span class="meta-item">🏷️ {escape(tags_str)}</span>
            {cat}{author}
            <span class="meta-item">🕐 {time_ago} ({time_str})</span>
          </div>
        </div>"""

    # 标签统计条
    tags_bar = ""
    for tag, count in sorted(tag_stats.items(), key=lambda x: -x[1])[:12]:
        tags_bar += f'<div class="tag-stat"><span class="tag-name">{escape(tag)}</span><span class="tag-count">{count}</span></div>'

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Linux.do AI 动态监控</title>
<style>
:root {{
  --bg:#0d1117;--card:#161b22;--border:#30363d;--text:#e6edf3;
  --text2:#8b949e;--accent:#58a6ff;--tag-bg:#1f2937;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",sans-serif;line-height:1.6;padding:0 16px 40px;max-width:900px;margin:0 auto}}
.header{{padding:24px 0;border-bottom:1px solid var(--border);margin-bottom:20px}}
.header h1{{font-size:22px;font-weight:600;color:var(--accent);margin-bottom:4px}}
.header .subtitle{{color:var(--text2);font-size:13px}}
.stats{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}}
.stat-box{{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:12px 16px;min-width:120px}}
.stat-box .num{{font-size:24px;font-weight:700;color:var(--accent)}}
.stat-box .label{{font-size:12px;color:var(--text2)}}
.controls{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px;align-items:center}}
.controls input{{flex:1;min-width:200px;background:var(--card);border:1px solid var(--border);border-radius:6px;padding:8px 12px;color:var(--text);font-size:14px;outline:none}}
.controls input:focus{{border-color:var(--accent)}}
.controls select{{background:var(--card);border:1px solid var(--border);border-radius:6px;padding:8px 12px;color:var(--text);font-size:14px;outline:none;cursor:pointer}}
.tags-bar{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px}}
.tag-stat{{display:flex;align-items:center;gap:4px;background:var(--tag-bg);border-radius:12px;padding:4px 10px;font-size:12px}}
.tag-stat .tag-name{{color:var(--accent)}}
.tag-stat .tag-count{{color:var(--text2)}}
.post-card{{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:14px 16px;margin-bottom:10px;transition:border-color .2s}}
.post-card:hover{{border-color:var(--accent)}}
.post-header{{margin-bottom:4px}}
.post-title{{color:var(--text);text-decoration:none;font-size:15px;font-weight:500;line-height:1.5}}
.post-title:hover{{color:var(--accent);text-decoration:underline}}
.excerpt{{color:var(--text2);font-size:13px;margin:4px 0 6px;line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.post-meta{{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:var(--text2)}}
.meta-item{{white-space:nowrap}}
.badge{{display:inline-block;font-size:11px;padding:1px 6px;border-radius:4px;margin-left:6px}}
.badge.pinned{{background:#f0883e22;color:#f0883e}}
.footer{{margin-top:32px;padding-top:16px;border-top:1px solid var(--border);color:var(--text2);font-size:12px;text-align:center}}
@media(max-width:600px){{
  .stats{{flex-direction:column}}
  .controls{{flex-direction:column}}
  .post-meta{{font-size:11px;gap:8px}}
}}
</style>
</head>
<body>
<div class="header">
  <h1>Linux.do AI 动态监控</h1>
  <div class="subtitle">最后更新: {now_cn} (CST) · 数据来源: linux.do RSS · 共 {len(posts)} 条帖子</div>
</div>
<div class="stats">
  <div class="stat-box"><div class="num">{len(posts)}</div><div class="label">帖子总数</div></div>
  <div class="stat-box"><div class="num">{len(tag_stats)}</div><div class="label">覆盖标签</div></div>
  <div class="stat-box"><div class="num">{sum(1 for p in posts if p["pinned"])}</div><div class="label">置顶帖</div></div>
</div>
<div class="tags-bar">{tags_bar}</div>
<div class="controls">
  <input type="text" id="searchInput" placeholder="搜索标题、标签..." oninput="filterPosts()">
  <select id="sortSelect" onchange="sortPosts()">
    <option value="time">按时间排序</option>
    <option value="time-asc">最早发布</option>
  </select>
</div>
<div id="postsContainer">{cards}</div>
<div class="footer">由 linuxdo-ai-monitor 自动生成 · GitHub Actions 定时运行 · 数据归 linux.do 社区所有</div>
<script>
function filterPosts(){{
  const q=document.getElementById('searchInput').value.toLowerCase();
  document.querySelectorAll('.post-card').forEach(c=>{{
    const t=c.querySelector('.post-title').textContent.toLowerCase();
    const g=c.dataset.tags.toLowerCase();
    c.style.display=(t.includes(q)||g.includes(q))?'':'none';
  }});
}}
function sortPosts(){{
  const ct=document.getElementById('postsContainer');
  const s=document.getElementById('sortSelect').value;
  const cs=Array.from(ct.querySelectorAll('.post-card'));
  cs.sort((a,b)=>s==='time'?b.dataset.time.localeCompare(a.dataset.time):a.dataset.time.localeCompare(b.dataset.time));
  cs.forEach(c=>ct.appendChild(c));
}}
</script>
</body>
</html>"""

# ── 推送通知 ──────────────────────────────────────────
def push_bark(config, summary):
    bark = config.get("push", {}).get("bark", {})
    if not bark.get("enabled") or not bark.get("key"):
        return
    server = bark.get("server", "https://api.day.app")
    url = f"{server}/{bark['key']}/{requests.utils.quote('Linux.do AI 动态')}/{requests.utils.quote(summary[:800])}"
    try:
        resp = requests.get(url, timeout=10)
        print(f"  🍎 Bark 推送: {resp.status_code}")
    except Exception as e:
        print(f"  ⚠️ Bark 推送失败: {e}")

def push_feishu(config, summary):
    feishu = config.get("push", {}).get("feishu", {})
    if not feishu.get("enabled") or not feishu.get("webhook_url"):
        return
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": "Linux.do AI 动态"}, "template": "blue"},
            "elements": [{"tag": "markdown", "content": summary[:4000]}]
        }
    }
    try:
        resp = requests.post(feishu["webhook_url"], json=payload, timeout=10)
        print(f"  🐦 飞书推送: {resp.status_code}")
    except Exception as e:
        print(f"  ⚠️ 飞书推送失败: {e}")

# ── 主流程 ────────────────────────────────────────────
def main():
    print("=" * 50)
    print("  Linux.do AI 动态监控 (RSS)")
    print("=" * 50)

    config = load_config()

    # 1. 抓取
    print("\n📥 抓取 RSS...")
    all_posts = fetch_all_posts(config)
    print(f"\n   原始: {len(all_posts)} 条")

    # 2. 去重
    posts = deduplicate(all_posts)
    print(f"   去重后: {len(posts)} 条")

    if not posts:
        print("⚠️ 未获取到任何帖子")
        sys.exit(1)

    # 3. 生成 HTML
    print("\n📄 生成报告...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    html = generate_html(posts, config)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"   ✅ {OUTPUT_HTML}")

    # 4. 推送摘要（最新 5 条）
    posts.sort(key=lambda p: parse_rfc2822(p["pub_date"]), reverse=True)
    top5 = posts[:5]
    lines = []
    for i, p in enumerate(top5, 1):
        dt = parse_rfc2822(p["pub_date"])
        lines.append(f"{i}. {p['title']}\n   {format_time_ago(dt)} · {p['author']}")
    summary = f"共 {len(posts)} 条 AI 动态，最新 Top5:\n\n" + "\n\n".join(lines)

    print("\n📱 推送通知...")
    push_bark(config, summary)
    push_feishu(config, summary)

    print(f"\n✅ 完成！共 {len(posts)} 条帖子")

if __name__ == "__main__":
    main()
