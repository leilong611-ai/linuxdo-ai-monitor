"""统一数据模型 - V3 多源 AI 情报雷达"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Post:
    """跨源统一的帖子数据类"""
    # 身份
    uid: str                        # 全局唯一 ID: "{source_id}:{local_id}"
    title: str
    url: str
    summary: str = ""               # 一句话摘要

    # 来源归属
    source_id: str = ""             # "linuxdo", "hackernews", "reddit_claudeai"
    source_name: str = ""           # 显示名 "Linux.do", "Hacker News"
    sources: list = field(default_factory=list)  # 去重后的多源归属

    # 时间
    published_at: datetime = field(default_factory=lambda: datetime.min)
    fetched_at: datetime = field(default_factory=datetime.now)

    # 参与度（归一化 0-100）
    engagement_score: int = 0
    raw_engagement: dict = field(default_factory=dict)  # 源特有指标

    # 分类
    category: str = "trending"      # claude|openai|gemini|xai|cn_llm|ai_tools|forum_tips|trending
    is_claude: bool = False
    is_alert: bool = False
    is_new: bool = False

    # 内容
    excerpt: str = ""               # 纯文本摘录，最多 200 字符
    author: str = ""
    tags: list = field(default_factory=list)
    language: str = "zh"            # zh | en | mixed

    def to_dict(self):
        return {
            "uid": self.uid,
            "title": self.title,
            "url": self.url,
            "summary": self.summary,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "sources": self.sources,
            "published_at": self.published_at.isoformat() if self.published_at else "",
            "engagement_score": self.engagement_score,
            "category": self.category,
            "is_claude": self.is_claude,
            "is_alert": self.is_alert,
            "is_new": self.is_new,
            "excerpt": self.excerpt,
            "author": self.author,
            "tags": self.tags,
            "language": self.language,
        }


@dataclass
class SourceStatus:
    """数据源抓取状态"""
    source_id: str
    source_name: str
    success: bool = False
    post_count: int = 0
    error: str = ""


@dataclass
class Briefing:
    """每日简报"""
    date: str = ""
    total: int = 0
    sections: dict = field(default_factory=dict)  # category -> [Post]
    source_statuses: list = field(default_factory=list)  # [SourceStatus]
    all_posts: list = field(default_factory=list)

    def to_dict(self):
        return {
            "date": self.date,
            "total": self.total,
            "sections": {
                k: [p.to_dict() for p in v] for k, v in self.sections.items()
            },
            "source_statuses": [
                {"id": s.source_id, "name": s.source_name,
                 "success": s.success, "count": s.post_count, "error": s.error}
                for s in self.source_statuses
            ],
        }
