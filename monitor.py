#!/usr/bin/env python3
"""
AI 情报雷达 V3 - 多源监控入口
"""

import sys

# 导入所有数据源模块（触发注册）
import sources.linuxdo
import sources.hackernews
import sources.reddit
import sources.v2ex
import sources.beehiiv
import sources.atom_blog
import sources.rss_base
import sources.arxiv
import sources.huggingface
import sources.juejin

from config import load_config
from sources import get_enabled_sources
from classifier import classify_all, CATEGORY_KEYWORDS
from dedup import deduplicate
from summary import extract_summary
from report import build_briefing, render_report
from models import SourceStatus
from database import init_db, upsert_posts, enrich_posts_from_db, get_db_stats


def main():
    print("=" * 50)
    print("  AI 情报雷达 V3")
    print("=" * 50)

    # 初始化数据库
    init_db()

    config = load_config()

    # 获取启用的数据源
    enabled = get_enabled_sources(config)
    print(f"\n📡 已启用 {len(enabled)} 个数据源")

    # 抓取所有源
    all_posts = []
    source_statuses = []

    for source in enabled:
        print(f"\n  [{source.source_name}]")
        try:
            posts = source.fetch()
            all_posts.extend(posts)
            source_statuses.append(SourceStatus(
                source_id=source.source_id,
                source_name=source.source_name,
                success=True,
                post_count=len(posts),
            ))
        except Exception as e:
            print(f"    ⚠️ 抓取失败: {e}")
            source_statuses.append(SourceStatus(
                source_id=source.source_id,
                source_name=source.source_name,
                success=False,
                post_count=0,
                error=str(e),
            ))

    print(f"\n📊 原始数据: {len(all_posts)} 条")

    # 跨源去重
    threshold = config.get("report", {}).get("dedup_title_threshold", 0.75)
    posts = deduplicate(all_posts, title_threshold=threshold)
    print(f"   去重后: {len(posts)} 条")

    # 分类
    posts = classify_all(posts)

    # 提取摘要
    for p in posts:
        p.summary = extract_summary(p.title, p.excerpt)

    # 写入数据库（增量更新）
    db_count = upsert_posts(posts)
    print(f"   💾 数据库: {db_count} 条写入")

    # AI 分析（如果设置了 API Key）
    print(f"\n🤖 AI 分析中...")
    try:
        from ai_analyzer import analyze_posts
        analyze_posts(posts)
    except Exception as e:
        print(f"  ⚠️ 跳过 AI 分析: {e}")

    # 从数据库回填 AI 评论（确保已分析帖子有数据）
    enrich_posts_from_db(posts)

    # 构建简报
    briefing = build_briefing(posts, source_statuses)

    # 统计
    cat_counts = {}
    for cat_id in CATEGORY_KEYWORDS:
        cat_counts[cat_id] = len([p for p in briefing.all_posts if p.category == cat_id])

    print(f"\n📋 分类统计:")
    for cat_id, count in cat_counts.items():
        if count > 0:
            info = CATEGORY_KEYWORDS[cat_id]
            print(f"   {info['emoji']} {info['label']}: {count} 条")

    # 渲染报告（含AI评分+存档）
    print(f"\n📄 生成报告...")
    render_report(briefing)

    # 飞书推送
    print(f"\n📱 推送飞书日报...")
    try:
        from feishu_push import push_daily_briefing
        push_daily_briefing(briefing)
    except Exception as e:
        print(f"  ⚠️ 飞书推送失败: {e}")

    # 数据库统计
    stats = get_db_stats()
    print(f"\n💾 数据库累计: {stats['total_posts']} 条帖子, {stats['analyzed_posts']} 条已分析")

    print(f"\n✅ 完成")


if __name__ == "__main__":
    main()
