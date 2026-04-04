"""Linux.do 数据源 - Discourse RSS 抓取"""

import re
import time
from html import unescape
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

from sources import BaseSource, register_source
from models import Post

NS = {"dc": "http://purl.org/dc/elements/1.1/", "discourse": "http://www.discourse.org/"}


def strip_html(html_str):
    text = re.sub(r"<[^>]+>", "", html_str)
    return unescape(re.sub(r"\s+", " ", text).strip())


def parse_rfc2822(t_str):
    if not t_str:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return parsedate_to_datetime(t_str)
    except (ValueError, TypeError):
        return datetime.min.replace(tzinfo=timezone.utc)


def extract_engagement(desc_html):
    m = re.search(r"(\d+)\s*个帖子\s*-\s*(\d+)\s*位参与者", desc_html)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 1, 1


@register_source
class LinuxdoSource(BaseSource):
    source_id = "linuxdo"
    source_name = "Linux.do"

    def fetch(self):
        site = self.cfg.get("site", "https://linux.do")
        tags = self.cfg.get("tags", [])
        max_items = self.cfg.get("max_items", 20)
        all_posts = []

        # 优先抓取 Claude 相关标签
        claude_tags = ["Claude", "人工智能"]
        for tag in claude_tags:
            if tag in tags:
                posts = self._fetch_tag(site, tag, max_items)
                all_posts.extend(posts)
                time.sleep(self.delay)

        # 其他标签
        for tag in tags:
            if tag not in claude_tags:
                posts = self._fetch_tag(site, tag, max_items)
                all_posts.extend(posts)
                time.sleep(self.delay)

        # 额外分类
        for cat_slug in self.cfg.get("extra_categories", []):
            url = f"{site}/c/news/34.rss" if cat_slug == "前沿快讯" else f"{site}/c/{cat_slug}.rss"
            print(f"    📥 {cat_slug}")
            posts = self._fetch_url(url, cat_slug)
            print(f"       → {len(posts)} 条")
            all_posts.extend(posts)

        return all_posts

    def _fetch_tag(self, site, tag, max_items):
        url = f"{site}/tag/{tag}.rss"
        print(f"    📥 {tag}")
        posts = self._fetch_url(url, tag)
        print(f"       → {len(posts)} 条")
        return posts

    def _fetch_url(self, url, source_tag):
        root = self._fetch_xml(url)
        if root is None:
            return []

        posts = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = item.findtext("pubDate") or ""
            desc_html = item.findtext("description") or ""
            category = item.findtext("category") or ""
            author = item.findtext("dc:creator", namespaces=NS) or ""

            pinned_el = item.find("discourse:topicPinned", NS)
            pinned = (pinned_el.text == "Yes") if pinned_el is not None else False

            # 提取 topic_id
            topic_id = 0
            m = re.search(r"/(\d+)(?:$|/|\?)", link)
            if m:
                topic_id = int(m.group(1))

            excerpt = strip_html(desc_html)[:200]
            reply_count, participant_count = extract_engagement(desc_html)

            # 计算参与度（归一化到 0-100）
            raw_score = reply_count * 2 + participant_count * 3
            engagement = min(100, raw_score)

            # 检测语言
            has_chinese = bool(re.search(r"[\u4e00-\u9fff]", title + excerpt))
            language = "zh" if has_chinese else "en"

            post = Post(
                uid=f"linuxdo:{topic_id}" if topic_id else f"linuxdo:{hash(link)}",
                title=title,
                url=link,
                source_id="linuxdo",
                source_name="Linux.do",
                sources=["linuxdo"],
                published_at=parse_rfc2822(pub_date),
                engagement_score=engagement,
                raw_engagement={"replies": reply_count, "participants": participant_count},
                excerpt=excerpt,
                author=author,
                tags=[source_tag],
                language=language,
            )
            posts.append(post)

        return posts
