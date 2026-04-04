"""掘金数据源 - via RSSHub"""

import re
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

from sources import BaseSource, register_source
from models import Post


@register_source
class JuejinSource(BaseSource):
    source_id = "juejin"
    source_name = "掘金"

    def fetch(self):
        url = self.cfg.get("url", "https://rsshub.app/juejin/tag/AI")
        max_items = self.cfg.get("max_items", 15)
        filter_kw = [kw.lower() for kw in self.cfg.get("filter_keywords", [])]

        print(f"    📥 掘金 AI")
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
            author = item.findtext("dc:creator", namespaces={"dc": "http://purl.org/dc/elements/1.1/"}) or ""

            excerpt = re.sub(r"<[^>]+>", "", desc)[:200]

            if filter_kw:
                combined = f"{title} {excerpt}".lower()
                if not any(kw in combined for kw in filter_kw):
                    continue

            has_chinese = bool(re.search(r"[\u4e00-\u9fff]", title + excerpt))

            post = Post(
                uid=f"juejin:{hash(link)}",
                title=title,
                url=link,
                source_id="juejin",
                source_name="掘金",
                sources=["juejin"],
                published_at=self._parse_date(pub_date),
                engagement_score=15,
                raw_engagement={},
                excerpt=excerpt,
                author=author,
                tags=["掘金", "AI"],
                language="zh" if has_chinese else "en",
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
