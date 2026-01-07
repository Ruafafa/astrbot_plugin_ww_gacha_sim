"""
网络资源访问优化模块
针对国内网络环境优化资源访问
"""
import httpx
import os
import time
from typing import Optional, Dict, Any
from urllib.parse import urlparse
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ResourcesDownloader:
    """网络资源访问优化器"""
    
    def __init__(self, sources: str = "https://raw.githubusercontent.com/TomyJan/WutheringWaves-UIResources/3.0/",
        mirror_sources: list[str] = ["https://gitee.com", "https://hub.fastgit.org", "https://ghproxy.com"]
    ):

        self.sources = sources
        self.mirror_sources = mirror_sources

        # 请求头
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # 记录当前是否使用镜像源
        self.using_mirror = False
        self.current_mirror = None
    
    def check_github_connectivity(self) -> bool:
        """
        检测是否能够正常访问GitHub
        返回True表示可以访问，False表示无法访问
        """
        test_urls = [
            "https://api.github.com",  # GitHub API基础域名
            "https://github.com",  # GitHub主域名
        ]
        
        for test_url in test_urls:
            try:
                # 使用较短的超时时间进行检测
                with httpx.Client(timeout=5.0) as client:
                    response = client.get(test_url, headers=self.headers)
                    if response.status_code == 200:
                        logger.info(f"✅ 成功访问GitHub: {test_url}")
                        return True
            except httpx.TimeoutException:
                logger.warning(f"❌ 访问GitHub超时: {test_url}")
            except httpx.RequestError as e:
                logger.error(f"❌ 请求错误时访问GitHub: {test_url}, Error: {e}")
            except Exception as e:
                logger.error(f"❌ 访问GitHub时发生未知错误: {test_url}, Error: {e}")

        logger.error("❌ 无法访问GitHub服务")
        return False
    
    def check_system_proxy(self) -> Dict[str, Any]:
        """
        检测系统是否配置了有效的网络代理
        返回代理配置信息
        """
        proxy_env_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']
        proxies = {}
        
        for var in proxy_env_vars:
            if var in os.environ:
                proxies[var] = os.environ[var]
        
        if proxies:
            logger.info(f"✅ 检测到系统代理配置: {proxies}")
        else:
            logger.warning("❌ 未检测到系统代理配置")
        return proxies
    
    def switch_to_mirror(self, original_url: str) -> Optional[str]:
        """
        切换到预设的GitHub镜像源
        返回镜像URL，若所有镜像都不可用则返回None
        """
        logger.info(f"🔄 开始切换GitHub镜像源，原始URL: {original_url}")
        
        for mirror in self.mirror_sources:
            try:
                # 测试镜像源是否可用
                test_url = f"{mirror}/"
                with httpx.Client(timeout=5.0) as client:
                    response = client.get(test_url, headers=self.headers)
                    if response.status_code in [200, 301, 302]:
                        # 构建镜像URL - 通用方法：提取相对路径并结合镜像源
                        # 从原始URL中提取相对于sources的路径
                        relative_path = original_url
                        if hasattr(self, 'sources') and self.sources:
                            # 如果原始URL以sources开头，则提取相对路径
                            if original_url.startswith(self.sources):
                                relative_path = original_url[len(self.sources):]
                        
                        # 确保相对路径前面有一个斜杠
                        if not relative_path.startswith('/'):
                            relative_path = '/' + relative_path
                            
                        # 组合镜像源和相对路径
                        if "ghproxy.com" in mirror:
                            # ghproxy.com: 使用代理格式，将原URL作为参数
                            mirror_url = f"{mirror.rstrip('/')}/{original_url}"
                        else:
                            # 其他镜像源：直接组合镜像源和相对路径
                            mirror_url = f"{mirror.rstrip('/')}{relative_path}"
                        
                        self.using_mirror = True
                        self.current_mirror = mirror
                        logger.info(f"✅ 成功切换到镜像源: {mirror}, 镜像URL: {mirror_url}")
                        return mirror_url
                    else:
                        logger.warning(f"Mirror source unavailable: {mirror}, status code: {response.status_code}")
            except httpx.TimeoutException:
                logger.warning(f"Mirror source timeout: {mirror}")
            except httpx.RequestError as e:
                logger.error(f"Request error when accessing mirror: {mirror}, Error: {e}")
                print(f"❌ 无法访问镜像源: {mirror}, 错误: {e}")
            except Exception as e:
                logger.error(f"Unexpected error when accessing mirror: {mirror}, Error: {e}")
                print(f"❌ 无法访问镜像源: {mirror}, 错误: {e}")
        
        print("❌ 所有镜像源都不可用")
        logger.error("All mirror sources are unavailable")
        return None
    
    def download_with_retry(self, url: str, max_retries: int = 3, timeout: int = 15) -> Optional[bytes]:
        """带重试机制的下载功能"""
        # 检查URL是否有效
        if not self.is_valid_resource_url(url):
            logger.warning(f"❌ 无效的URL: {url}")
            return None
        
        # 仅对GitHub URL进行特殊处理
        is_github_url = "github" in url.lower()
        if is_github_url:
            # 1. 执行GitHub连通性测试
            try:
                can_access_github = self.check_github_connectivity()
            except Exception as e:
                logger.error(f"❌ 检查GitHub连通性时发生未知错误: {e}")
                can_access_github = False
            
            if not can_access_github:
                # 2. 检测系统是否配置了有效的网络代理
                try:
                    system_proxies = self.check_system_proxy()
                except Exception as e:
                    logger.error(f"❌ 检查系统代理时发生未知错误: {e}")
                    system_proxies = {}
                
                if not system_proxies:
                    # 3. 自动切换至预设的GitHub镜像源
                    try:
                        mirror_url = self.switch_to_mirror(url)
                        if mirror_url:
                            url = mirror_url
                        else:
                            # 所有镜像源都不可用
                            logger.error("❌ 无法访问GitHub且所有镜像源都不可用，建议检查网络连接或手动配置代理")
                            return None
                    except Exception as e:
                        logger.error(f"❌ 镜像切换失败: {e}")
                        return None
        
        # 4. 尝试下载资源
        for attempt in range(max_retries):
            try:
                logger.info(f"Download attempt {attempt + 1}/{max_retries}: {url}")
                
                with httpx.Client(timeout=httpx.Timeout(timeout=timeout)) as client:
                    response = client.get(url, headers=self.headers)
                    if response.status_code == 200:
                        logger.info(f"✅ 下载成功: {url}")
                        return response.content
                    else:
                        logger.warning(f"❌ 下载失败，状态码: {response.status_code}, URL: {url}")
            except httpx.TimeoutException:
                logger.warning(f"❌ 下载超时，尝试 {attempt + 1}/{max_retries}: {url}")
            except httpx.RequestError as e:
                logger.error(f"❌ 下载请求错误，尝试 {attempt + 1}/{max_retries}: {url}, Error: {e}")
            except Exception as e:
                logger.error(f"❌ 下载尝试 {attempt + 1} 失败: {e}, URL: {url}")
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 指数退避
                logger.info(f"⏱️  等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
        
        # 5. 所有尝试都失败
        logger.error(f"❌ 所有下载尝试都失败: {url}")
        return None
    
    def is_valid_resource_url(self, url: str) -> bool:
        """检查资源URL是否有效"""
        try:
            parsed = urlparse(url)
            is_valid = all([parsed.scheme, parsed.netloc])
            if not is_valid:
                logger.warning(f"Invalid URL format: {url}")
            return is_valid
        except Exception as e:
            logger.error(f"Error parsing URL: {url}, Error: {e}")
            return False