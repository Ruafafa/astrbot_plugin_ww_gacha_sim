"""
网络资源访问模块
针对国内网络环境优化资源访问
"""

import logging
import time
from urllib.parse import urlparse

import httpx

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ResourceLoader:
    """网络资源访问优化器"""

    def __init__(self, proxy: dict[str, str] | None = None):
        """
        初始化资源加载器

        Args:
            proxy: 代理配置字典（可选）
        """
        # 请求头
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def download_with_retry(
        self,
        url: str,
        max_retries: int = 3,
        timeout: int = 15,
        proxy: dict[str, str] | None = None,
    ) -> bytes | None:
        """
        简单的资源下载功能，支持代理配置

        Args:
            url: 资源URL
            max_retries: 最大重试次数
            timeout: 超时时间（秒）
            proxy: 代理配置字典（可选）

        Returns:
            下载的内容，失败返回None
        """
        if not self.is_valid_resource_url(url):
            logger.warning(f"❌ 无效的URL: {url}")
            return None

        for attempt in range(max_retries):
            try:
                logger.info(f"Download attempt {attempt + 1}/{max_retries}: {url}")

                client_kwargs = {
                    "timeout": httpx.Timeout(timeout=timeout),
                    "verify": False,  # 禁用 SSL 验证以解决代理下的 SSL 错误
                    "http2": False,  # 禁用 HTTP/2 避免部分代理兼容性问题
                }
                if proxy:
                    # 适配新版 httpx，使用 proxy 参数而不是 proxies
                    proxy_url = None
                    if isinstance(proxy, dict):
                        proxy_url = (
                            proxy.get("all://")
                            or proxy.get("http://")
                            or proxy.get("https://")
                        )
                        if not proxy_url and len(proxy) > 0:
                            proxy_url = next(iter(proxy.values()))

                    if proxy_url:
                        # 检查是否为 GitHub 加速代理（如 gh-proxy.com）
                        # 如果是加速代理且目标是 GitHub 资源，则使用 URL 前缀拼接方式，而不是标准代理协议
                        is_gh_accelerator = any(domain in proxy_url for domain in ["gh-proxy.com", "ghproxy", "fastgit"])
                        is_github_resource = any(domain in url for domain in ["github.com", "githubusercontent.com"])
                        
                        if is_gh_accelerator and is_github_resource:
                            # 移除末尾的斜杠以避免双重斜杠
                            prefix = proxy_url.rstrip("/")
                            url = f"{prefix}/{url}"
                            logger.info(f"使用 GitHub 加速代理: {url}")
                            # 清空 client_kwargs 中的 proxy，因为我们已经重写了 URL
                            if "proxy" in client_kwargs:
                                del client_kwargs["proxy"]
                        else:
                            client_kwargs["proxy"] = proxy_url

                with httpx.Client(**client_kwargs) as client:
                    response = client.get(url, headers=self.headers)
                    if response.status_code == 200:
                        logger.info(f"✅ 下载成功: {url}")
                        return response.content
                    else:
                        logger.warning(
                            f"❌ 下载失败，状态码: {response.status_code}, URL: {url}"
                        )
            except httpx.TimeoutException:
                logger.warning(f"❌ 下载超时，尝试 {attempt + 1}/{max_retries}: {url}")
            except httpx.RequestError as e:
                logger.error(
                    f"❌ 下载请求错误，尝试 {attempt + 1}/{max_retries}: {url}, Error: {e}"
                )
            except Exception as e:
                logger.error(f"❌ 下载尝试 {attempt + 1} 失败: {e}, URL: {url}")

            if attempt < max_retries - 1:
                wait_time = 2**attempt  # 指数退避
                logger.info(f"⏱️  等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)

        logger.error(f"❌ 所有下载尝试都失败: {url}")
        return None

    def is_valid_resource_url(self, url: str) -> bool:
        """检查资源URL是否有效 (仅支持 http 和 https)"""
        try:
            parsed = urlparse(url)
            is_valid = all([parsed.scheme, parsed.netloc]) and parsed.scheme in (
                "http",
                "https",
            )
            if not is_valid:
                logger.warning(f"Invalid URL format or scheme: {url}")
            return is_valid
        except Exception as e:
            logger.error(f"Error parsing URL: {url}, Error: {e}")
            return False
