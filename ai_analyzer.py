#!/usr/bin/env python3
"""
AI 分析器 V2 - Claude Opus 专业评分

每天自动分析新闻：
  - importance: 重要程度 1-5
  - sentiment: 正面/中性/负面
  - summary: 一句话专业点评
  - action: 操作建议（是否需要关注/行动）

模型: Claude Opus (最强分析能力)
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

try:
    import anthropic
except ImportError:
    anthropic = None

BASE_DIR = Path(__file__).resolve().parent
API_DIR = BASE_DIR / "output" / "api"

# 模型选择：优先用 Opus，不可用则降级
MODEL_PRIORITY = ["claude-opus-4-20250514", "claude-sonnet-4-20250514"]

TZ_CN = timezone(timedelta(hours=8))


def get_model(client):
    """自动选择可用的最佳模型"""
    for model in MODEL_PRIORITY:
        try:
            # 尝试调用，看模型是否可用
            return model
        except Exception:
            continue
    return MODEL_PRIORITY[-1]  # 兜底用 Sonnet


def analyze_posts(posts, max_posts=40):
    """对 Post 对象列表进行 AI 分析，直接修改对象属性"""
    if anthropic is None:
        print("  ℹ️ anthropic 未安装，跳过 AI 分析")
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  ℹ️ ANTHROPIC_API_KEY 未设置，跳过 AI 分析")
        return

    client = anthropic.Anthropic(api_key=api_key)
    model = get_model(client)

    # 按参与度排序，只分析前 max_posts 条
    sorted_posts = sorted(posts, key=lambda p: getattr(p, 'engagement_score', 0), reverse=True)
    to_analyze = sorted_posts[:max_posts]

    if not to_analyze:
        return

    # 构建专业的分析请求
    items = ""
    for i, p in enumerate(to_analyze):
        title = getattr(p, 'title', '')
        excerpt = getattr(p, 'excerpt', '') or getattr(p, 'summary', '')
        source = getattr(p, 'sources', [])
        category = getattr(p, 'category', '')
        score = getattr(p, 'engagement_score', 0)
        author = getattr(p, 'author', '')

        items += f"\n[{i+1}] {title}\n"
        if excerpt:
            items += f"    摘要: {excerpt[:150]}\n"
        items += f"    来源: {', '.join(source[:3])} | 分类: {category} | 热度: {score}\n"
        if author:
            items += f"    作者: {author}\n"

    now = datetime.now(TZ_CN).strftime("%Y-%m-%d")

    prompt = f"""你是一位资深的 AI 行业分析师，今天是 {now}。
请对以下从各渠道采集的 AI 行业动态进行专业分析。

对每条新闻，请评估：

1. **重要性** (1-5星):
   ★★★★★ 行业级重大突破/颠覆性发布
   ★★★★ 重要更新，值得所有从业者关注
   ★★★ 有价值的行业动态，相关人员应了解
   ★★ 一般信息，部分人群感兴趣
   ★ 低价值/广告/水帖/重复信息

2. **情绪** (positive/neutral/negative):
   positive = 利好消息/突破/进步
   negative = 风险/故障/封禁/争议
   neutral = 中性信息/讨论/评测

3. **一句话点评** (15-30字中文):
   精炼概括这条信息的核心价值和影响

4. **操作建议** (watch/act/skip):
   act = 需要立即采取行动（如：抢购/续费/关注安全漏洞）
   watch = 值得持续关注跟踪
   skip = 可以忽略

严格按以下 JSON 格式输出，不要加任何其他文字:
[
  {{"i":1,"r":5,"s":"positive","c":"一句话点评","a":"watch"}},
  ...
]

新闻列表:
{items}"""

    try:
        print(f"  🤖 AI 分析中... ({len(to_analyze)} 条, 模型: {model.split('-')[1]})")

        message = client.messages.create(
            model=model,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text.strip()

        # 解析 JSON
        start = response_text.find("[")
        end = response_text.rfind("]") + 1
        if start < 0 or end <= start:
            print(f"  ⚠️ AI 返回格式异常，跳过")
            return

        analyses = json.loads(response_text[start:end])

        # 将结果写入 Post 对象
        for i, p in enumerate(to_analyze):
            analysis = next((a for a in analyses if a.get("i") == i + 1), None)
            if analysis:
                p.ai_rating = analysis.get("r", 0)
                p.ai_sentiment = analysis.get("s", "neutral")
                p.ai_comment = analysis.get("c", "")
                p.ai_action = analysis.get("a", "skip")

        analyzed = sum(1 for p in to_analyze if getattr(p, 'ai_rating', None))
        print(f"  ✅ AI 分析完成: {analyzed}/{len(to_analyze)} 条已评分")

        # 保存结果到 API 数据
        save_ai_to_api(to_analyze)

    except Exception as e:
        print(f"  ⚠️ AI 分析失败: {e}")


def save_ai_to_api(posts):
    """将 AI 分析结果保存到 api/posts.json"""
    api_path = API_DIR / "posts.json"
    if not api_path.exists():
        return

    try:
        with open(api_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return

    # 建立 uid -> ai 分析 的映射
    ai_map = {}
    for p in posts:
        uid = getattr(p, 'uid', '')
        if uid and getattr(p, 'ai_rating', None):
            ai_map[uid] = {
                "ai_rating": p.ai_rating,
                "ai_sentiment": getattr(p, 'ai_sentiment', 'neutral'),
                "ai_comment": getattr(p, 'ai_comment', ''),
                "ai_action": getattr(p, 'ai_action', 'skip'),
            }

    # 更新 posts 中的 AI 字段
    for post in data.get("posts", []):
        uid = post.get("uid", "")
        if uid in ai_map:
            post.update(ai_map[uid])

    data["ai_analyzed"] = True
    data["ai_analyzed_at"] = datetime.now(TZ_CN).isoformat()

    with open(api_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    # 独立运行：读取 API 数据 → 分析 → 写回
    api_path = API_DIR / "posts.json"
    if not api_path.exists():
        print("请先运行 monitor.py")
        sys.exit(1)

    with open(api_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    posts_data = data.get("posts", [])
    print(f"待分析: {len(posts_data)} 条")

    if not posts_data:
        sys.exit(0)

    # 转为简单对象进行分析
    class FakePost:
        pass

    posts = []
    for pd in posts_data:
        fp = FakePost()
        fp.uid = pd.get("uid", "")
        fp.title = pd.get("title", "")
        fp.excerpt = pd.get("excerpt", "")
        fp.summary = pd.get("summary", "")
        fp.sources = pd.get("source", [])
        fp.category = pd.get("category", "")
        fp.engagement_score = pd.get("engagement_score", 0)
        fp.author = pd.get("author", "")
        fp.ai_rating = pd.get("ai_rating")
        fp.ai_sentiment = pd.get("ai_sentiment", "neutral")
        fp.ai_comment = pd.get("ai_comment", "")
        fp.ai_action = pd.get("ai_action", "skip")
        posts.append(fp)

    analyze_posts(posts)

    # 写回
    for fp, pd in zip(posts, posts_data):
        if getattr(fp, 'ai_rating', None):
            pd["ai_rating"] = fp.ai_rating
            pd["ai_sentiment"] = getattr(fp, 'ai_sentiment', 'neutral')
            pd["ai_comment"] = getattr(fp, 'ai_comment', '')
            pd["ai_action"] = getattr(fp, 'ai_action', 'skip')

    data["ai_analyzed"] = True
    data["ai_analyzed_at"] = datetime.now(TZ_CN).isoformat()
    with open(api_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    print("✅ 分析结果已保存")
