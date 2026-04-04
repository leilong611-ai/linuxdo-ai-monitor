"""Reddit 数据源 - 子版块 RSS"""

import re
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

from sources import BaseSource, register_source
from models import Post

NS = {"dc": "http://purl.org/dc/elements/1.1/", "media": "http://search.yahoo.com/mrss/"}


@register_source
class RedditSource(BaseSource):
    source_id = "reddit"
    source_name = "Reddit"
    source_type = "reddit_rss"

    def __init__(self, source_config, global_config):
        super().__init__(source_config, global_config)
        # 从配置获取实际的 source_id 和 name
        self.source_id = source_config.get("id", "reddit")
        self.source_name = source_config.get("name", "Reddit")

    def fetch(self):
        url = self.cfg.get("url", "")
        if not url:
            return []
        max_items = self.cfg.get("max_items", 25)

        subreddit = self.cfg.get("subreddit", "")
        print(f"    📥 Reddit r/{subreddit}")

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

            # Reddit RSS 描述是 HTML
            excerpt = re.sub(r"<[^>]+>", "", desc)[:200]
            author = item.findtext("dc:creator", namespaces=NS) or ""
            if author.startswith("u/"):
                author = author[2:]

            has_chinese = bool(re.search(r"[\u4e00-\u9fff]", title + excerpt))

            post = Post(
                uid=f"{self.source_id}:{hash(link)}",
                title=title,
                url=link,
                source_id=self.source_id,
                source_name=self.source_name,
                sources=[self.source_id],
                published_at=self._parse_date(pub_date),
                engagement_score=10,  # Reddit RSS 无点赞数据，给基础分
                raw_engagement={},
                excerpt=excerpt,
                author=author,
                tags=[subreddit] if subreddit else ["Reddit"],
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
