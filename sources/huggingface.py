"""HuggingFace 数据源 - Blog RSS"""

import re
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

from sources import BaseSource, register_source
from models import Post


@register_source
class HuggingFaceSource(BaseSource):
    source_id = "huggingface"
    source_name = "HuggingFace"
    source_type = "huggingface"

    def fetch(self):
        url = self.cfg.get("url", "https://huggingface.co/blog/feed.xml")
        max_items = self.cfg.get("max_items", 10)

        print(f"    📥 HuggingFace")
        root = self._fetch_xml(url)
        if root is None:
            print(f"       → 0 条")
            return []

        posts = []
        # HuggingFace 使用 Atom 格式
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        entries = root.findall(".//atom:entry", ns)
        if not entries:
            entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        # 也尝试 RSS 格式
        if not entries:
            entries = root.findall(".//item")

        for entry in entries:
            title = ""
            title_el = entry.find("atom:title", ns)
            if title_el is None:
                title_el = entry.find("{http://www.w3.org/2005/Atom}title")
            if title_el is None:
                title_el = entry.find("title")
            if title_el is not None:
                title = (title_el.text or "").strip()

            link = ""
            link_el = entry.find("atom:link[@rel='alternate']", ns)
            if link_el is None:
                link_el = entry.find("{http://www.w3.org/2005/Atom}link")
            if link_el is None:
                link_el = entry.find("link")
            if link_el is not None:
                link = link_el.get("href", "") or link_el.text or ""

            pub_date = ""
            updated_el = entry.find("atom:updated", ns)
            if updated_el is None:
                updated_el = entry.find("{http://www.w3.org/2005/Atom}updated")
            if updated_el is None:
                updated_el = entry.find("pubDate")
            if updated_el is not None:
                pub_date = updated_el.text or ""

            desc = ""
            summary_el = entry.find("atom:summary", ns)
            if summary_el is None:
                summary_el = entry.find("{http://www.w3.org/2005/Atom}summary")
            if summary_el is None:
                summary_el = entry.find("description")
            if summary_el is not None:
                desc = summary_el.text or ""

            excerpt = re.sub(r"<[^>]+>", "", desc)[:200]

            post = Post(
                uid=f"huggingface:{hash(link)}",
                title=title,
                url=link,
                source_id="huggingface",
                source_name="HuggingFace",
                sources=["huggingface"],
                published_at=self._parse_date(pub_date),
                engagement_score=25,
                raw_engagement={},
                excerpt=excerpt,
                author="HuggingFace",
                tags=["HuggingFace"],
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
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
        try:
            return parsedate_to_datetime(date_str)
        except (ValueError, TypeError):
            return datetime.min.replace(tzinfo=timezone.utc)
