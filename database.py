"""SQLite 底层数据库 - AI 情报雷达统一存储"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

from models import Post

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "radar.db"

TZ_CN = timezone(timedelta(hours=8))


def get_conn() -> sqlite3.Connection:
    """获取数据库连接"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS posts (
            uid TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT,
            summary TEXT,
            excerpt TEXT,
            source_id TEXT,
            source_name TEXT,
            sources TEXT DEFAULT '[]',
            category TEXT DEFAULT 'trending',
            published_at TEXT,
            fetched_at TEXT,
            engagement_score INTEGER DEFAULT 0,
            author TEXT,
            tags TEXT DEFAULT '[]',
            language TEXT DEFAULT 'zh',
            is_claude INTEGER DEFAULT 0,
            is_alert INTEGER DEFAULT 0,
            is_new INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ai_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_uid TEXT NOT NULL,
            rating INTEGER,
            sentiment TEXT DEFAULT 'neutral',
            action TEXT DEFAULT 'skip',
            brief_comment TEXT,
            deep_comment TEXT,
            industry_impact TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_uid) REFERENCES posts(uid),
            UNIQUE(post_uid)
        );

        CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category);
        CREATE INDEX IF NOT EXISTS idx_posts_published ON posts(published_at);
        CREATE INDEX IF NOT EXISTS idx_ai_sentiment ON ai_comments(sentiment);
    """)
    conn.commit()
    conn.close()
    print(f"   💾 数据库就绪: {DB_PATH}")


def upsert_posts(posts: list):
    """批量写入/更新帖子"""
    if not posts:
        return
    conn = get_conn()
    now = datetime.now(TZ_CN).isoformat()
    count = 0
    for p in posts:
        sources_json = json.dumps(p.sources if isinstance(p.sources, list) else [], ensure_ascii=False)
        tags_json = json.dumps(p.tags if isinstance(p.tags, list) else [], ensure_ascii=False)
        pub_at = p.published_at.isoformat() if p.published_at and p.published_at.year >= 2000 else ""

        try:
            conn.execute("""
                INSERT INTO posts (uid, title, url, summary, excerpt, source_id, source_name,
                    sources, category, published_at, fetched_at, engagement_score,
                    author, tags, language, is_claude, is_alert, is_new, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(uid) DO UPDATE SET
                    title=excluded.title,
                    summary=excluded.summary,
                    excerpt=excluded.excerpt,
                    category=excluded.category,
                    engagement_score=excluded.engagement_score,
                    sources=excluded.sources,
                    is_claude=excluded.is_claude,
                    is_alert=excluded.is_alert,
                    is_new=excluded.is_new
            """, (
                p.uid, p.title, p.url, p.summary or "", p.excerpt or "",
                p.source_id, p.source_name, sources_json, p.category,
                pub_at, now, p.engagement_score,
                p.author or "", tags_json, p.language,
                1 if p.is_claude else 0, 1 if p.is_alert else 0, 1 if p.is_new else 0,
                now
            ))
            count += 1
        except Exception as e:
            print(f"  ⚠️ DB写入失败 {p.uid}: {e}")
    conn.commit()
    conn.close()
    return count


def save_ai_comment(post_uid: str, rating: int, sentiment: str, action: str,
                    brief_comment: str = "", deep_comment: str = "",
                    industry_impact: str = ""):
    """保存单条 AI 评论"""
    conn = get_conn()
    now = datetime.now(TZ_CN).isoformat()
    conn.execute("""
        INSERT INTO ai_comments (post_uid, rating, sentiment, action,
            brief_comment, deep_comment, industry_impact, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(post_uid) DO UPDATE SET
            rating=excluded.rating,
            sentiment=excluded.sentiment,
            action=excluded.action,
            brief_comment=excluded.brief_comment,
            deep_comment=excluded.deep_comment,
            industry_impact=excluded.industry_impact,
            created_at=excluded.created_at
    """, (post_uid, rating, sentiment, action, brief_comment, deep_comment,
          industry_impact, now))
    conn.commit()
    conn.close()


def get_ai_comment(post_uid: str) -> Optional[dict]:
    """按 post uid 查询 AI 评论"""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM ai_comments WHERE post_uid = ?", (post_uid,)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def get_ai_comments_batch(post_uids: list) -> dict:
    """批量查询 AI 评论，返回 dict[uid -> comment_dict]"""
    if not post_uids:
        return {}
    conn = get_conn()
    placeholders = ",".join("?" * len(post_uids))
    rows = conn.execute(
        f"SELECT * FROM ai_comments WHERE post_uid IN ({placeholders})",
        post_uids
    ).fetchall()
    conn.close()
    return {row["post_uid"]: dict(row) for row in rows}


def get_unanalyzed_posts(limit: int = 50) -> list:
    """获取未分析帖子（增量分析用）"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT p.* FROM posts p
        LEFT JOIN ai_comments a ON p.uid = a.post_uid
        WHERE a.post_uid IS NULL
        ORDER BY p.engagement_score DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_posts(days: int = 2) -> list:
    """获取最近 N 天帖子（含 AI 评论）"""
    conn = get_conn()
    cutoff = (datetime.now(TZ_CN) - timedelta(days=days)).isoformat()
    rows = conn.execute("""
        SELECT p.*, a.rating as ai_rating, a.sentiment as ai_sentiment,
            a.action as ai_action, a.brief_comment as ai_comment,
            a.deep_comment, a.industry_impact
        FROM posts p
        LEFT JOIN ai_comments a ON p.uid = a.post_uid
        WHERE p.published_at >= ?
        ORDER BY p.engagement_score DESC
    """, (cutoff,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_db_stats() -> dict:
    """获取数据库统计"""
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    analyzed = conn.execute("SELECT COUNT(*) FROM ai_comments").fetchone()[0]
    cats = conn.execute("""
        SELECT category, COUNT(*) as cnt FROM posts GROUP BY category ORDER BY cnt DESC
    """).fetchall()
    conn.close()
    return {
        "total_posts": total,
        "analyzed_posts": analyzed,
        "categories": {r["category"]: r["cnt"] for r in cats}
    }


def export_api_json(days: int = 2) -> dict:
    """导出 API 格式 JSON（兼容现有接口）"""
    posts = get_recent_posts(days)
    now_str = datetime.now(TZ_CN).strftime("%Y-%m-%d")
    return {
        "date": now_str,
        "total": len(posts),
        "updated_at": datetime.now(TZ_CN).isoformat(),
        "api_version": 2,
        "description": "AI 情报雷达 - 每日新闻数据接口 v2",
        "posts": posts,
    }


def enrich_posts_from_db(posts: list):
    """从数据库加载 AI 评论到 Post 对象"""
    uids = [p.uid for p in posts if hasattr(p, 'uid')]
    if not uids:
        return
    comments = get_ai_comments_batch(uids)
    for p in posts:
        c = comments.get(p.uid)
        if c:
            p.ai_rating = c.get("rating")
            p.ai_sentiment = c.get("sentiment", "neutral")
            p.ai_comment = c.get("brief_comment", "")
            p.ai_action = c.get("action", "skip")
            p.deep_comment = c.get("deep_comment", "")
            p.industry_impact = c.get("industry_impact", "")
