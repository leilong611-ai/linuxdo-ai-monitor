"""配置加载 + V2→V3 兼容"""

import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"


def _migrate_v2_to_v3(v2):
    """将 V2 格式配置转换为 V3"""
    v3 = {
        "version": 3,
        "report": {
            "title": "AI 情报雷达",
            "max_posts_per_section": 20,
            "dedup_title_threshold": 0.75,
        },
        "sources": [],
        "classification": {
            "alert_keywords": [
                "故障", "封号", "封禁", "异常", "下线", "涨价", "停服",
                "暂停", "跑路", "骗局", "风险", "警告", "安全", "泄露",
                "banned", "down", "outage", "涨价", "崩了", "挂了", "炸了",
                "被封", "限制", "收紧", "审核", "严查",
            ],
            "new_keywords": [
                "发布", "更新", "上线", "新版", "v2", "v3", "正式", "推出",
                "announce", "release", "launch", "新品", "开放", "公测",
                "升级", "改版", "来了", "全新", "first", "finally",
            ],
            "trending_score_threshold": 50,
        },
        "push": v2.get("push", {}),
        "request": v2.get("request", {}),
    }

    # linux.do 源
    v3["sources"].append({
        "id": "linuxdo",
        "name": "Linux.do",
        "enabled": True,
        "type": "discourse_rss",
        "site": v2.get("site", "https://linux.do"),
        "tags": v2.get("tags", []),
        "search_queries": v2.get("search_queries", []),
        "extra_categories": ["前沿快讯"],
        "max_items": v2.get("max_posts_per_tag", 20),
    })

    return v3


def load_config():
    """加载配置，支持 V2 和 V3 格式"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # V2 格式检测（无 version 字段或 version < 3）
    if cfg.get("version", 0) < 3:
        cfg = _migrate_v2_to_v3(cfg)

    # 环境变量覆盖飞书配置
    fw = os.environ.get("FEISHU_WEBHOOK", "")
    if fw and not cfg.get("push", {}).get("feishu", {}).get("webhook_url"):
        cfg.setdefault("push", {}).setdefault("feishu", {})["enabled"] = True
        cfg["push"]["feishu"]["webhook_url"] = fw

    return cfg
