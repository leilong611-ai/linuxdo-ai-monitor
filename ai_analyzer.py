"""
AI 分析器 - 调用 Claude API 对每日新闻进行评分和点评

使用方式:
  1. 设置环境变量 ANTHROPIC_API_KEY
  2. python ai_analyzer.py          # 读取 output/api/posts.json → 分析 → 写回
  3. 或在 monitor.py 中自动调用

AI 会为每条新闻添加:
  - ai_rating: 1-5 星（重要程度）
  - ai_comment: 一句话点评（中文）
"""

import json
import os
import sys
import time
from pathlib import Path

try:
    import anthropic
except ImportError:
    anthropic = None

BASE_DIR = Path(__file__).resolve().parent
API_DATA = BASE_DIR / "output" / "api" / "posts.json"
BRIEFING_DATA = BASE_DIR / "output" / "briefing.json"

MAX_POSTS_PER_BATCH = 30  # 每批分析条数
MODEL = "claude-sonnet-4-20250514"  # 使用较快的模型


def analyze_posts(posts):
    """调用 Claude API 批量分析新闻"""
    if anthropic is None:
        print("  ⚠️ anthropic 包未安装，跳过 AI 分析。运行: pip install anthropic")
        return posts

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  ℹ️ ANTHROPIC_API_KEY 未设置，跳过 AI 分析")
        return posts

    client = anthropic.Anthropic(api_key=api_key)

    # 取评分最高的前 N 条分析（避免 API 费用过高）
    scored = sorted(posts, key=lambda p: p.get("engagement_score", 0), reverse=True)
    to_analyze = scored[:MAX_POSTS_PER_BATCH]

    if not to_analyze:
        return posts

    # 构建分析请求
    items_text = ""
    for i, p in enumerate(to_analyze):
        items_text += f"\n[{i+1}] {p.get('title', '')}\n"
        items_text += f"  来源: {', '.join(p.get('source', []))}\n"
        items_text += f"  摘要: {p.get('excerpt', p.get('summary', ''))[:120]}\n"
        items_text += f"  分类: {p.get('category', '')} | 热度: {p.get('engagement_score', 0)}\n"

    prompt = f"""你是一位资深 AI 行业分析师。请对以下 AI 新闻逐条评分和点评。

评分标准（1-5星）:
- 5星: 重大突破/重磅发布，影响整个行业
- 4星: 重要更新/值得深入关注
- 3星: 有价值的行业动态
- 2星: 一般信息，部分人可能感兴趣
- 1星: 低价值/广告/重复信息

请严格按以下 JSON 数组格式输出，不要加任何其他文字:
[
  {{"i": 1, "rating": 4, "comment": "一句话中文点评"}},
  ...
]

新闻列表:
{items_text}"""

    try:
        print(f"  🤖 AI 分析中... ({len(to_analyze)} 条)")
        message = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text.strip()

        # 解析 JSON 响应
        # 尝试提取 JSON 数组
        start = response_text.find("[")
        end = response_text.rfind("]") + 1
        if start >= 0 and end > start:
            analyses = json.loads(response_text[start:end])
        else:
            print(f"  ⚠️ AI 返回格式异常")
            return posts

        # 将分析结果合并回帖子
        analysis_map = {a["i"]: a for a in analyses}
        for i, p in enumerate(to_analyze):
            a = analysis_map.get(i + 1)
            if a:
                p["ai_rating"] = a.get("rating", 0)
                p["ai_comment"] = a.get("comment", "")

        print(f"  ✅ AI 分析完成: {len(analyses)} 条已评分")

    except Exception as e:
        print(f"  ⚠️ AI 分析失败: {e}")

    return posts


def run_analysis():
    """独立运行: 读取 posts.json → 分析 → 写回"""
    data_path = API_DATA if API_DATA.exists() else BRIEFING_DATA
    if not data_path.exists():
        print("❌ 未找到数据文件，请先运行 monitor.py")
        sys.exit(1)

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    posts = data.get("posts", [])
    if not posts:
        # briefing.json 格式
        for section_posts in data.get("sections", {}).values():
            posts.extend(section_posts)

    if not posts:
        print("❌ 没有可分析的帖子")
        sys.exit(1)

    print(f"📊 待分析: {len(posts)} 条")
    posts = analyze_posts(posts)

    # 写回 posts.json
    API_DATA.parent.mkdir(parents=True, exist_ok=True)
    data["posts"] = posts
    data["ai_analyzed"] = True
    with open(API_DATA, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    # 也更新 briefing.json（给报告渲染用）
    if BRIEFING_DATA.exists():
        with open(BRIEFING_DATA, "r", encoding="utf-8") as f:
            briefing = json.load(f)
        # 将 AI 评分写入 sections
        rating_map = {p.get("uid"): p for p in posts if p.get("ai_rating")}
        for section_posts in briefing.get("sections", {}).values():
            for p in section_posts:
                uid = p.get("uid", "")
                if uid in rating_map:
                    p["ai_rating"] = rating_map[uid].get("ai_rating")
                    p["ai_comment"] = rating_map[uid].get("ai_comment", "")
        with open(BRIEFING_DATA, "w", encoding="utf-8") as f:
            json.dump(briefing, f, ensure_ascii=False, indent=2, default=str)

    print("✅ AI 分析结果已保存")


if __name__ == "__main__":
    run_analysis()
