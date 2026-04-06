#!/usr/bin/env python3
"""
AI 分析器 V3 - 三层评论体系

通过 BigModel Anthropic 兼容接口调用 GLM-5.1：
  base_url: https://open.bigmodel.cn/api/anthropic
  model: glm-5.1

为每条新闻生成三层评论：
  1. brief_comment: 15-30字核心判断
  2. deep_comment: 100-200字深度观点
  3. industry_impact: 50-100字行业影响
  + rating 1-5, sentiment, action
"""

import json
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

try:
    import anthropic
except ImportError:
    anthropic = None

from database import init_db, upsert_posts, save_ai_comment, get_unanalyzed_posts, get_ai_comment

BASE_DIR = Path(__file__).resolve().parent

MAX_POSTS_PER_BATCH = 30
MODEL = "glm-5.1"
BASE_URL = "https://open.bigmodel.cn/api/anthropic"

TZ_CN = timezone(timedelta(hours=8))


def get_api_key():
    """获取 API Key：环境变量 > Keychain"""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "openclaw/ANTHROPIC_API_KEY", "-w"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def analyze_posts(posts):
    """对 Post 对象列表进行三层 AI 分析"""
    if anthropic is None:
        print("  ℹ️ anthropic 包未安装，跳过 AI 分析")
        return

    api_key = get_api_key()
    if not api_key:
        print("  ℹ️ API Key 未找到，跳过 AI 分析")
        return

    client = anthropic.Anthropic(
        api_key=api_key,
        base_url=BASE_URL,
    )

    # 按 engagement_score 排序，取 top N
    scored = sorted(posts, key=lambda p: getattr(p, 'engagement_score', 0), reverse=True)
    to_analyze = scored[:MAX_POSTS_PER_BATCH]

    if not to_analyze:
        return

    # 构建新闻列表
    items_text = ""
    for i, p in enumerate(to_analyze):
        title = getattr(p, 'title', '') or ''
        excerpt = getattr(p, 'excerpt', '') or getattr(p, 'summary', '') or ''
        source = getattr(p, 'sources', []) or []
        category = getattr(p, 'category', '')
        score = getattr(p, 'engagement_score', 0)
        author = getattr(p, 'author', '')

        items_text += f"\n[{i+1}] {title}\n"
        if excerpt:
            items_text += f"    摘要: {excerpt[:150]}\n"
        items_text += f"    来源: {', '.join(source[:3])} | 分类: {category} | 热度: {score}\n"
        if author:
            items_text += f"    作者: {author}\n"

    now = datetime.now(TZ_CN).strftime("%Y-%m-%d")

    prompt = f"""你是一位资深 AI 行业分析师，今天是 {now}。
请对以下从各渠道采集的 AI 行业动态进行专业三层分析。

对每条新闻评估：

1. **重要性** (1-5星):
   5 = 行业级重大突破/颠覆性发布
   4 = 重要更新，从业者必知
   3 = 有价值动态
   2 = 一般信息
   1 = 低价值/广告

2. **情绪** (positive/neutral/negative)

3. **操作建议** (act/watch/skip)

4. **短评** brief: 15-30字中文核心判断

5. **深度观点** deep: 100-200字中文深度分析，包括：
   - 事件本质解读
   - 对AI从业者/用户的直接影响
   - 与近期同类事件关联
   - 1-3个月趋势预判

6. **行业影响** impact: 50-100字中文，包括：
   - 受影响的产业链环节
   - 竞品动态对比

严格按以下 JSON 格式输出，不加任何其他文字:
[
  {{"i":1,"r":4,"s":"positive","a":"watch","b":"短评","d":"深度观点","p":"行业影响"}},
  ...
]

新闻列表:
{items_text}"""

    try:
        print(f"  🤖 GLM-5.1 三层分析中... ({len(to_analyze)} 条)")

        message = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text.strip()

        start = response_text.find("[")
        end = response_text.rfind("]") + 1
        if start < 0 or end <= start:
            print(f"  ⚠️ AI 返回格式异常")
            return

        analyses = json.loads(response_text[start:end])
        analysis_map = {a["i"]: a for a in analyses}

        count = 0
        for i, p in enumerate(to_analyze):
            a = analysis_map.get(i + 1)
            if a:
                p.ai_rating = a.get("r", 0)
                p.ai_sentiment = a.get("s", "neutral")
                p.ai_action = a.get("a", "skip")
                p.ai_comment = a.get("b", "")
                p.deep_comment = a.get("d", "")
                p.industry_impact = a.get("p", "")

                # 写入数据库
                save_ai_comment(
                    post_uid=p.uid,
                    rating=p.ai_rating,
                    sentiment=p.ai_sentiment,
                    action=p.ai_action,
                    brief_comment=p.ai_comment,
                    deep_comment=p.deep_comment,
                    industry_impact=p.industry_impact,
                )
                count += 1

        print(f"  ✅ AI 三层分析完成: {count} 条已评分入库")

    except Exception as e:
        print(f"  ⚠️ AI 分析失败: {e}")


def incremental_analyze():
    """增量分析：只处理数据库中未分析的帖子"""
    init_db()

    if anthropic is None:
        print("  ℹ️ anthropic 包未安装，跳过增量分析")
        return

    api_key = get_api_key()
    if not api_key:
        print("  ℹ️ API Key 未找到，跳过增量分析")
        return

    unanalyzed = get_unanalyzed_posts(limit=MAX_POSTS_PER_BATCH)
    if not unanalyzed:
        print("  ✅ 所有帖子已分析完毕")
        return

    print(f"  📋 待增量分析: {len(unanalyzed)} 条")

    # 转换为简单对象供 analyze_posts 使用
    class _Post:
        pass

    posts = []
    for r in unanalyzed:
        p = _Post()
        p.uid = r["uid"]
        p.title = r["title"]
        p.excerpt = r.get("excerpt", "")
        p.summary = r.get("summary", "")
        p.sources = json.loads(r.get("sources", "[]"))
        p.category = r.get("category", "")
        p.engagement_score = r.get("engagement_score", 0)
        p.author = r.get("author", "")
        p.ai_rating = 0
        p.ai_sentiment = "neutral"
        p.ai_comment = ""
        p.ai_action = "skip"
        p.deep_comment = ""
        p.industry_impact = ""
        posts.append(p)

    analyze_posts(posts)


def save_ai_to_api(posts):
    """将 AI 分析结果保存到 API 数据（兼容旧接口）"""
    api_path = BASE_DIR / "output" / "api" / "posts.json"
    if not api_path.exists():
        return

    try:
        with open(api_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return

    rating_map = {}
    for p in posts:
        uid = getattr(p, 'uid', '')
        if uid and getattr(p, 'ai_rating', 0):
            rating_map[uid] = {
                "ai_rating": p.ai_rating,
                "ai_sentiment": getattr(p, 'ai_sentiment', 'neutral'),
                "ai_comment": getattr(p, 'ai_comment', ''),
                "ai_action": getattr(p, 'ai_action', 'skip'),
                "deep_comment": getattr(p, 'deep_comment', ''),
                "industry_impact": getattr(p, 'industry_impact', ''),
            }

    for pd in data.get("posts", []):
        uid = pd.get("uid", "")
        if uid in rating_map:
            pd.update(rating_map[uid])

    data["ai_analyzed"] = True
    data["ai_analyzed_at"] = datetime.now(TZ_CN).isoformat()

    with open(api_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    if not Path("data/radar.db").exists():
        print("请先运行 monitor.py")
        sys.exit(1)

    incremental_analyze()
    print("✅ 增量分析完成")
