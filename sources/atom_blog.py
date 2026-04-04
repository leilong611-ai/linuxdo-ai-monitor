"""Atom Blog 数据源 - Simon Willison 等"""

import re
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

from sources import BaseSource, register_source
from models import Post

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


@register_source
class AtomBlogSource(BaseSource):
    source_id = "atom_blog"
    source_name = "Blog"
    source_type = "atom"

    def __init__(self, source_config, global_config):
        super().__init__(source_config, global_config)
        self.source_id = source_config.get("id", "atom_blog")
        self.source_name = source_config.get("name", "Blog")

    def fetch(self):
        url = self.cfg.get("url", "")
        if not url:
            return []
        max_items = self.cfg.get("max_items", 10)
        filter_kw = [kw.lower() for kw in self.cfg.get("filter_keywords", [])]

        print(f"    📥 {self.source_name}")
        root = self._fetch_xml(url)
        if root is None:
            print(f"       → 0 条")
            return []

        posts = []
        # Atom feed 使用 <entry> 而非 <item>
        entries = root.findall(".//atom:entry", ATOM_NS)
        if not entries:
            entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")

        for entry in entries:
            title = ""
            title_el = entry.find("atom:title", ATOM_NS)
            if title_el is None:
                title_el = entry.find("{http://www.w3.org/2005/Atom}title")
            if title_el is not None:
                title = (title_el.text or "").strip()

            link = ""
            link_el = entry.find("atom:link[@rel='alternate']", ATOM_NS)
            if link_el is None:
                link_el = entry.find("{http://www.w3.org/2005/Atom}link[@rel='alternate']")
            if link_el is None:
                link_el = entry.find("atom:link", ATOM_NS)
                if link_el is None:
                    link_el = entry.find("{http://www.w3.org/2005/Atom}link")
            if link_el is not None:
                link = link_el.get("href", "")

            # 发布时间
            published = ""
            updated_el = entry.find("atom:updated", ATOM_NS)
            if updated_el is None:
                updated_el = entry.find("{http://www.w3.org/2005/Atom}updated")
            if updated_el is not None:
                published = updated_el.text or ""

            # 内容/摘要
            content = ""
            summary_el = entry.find("atom:summary", ATOM_NS)
            if summary_el is None:
                summary_el = entry.find("{http://www.w3.org/2005/Atom}summary")
            if summary_el is None:
                summary_el = entry.find("atom:content", ATOM_NS)
                if summary_el is None:
                    summary_el = entry.find("{http://www.w3.org/2005/Atom}content")
            if summary_el is not None:
                content = summary_el.text or ""

            excerpt = re.sub(r"<[^>]+>", "", content)[:200]

            # 过滤关键词
            if filter_kw:
                combined = f"{title} {excerpt}".lower()
                if not any(kw in combined for kw in filter_kw):
                    continue

            has_chinese = bool(re.search(r"[\u4e00-\u9fff]", title + excerpt))

            post = Post(
                uid=f"{self.source_id}:{hash(link)}",
                title=title,
                url=link,
                source_id=self.source_id,
                source_name=self.source_name,
                sources=[self.source_id],
                published_at=self._parse_iso(published),
                engagement_score=20,  # 博客内容，固定分
                raw_engagement={},
                excerpt=excerpt,
                author=self.source_name,
                tags=["Blog"],
                language="en" if not has_chinese else "mixed",
            )
            posts.append(post)
            if len(posts) >= max_items:
                break

        print(f"       → {len(posts)} 条")
        return posts

    def _parse_iso(self, date_str):
        if not date_str:
            return datetime.min.replace(tzinfo=timezone.utc)
        try:
            # ISO 8601 格式
            date_str = date_str.rstrip("Z") + "+00:00" if date_str.endswith("Z") else date_str
            return datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            return datetime.min.replace(tzinfo=timezone.utc)
