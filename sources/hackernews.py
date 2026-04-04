"""Hacker News 数据源 - via hnrss.org"""

import re
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

from sources import BaseSource, register_source
from models import Post


@register_source
class HackerNewsSource(BaseSource):
    source_id = "hackernews"
    source_name = "Hacker News"

    def fetch(self):
        url = self.cfg.get("url", "https://hnrss.org/newest?q=AI&count=30")
        filter_kw = self.cfg.get("filter_keywords", [])
        max_items = self.cfg.get("max_items", 30)

        print(f"    📥 Hacker News")
        root = self._fetch_xml(url)
        if root is None:
            print(f"       → 0 条")
            return []

        posts = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = item.findtext("pubDate") or ""
            desc = (item.findtext("description") or "").strip()

            # 提取 HN 点赞数（hnrss.org 提供）
            points = 0
            comments_url = ""
            for child in item:
                tag = child.tag
                if "points" in tag.lower():
                    try:
                        points = int(child.text or "0")
                    except ValueError:
                        pass
                if child.text and "news.ycombinator.com" in (child.text or ""):
                    comments_url = child.text

            # 过滤非 AI 内容
            if filter_kw:
                combined = f"{title} {desc}".lower()
                if not any(kw.lower() in combined for kw in filter_kw):
                    continue

            excerpt = re.sub(r"<[^>]+>", "", desc)[:200]
            has_chinese = bool(re.search(r"[\u4e00-\u9fff]", title + excerpt))
            engagement = min(100, points // 10) if points else 0

            post = Post(
                uid=f"hn:{hash(link)}",
                title=title,
                url=link or comments_url,
                source_id="hackernews",
                source_name="Hacker News",
                sources=["hackernews"],
                published_at=self._parse_date(pub_date),
                engagement_score=engagement,
                raw_engagement={"points": points},
                excerpt=excerpt,
                author="",
                tags=["Hacker News"],
                language="en" if not has_chinese else "mixed",
            )
            posts.append(post)
            if len(posts) >= max_items:
                break

        print(f"       → {len(posts)} 条")
        return posts

    def _parse_date(self, date_str):
        if not date_str:
            return datetime.min.replace(tzinfo=timezone.utc)
        try:
            return parsedate_to_datetime(date_str)
        except (ValueError, TypeError):
            return datetime.min.replace(tzinfo=timezone.utc)
