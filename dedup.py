"""跨源去重 - URL 规范化 + 标题相似度"""

import re
from difflib import SequenceMatcher
from urllib.parse import urlparse, parse_qs, urlunparse


def normalize_url(url):
    """URL 规范化：去追踪参数、去尾斜杠、小写域名"""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        # 小写域名
        netloc = parsed.netloc.lower()
        # 去除 www 前缀
        if netloc.startswith("www."):
            netloc = netloc[4:]
        # 去除追踪参数
        clean_params = {}
        if parsed.query:
            for k, v in parse_qs(parsed.query).items():
                if not k.startswith("utm_") and k not in ("ref", "source", "from", "fbclid", "gclid"):
                    clean_params[k] = v[0]
        # 重建
        query = "&".join(f"{k}={v}" for k, v in clean_params.items()) if clean_params else ""
        path = parsed.path.rstrip("/")
        if not path:
            path = "/"
        return f"{parsed.scheme}://{netloc}{path}"
    except Exception:
        return url.lower().rstrip("/")


def normalize_title(title):
    """标题规范化：去标点、去来源前缀、小写"""
    t = title.lower().strip()
    # 去除常见来源前缀
    for prefix in ["[hacker news]", "[hn]", "(r/", "[reddit]", "[linux.do]", "[v2ex]"]:
        t = t.replace(prefix.lower(), "")
    # 去除标点
    t = re.sub(r"[^\w\s\u4e00-\u9fff]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def title_similarity(t1, t2):
    """计算标题相似度"""
    return SequenceMatcher(None, normalize_title(t1), normalize_title(t2)).ratio()


def merge_posts(posts):
    """合并重复帖子，保留最佳信息"""
    if not posts:
        return None
    # 以参与度最高的为主帖
    best = max(posts, key=lambda p: p.engagement_score)
    # 合并源归属
    all_sources = []
    for p in posts:
        for s in p.sources:
            if s not in all_sources:
                all_sources.append(s)
    best.sources = all_sources
    # 保留最长的 excerpt
    for p in posts:
        if len(p.excerpt) > len(best.excerpt):
            best.excerpt = p.excerpt
    # 保留最早发布时间
    for p in posts:
        if p.published_at and best.published_at and p.published_at < best.published_at:
            best.published_at = p.published_at
    # 合并标签
    all_tags = []
    for p in posts:
        for t in p.tags:
            if t not in all_tags:
                all_tags.append(t)
    best.tags = all_tags
    return best


def deduplicate(posts, title_threshold=0.75):
    """跨源去重"""
    if not posts:
        return posts

    # 第一轮：按规范化 URL 分组
    url_buckets = {}
    for p in posts:
        key = normalize_url(p.url)
        url_buckets.setdefault(key, []).append(p)

    # 已合并的帖子
    merged = []

    # URL 精确匹配的去重
    url_deduped = []
    for key, bucket in url_buckets.items():
        if len(bucket) > 1:
            merged_post = merge_posts(bucket)
            if merged_post:
                url_deduped.append(merged_post)
        else:
            url_deduped.append(bucket[0])

    # 第二轮：标题相似度匹配（仅对未合并的帖子）
    final = []
    used = set()

    for i, p1 in enumerate(url_deduped):
        if i in used:
            continue
        group = [p1]
        for j in range(i + 1, len(url_deduped)):
            if j in used:
                continue
            p2 = url_deduped[j]
            # 只对不同源的比较标题相似度
            if p1.source_id != p2.source_id:
                sim = title_similarity(p1.title, p2.title)
                if sim >= title_threshold:
                    group.append(p2)
                    used.add(j)

        if len(group) > 1:
            final.append(merge_posts(group))
        else:
            final.append(p1)
        used.add(i)

    return final
