"""arXiv 数据源 - cs.AI RSS"""

import re
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

from sources import BaseSource, register_source
from models import Post


@register_source
class ArxivSource(BaseSource):
    source_id = "arxiv"
    source_name = "arXiv"
    source_type = "arxiv"

    def __init__(self, source_config, global_config):
        super().__init__(source_config, global_config)
        self.source_id = source_config.get("id", "arxiv")
        self.source_name = source_config.get("name", "arXiv")

    def fetch(self):
        url = self.cfg.get("url", "https://arxiv.org/rss/cs.AI")
        max_items = self.cfg.get("max_items", 20)

        print(f"    📥 {self.source_name}")
        root = self._fetch_xml(url)
        if root is None:
            print(f"       → 0 条")
            return []

        posts = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = item.findtext("pubDate") or item.findtext("dc:date", namespaces={"dc": "http://purl.org/dc/elements/1.1/"}) or ""
            desc = (item.findtext("description") or "").strip()

            # arXiv 标题格式: "Title. Authors" — 去掉作者部分
            if "\n" in title:
                title = title.split("\n")[0].strip()

            # 清理 HTML 描述
            excerpt = re.sub(r"<[^>]+>", "", desc)[:200]
            # arXiv 描述通常包含 "Abstract: ..."
            abs_match = re.search(r"Abstract:\s*(.+)", excerpt, re.IGNORECASE)
            if abs_match:
                excerpt = abs_match.group(1)[:200]

            post = Post(
                uid=f"{self.source_id}:{hash(link)}",
                title=title,
                url=link,
                source_id=self.source_id,
                source_name=self.source_name,
                sources=[self.source_id],
                published_at=self._parse_date(pub_date),
                engagement_score=15,  # 学术论文，固定分
                raw_engagement={},
                excerpt=excerpt,
                author="",
                tags=["cs.AI", "Paper"],
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
            pass
        # 尝试 ISO 格式
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return datetime.min.replace(tzinfo=timezone.utc)
