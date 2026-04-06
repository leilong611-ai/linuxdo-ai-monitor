#!/usr/bin/env python3
"""AI 情报雷达 V4 - 交互式 Web 应用"""

import json
import os
import sys
import subprocess
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, jsonify
from database import (
    init_db, get_posts_with_interactions, get_user_comments, get_user_profile,
    save_user_comment, update_user_profile, save_ai_reply, get_ai_replies,
    get_conn, get_db_stats, get_all_user_comments
)

app = Flask(__name__, template_folder="templates", static_folder="output")
TZ_CN = timezone(timedelta(hours=8))


@app.route("/")
def index():
    """交互版报告首页"""
    mode = request.args.get("mode", "for_you")
    days = int(request.args.get("days", 2))
    posts = get_posts_with_interactions(days=days, mode=mode)
    profile = get_user_profile(limit=20)
    stats = get_db_stats()

    # 按板块分组
    categories_order = ["claude", "openai", "gemini", "xai", "cn_llm", "ai_tools", "forum_tips", "trending"]
    category_info = {
        "claude": {"label": "Claude 专区", "emoji": "🟠", "color": "#f59e0b"},
        "openai": {"label": "OpenAI / GPT", "emoji": "🟢", "color": "#10b981"},
        "gemini": {"label": "Gemini / Google", "emoji": "🔵", "color": "#3b82f6"},
        "xai": {"label": "xAI / Grok", "emoji": "🟣", "color": "#a78bfa"},
        "cn_llm": {"label": "国内大模型", "emoji": "🔴", "color": "#f87171"},
        "ai_tools": {"label": "AI 工具", "emoji": "🔧", "color": "#22d3ee"},
        "forum_tips": {"label": "论坛技巧 / 合租", "emoji": "💡", "color": "#fbbf24"},
        "trending": {"label": "突发热点 / 高赞", "emoji": "🔥", "color": "#f472b6"},
    }

    sections = {}
    for p in posts:
        cat = p.get("category", "trending")
        if cat not in sections:
            sections[cat] = []
        sections[cat].append(p)

    # 按分类排序
    ordered_sections = {}
    for cat_id in categories_order:
        if cat_id in sections:
            ordered_sections[cat_id] = sections[cat_id]

    now_str = datetime.now(TZ_CN).strftime("%Y-%m-%d %H:%M:%S")

    return render_template("interactive.html",
        report_title="AI 情报雷达",
        now_str=now_str,
        total=len(posts),
        mode=mode,
        profile=profile,
        stats=stats,
        categories=category_info,
        sections=ordered_sections,
        category_order=categories_order,
    )


@app.route("/api/posts")
def api_posts():
    """获取帖子列表"""
    mode = request.args.get("mode", "for_you")
    days = int(request.args.get("days", 2))
    posts = get_posts_with_interactions(days=days, mode=mode)
    return jsonify({"ok": True, "total": len(posts), "posts": posts})


@app.route("/api/comments/<uid>", methods=["GET"])
def api_get_comments(uid):
    """获取某帖子的用户评论"""
    comments = get_user_comments(uid)
    replies = get_ai_replies(uid)
    return jsonify({"ok": True, "comments": comments, "replies": replies})


@app.route("/api/comments", methods=["POST"])
def api_add_comment():
    """提交用户评论"""
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": "无数据"}), 400

    post_uid = data.get("post_uid", "")
    user_rating = int(data.get("user_rating", 0))
    user_comment = data.get("user_comment", "")
    user_tags = data.get("user_tags", "")
    stance = data.get("stance", "neutral")

    if not post_uid:
        return jsonify({"ok": False, "error": "缺少 post_uid"}), 400

    comment_id = save_user_comment(post_uid, user_rating, user_comment, user_tags, stance)

    # 更新用户画像
    if user_comment:
        # 简单分词：按空格和逗号拆分
        keywords = [w.strip() for w in user_comment.replace("，", ",").replace("、", ",").split(",") if len(w.strip()) >= 2]
        if user_tags:
            keywords.extend([t.strip() for t in user_tags.split(",") if t.strip()])
        if keywords:
            update_user_profile(keywords, stance)

    # 触发 AI 回应（后台线程，不阻塞响应）
    if user_comment:
        import threading
        t = threading.Thread(target=_async_ai_reply, args=(post_uid, comment_id, user_comment, stance), daemon=True)
        t.start()

    return jsonify({
        "ok": True,
        "comment_id": comment_id,
    })


@app.route("/api/profile")
def api_profile():
    """获取用户画像"""
    profile = get_user_profile(limit=50)
    recent_comments = get_all_user_comments(days=7)
    return jsonify({
        "ok": True,
        "profile": profile,
        "recent_comments_count": len(recent_comments),
    })


def _async_ai_reply(post_uid: str, comment_id: int, user_comment: str, stance: str):
    """后台线程：生成 AI 回应"""
    try:
        import anthropic
        stance_map = {"agree": "赞同", "disagree": "反对", "neutral": "中立"}
        stance_text = stance_map.get(stance, "中立")

        conn = get_conn()
        row = conn.execute("SELECT title, excerpt FROM posts WHERE uid = ?", (post_uid,)).fetchone()
        conn.close()
        if not row:
            return

        title = row["title"]
        excerpt = row["excerpt"] or ""
        prompt = f"你是AI情报分析师。用户对新闻「{title}」摘要「{excerpt[:100]}」发表了{stance_text}立场观点：「{user_comment}」。请简短回应（50-100字），直接输出回应文字。"

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            try:
                r = subprocess.run(
                    ["security", "find-generic-password", "-s", "openclaw/ANTHROPIC_API_KEY", "-w"],
                    capture_output=True, text=True, timeout=5
                )
                if r.returncode == 0:
                    api_key = r.stdout.strip()
            except Exception:
                pass

        if not api_key:
            print("  AI 回应跳过: 无 API Key", flush=True)
            return

        client = anthropic.Anthropic(api_key=api_key, base_url="https://open.bigmodel.cn/api/anthropic")
        msg = client.messages.create(
            model="glm-5.1",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
            timeout=30,
        )
        reply = msg.content[0].text.strip()
        if reply:
            save_ai_reply(post_uid, comment_id, reply)
            print(f"  AI 回应已保存: {post_uid} ({len(reply)}字)", flush=True)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  AI 回应异常: {e}", flush=True)


@app.route("/api/reply/<uid>/<int:comment_id>")
def api_check_reply(uid, comment_id):
    """轮询 AI 回应是否就绪"""
    replies = get_ai_replies(uid)
    for r in replies:
        if r.get("comment_id") == comment_id:
            return jsonify({"ok": True, "ready": True, "reply": r.get("reply_text", "")})
    return jsonify({"ok": True, "ready": False, "reply": ""})


if __name__ == "__main__":
    init_db()
    print("🌐 AI 情报雷达交互版启动")
    print("   本地访问: http://localhost:5001")
    app.run(host="0.0.0.0", port=5001, debug=False)
