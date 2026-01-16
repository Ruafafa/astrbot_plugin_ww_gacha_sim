"""
网络代理配置模块
负责管理网络代理设置，支持HTTP/HTTPS代理
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ProxyConfig:
    """网络代理配置类"""

    def __init__(self, proxy_url: str | None = None):
        """初始化代理配置"""
        self.proxy_enabled = False
        self.proxy_url = None
        self.proxy_username = None
        self.proxy_password = None

        if proxy_url:
            self.set_proxy(proxy_url)

    def set_proxy(
        self,
        proxy_url: str,
        username: str | None = None,
        password: str | None = None,
    ):
        """
        设置代理配置

        Args:
            proxy_url: 代理URL（格式: http://host:port 或 https://host:port 或 socks5://host:port）
            username: 代理用户名（可选）
            password: 代理密码（可选）
        """
        self.proxy_enabled = True
        
        # 清理URL并检查scheme
        proxy_url = proxy_url.strip()
        if not (proxy_url.startswith("http://") or proxy_url.startswith("https://") or proxy_url.startswith("socks")):
            proxy_url = f"http://{proxy_url}"
            
        self.proxy_url = proxy_url

        # 如果提供了用户名和密码，构建带认证的代理URL
        if username and password:
            from urllib.parse import urlparse

            parsed = urlparse(proxy_url)
            auth_part = f"{username}:{password}@"
            self.proxy_url = f"{parsed.scheme}://{auth_part}{parsed.netloc}"

        logger.info(f"设置代理: {self.proxy_url}")

    def disable_proxy(self):
        """禁用代理"""
        self.proxy_enabled = False
        self.proxy_url = None
        self.proxy_username = None
        self.proxy_password = None
        logger.info("已禁用代理")

    def get_proxy_dict(self) -> dict[str, str] | None:
        """
        获取代理配置字典，用于httpx

        Returns:
            代理配置字典，如果未启用代理则返回None
        """
        if not self.proxy_enabled or not self.proxy_url:
            return None

        # SOCKS代理支持
        if self.proxy_url.startswith("socks"):
            return {"all://": self.proxy_url}

        return {"http://": self.proxy_url, "https://": self.proxy_url}

    def get_config(self) -> dict[str, Any]:
        """
        获取完整的代理配置信息

        Returns:
            包含代理配置的字典
        """
        return {
            "enabled": self.proxy_enabled,
            "proxy_url": self.proxy_url,
            "proxy_username": self.proxy_username,
            "proxy_password": self.proxy_password,
        }
