"""数据源基类 + 注册表"""

import time
import requests
from xml.etree import ElementTree

from models import Post

# 按 source_id 注册
SOURCE_REGISTRY = {}
# 按 type 字段注册（用于一对多的源，如 Reddit 多子版块）
SOURCE_TYPE_REGISTRY = {}


def register_source(cls):
    """装饰器：注册数据源"""
    SOURCE_REGISTRY[cls.source_id] = cls
    # 也按 type 注册（如果类定义了 source_type）
    if hasattr(cls, 'source_type') and cls.source_type:
        SOURCE_TYPE_REGISTRY[cls.source_type] = cls
    return cls


def get_enabled_sources(config):
    """从配置中实例化所有启用的数据源"""
    sources = []
    for source_cfg in config.get("sources", []):
        if not source_cfg.get("enabled", True):
            continue
        # 先按 id 查找，再按 type 查找
        cls = SOURCE_REGISTRY.get(source_cfg.get("id"))
        if not cls:
            cls = SOURCE_TYPE_REGISTRY.get(source_cfg.get("type"))
        if cls:
            sources.append(cls(source_cfg, config))
        else:
            print(f"  ⚠️ 未知数据源: {source_cfg.get('id', '?')} (type={source_cfg.get('type', '?')})")
    return sources


class BaseSource:
    """所有数据源的抽象基类"""

    source_id = ""
    source_name = ""

    def __init__(self, source_config, global_config):
        self.cfg = source_config
        self.gcfg = global_config
        self.timeout = global_config.get("request", {}).get("timeout_seconds", 15)
        self.delay = global_config.get("request", {}).get("delay_seconds", 2)
        self.ua = global_config.get("request", {}).get(
            "user_agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        )

    def fetch(self):
        """抓取并返回 Post 列表。子类必须实现。"""
        raise NotImplementedError

    def _http_get(self, url, timeout=None):
        """带 User-Agent 和超时的 HTTP GET"""
        headers = {"User-Agent": self.ua}
        try:
            resp = requests.get(url, headers=headers, timeout=timeout or self.timeout)
            if resp.status_code == 200:
                return resp
            print(f"  ⚠️ {self.source_name} HTTP {resp.status_code}: {url[:60]}")
        except Exception as e:
            print(f"  ⚠️ {self.source_name} 请求失败: {e}")
        return None

    def _fetch_xml(self, url):
        """获取并解析 XML (RSS/Atom)"""
        resp = self._http_get(url)
        if resp:
            try:
                return ElementTree.fromstring(resp.content)
            except Exception as e:
                print(f"  ⚠️ {self.source_name} XML解析失败: {e}")
        return None

    def _fetch_json(self, url):
        """获取并解析 JSON"""
        resp = self._http_get(url)
        if resp:
            try:
                return resp.json()
            except Exception as e:
                print(f"  ⚠️ {self.source_name} JSON解析失败: {e}")
        return None
