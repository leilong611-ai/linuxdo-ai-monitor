"""8 大板块分类器 - V3 AI 情报雷达"""

CATEGORY_KEYWORDS = {
    "claude": {
        "keywords": [
            "claude", "opus", "sonnet", "haiku", "anthropic", "claude code",
            "claude pro", "claude max", "claude team", "claude api",
            "openclaw", "clawcode", "computer use",
        ],
        "priority": 0,
        "color": "#d97706",
        "emoji": "🟠",
        "label": "Claude 专区",
    },
    "openai": {
        "keywords": [
            "openai", "chatgpt", "gpt-4", "gpt-5", "gpt5", "gpt4",
            "codex", "sora", "dall-e", "dalle", "o1", "o3", "o4",
            "whisper", "openai api", "gpt-4o", "chatgpt pro",
        ],
        "priority": 1,
        "color": "#10a37f",
        "emoji": "🟢",
        "label": "OpenAI / GPT",
    },
    "gemini": {
        "keywords": [
            "gemini", "google ai", "bard", "deepmind", "google ai studio",
            "gemini pro", "gemini ultra", "gemini nano", "project astra",
        ],
        "priority": 2,
        "color": "#4285f4",
        "emoji": "🔵",
        "label": "Gemini / Google",
    },
    "xai": {
        "keywords": [
            "xai", "grok", "elon musk ai", "x.ai", "grok 3", "grok 4",
        ],
        "priority": 3,
        "color": "#8b5cf6",
        "emoji": "🟣",
        "label": "xAI / Grok",
    },
    "cn_llm": {
        "keywords": [
            "deepseek", "智谱", "glm", "通义千问", "qwen", "文心一言",
            "ernie", "kimi", "moonshot", "百川", "baichuan", "yi",
            "minimax", "abab", "豆包", "doubao", "讯飞星火", "spark",
            "step", "阶跃星辰", "zhipu", "百炼", "千问",
        ],
        "priority": 4,
        "color": "#ef4444",
        "emoji": "🔴",
        "label": "国内大模型",
    },
    "ai_tools": {
        "keywords": [
            "cursor", "copilot", "windsurf", "cline", "aider", "continue",
            "tabnine", "codeium", "replit ai", "v0", "bolt", "lovable",
            "mcp", "ai coding", "ai ide", "ai assistant", "openwebui",
            "ollama", "comfyui", "midjourney", "stable diffusion",
        ],
        "priority": 5,
        "color": "#06b6d4",
        "emoji": "🔧",
        "label": "AI 工具",
    },
    "forum_tips": {
        "keywords": [
            "合租", "拼车", "共享", "账号", "订阅", "破解", "白嫖",
            "注册机", "虚拟卡", "退款", "反代", "中转", "公益站",
            "group buy", "account sharing", "invite code", "拼单",
            "代充", "代购", "信用卡", "礼品卡",
        ],
        "priority": 6,
        "color": "#f59e0b",
        "emoji": "💡",
        "label": "论坛技巧 / 合租",
    },
    "trending": {
        "keywords": [],
        "priority": 7,
        "color": "#ec4899",
        "emoji": "🔥",
        "label": "突发热点 / 高赞",
    },
}

ALERT_KEYWORDS = [
    "故障", "封号", "封禁", "异常", "下线", "涨价", "停服",
    "暂停", "跑路", "骗局", "风险", "警告", "安全", "泄露",
    "banned", "down", "outage", "崩了", "挂了", "炸了",
    "被封", "限制", "收紧", "审核", "严查",
]

NEW_KEYWORDS = [
    "发布", "更新", "上线", "新版", "v2", "v3", "正式", "推出",
    "announce", "release", "launch", "新品", "开放", "公测",
    "升级", "改版", "来了", "全新", "first", "finally",
]


def classify_post(post):
    """对帖子进行分类，返回 category 字符串"""
    combined = f"{post.title} {post.excerpt}".lower()

    # 检测 alert/new 标志（与分类正交）
    post.is_alert = any(kw in combined for kw in ALERT_KEYWORDS)
    post.is_new = any(kw in combined for kw in NEW_KEYWORDS)

    # 按优先级匹配分类
    for cat_id, cat_info in sorted(CATEGORY_KEYWORDS.items(), key=lambda x: x[1]["priority"]):
        if cat_id == "trending":
            continue
        if any(kw in combined for kw in cat_info["keywords"]):
            post.category = cat_id
            post.is_claude = (cat_id == "claude")
            return cat_id

    # 无关键词匹配：高参与度归 trending
    threshold = 50
    if post.engagement_score >= threshold:
        post.category = "trending"
    else:
        post.category = "trending"  # 默认都保留

    post.is_claude = any(kw in combined for kw in CATEGORY_KEYWORDS["claude"]["keywords"])
    return post.category


def classify_all(posts):
    """批量分类"""
    for p in posts:
        classify_post(p)
    return posts


def get_category_info(category_id):
    """获取分类的显示信息"""
    return CATEGORY_KEYWORDS.get(category_id, CATEGORY_KEYWORDS["trending"])


def build_sections(posts):
    """按分类分组，返回有序的 sections dict"""
    sections = {}
    for cat_id in sorted(CATEGORY_KEYWORDS.keys(), key=lambda k: CATEGORY_KEYWORDS[k]["priority"]):
        cat_posts = [p for p in posts if p.category == cat_id]
        if cat_posts:
            # 各分类内按参与度排序
            cat_posts.sort(key=lambda p: p.engagement_score, reverse=True)
            sections[cat_id] = cat_posts
    return sections
