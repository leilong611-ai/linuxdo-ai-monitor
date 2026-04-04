"""V2EX 数据源 - JSON API"""

import re
from datetime import datetime, timezone, timedelta

from sources import BaseSource, register_source
from models import Post

TZ_CN = timezone(timedelta(hours=8))


@register_source
class V2EXSource(BaseSource):
    source_id = "v2ex"
    source_name = "V2EX"

    def fetch(self):
        url = self.cfg.get("url", "https://www.v2ex.com/api/topics/hot.json")
        filter_kw = [kw.lower() for kw in self.cfg.get("filter_keywords", [])]
        max_items = self.cfg.get("max_items", 15)

        print(f"    📥 V2EX")
        data = self._fetch_json(url)
        if not data:
            print(f"       → 0 条")
            return []

        posts = []
        for topic in data:
            title = topic.get("title", "")
            content = topic.get("content", "")
            url = topic.get("url", "")
            member = topic.get("member", {})
            node = topic.get("node", {})
            replies = topic.get("replies", 0)
            created = topic.get("created", 0)

            # 过滤 AI 相关
            combined = f"{title} {content}".lower()
            if filter_kw and not any(kw in combined for kw in filter_kw):
                continue

            excerpt = re.sub(r"<[^>]+>", "", content)[:200]
            author = member.get("username", "")
            node_name = node.get("name", "")
            engagement = min(100, replies * 2)

            has_chinese = bool(re.search(r"[\u4e00-\u9fff]", title + excerpt))

            post = Post(
                uid=f"v2ex:{topic.get('id', hash(url))}",
                title=title,
                url=url,
                source_id="v2ex",
                source_name="V2EX",
                sources=["v2ex"],
                published_at=datetime.fromtimestamp(created, tz=timezone.utc) if created else datetime.min.replace(tzinfo=timezone.utc),
                engagement_score=engagement,
                raw_engagement={"replies": replies},
                excerpt=excerpt,
                author=author,
                tags=[node_name] if node_name else ["V2EX"],
                language="zh" if has_chinese else "en",
            )
            posts.append(post)
            if len(posts) >= max_items:
                break

        print(f"       → {len(posts)} 条")
        return posts
