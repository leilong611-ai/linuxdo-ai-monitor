"""Beehiiv Newsletter 数据源 - Ben's Bites, The Rundown AI"""

import re
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

from sources import BaseSource, register_source
from models import Post


@register_source
class BeehiivSource(BaseSource):
    source_id = "beehiiv"
    source_name = "Newsletter"
    source_type = "beehiiv"

    def __init__(self, source_config, global_config):
        super().__init__(source_config, global_config)
        self.source_id = source_config.get("id", "beehiiv")
        self.source_name = source_config.get("name", "Newsletter")

    def fetch(self):
        url = self.cfg.get("url", "")
        if not url:
            return []
        max_items = self.cfg.get("max_items", 10)

        print(f"    📥 {self.source_name}")
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

            excerpt = re.sub(r"<[^>]+>", "", desc)[:200]
            author = item.findtext("dc:creator", namespaces={"dc": "http://purl.org/dc/elements/1.1/"}) or ""

            post = Post(
                uid=f"{self.source_id}:{hash(link)}",
                title=title,
                url=link,
                source_id=self.source_id,
                source_name=self.source_name,
                sources=[self.source_id],
                published_at=self._parse_date(pub_date),
                engagement_score=30,  # Newsletter 是精选内容，给固定分
                raw_engagement={},
                excerpt=excerpt,
                author=author,
                tags=["Newsletter"],
                language="en",
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
