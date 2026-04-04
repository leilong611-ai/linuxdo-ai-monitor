"""一句话摘要提取"""

import re


def extract_summary(title, excerpt, max_length=100):
    """从标题和摘录中提取一句话摘要"""
    # 优先使用 excerpt 的第一句
    if excerpt:
        # 取第一句（以。！？.!?结尾）
        sentences = re.split(r'[。！？.!?]', excerpt)
        for s in sentences:
            s = s.strip()
            if len(s) >= 10:  # 至少 10 个字符才算有效
                return s[:max_length]
        # 没有有效句子，直接截断
        clean = excerpt.strip()
        if clean:
            return clean[:max_length]

    # 回退到标题
    return title[:max_length] if title else ""
