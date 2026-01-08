"""
UI资源渲染模块
负责抽卡相关的UI资源（如图像、音效、动画文件）的渲染相关逻辑
"""
import hashlib
import logging
from PIL import Image
from typing import Dict, Optional, List
from . import PLUGIN_PATH
from ..item_data.item_manager import ItemManager
from pathlib import Path
import json
from .resources_downloader import ResourcesDownloader
from .local_file_cache_manager import LocalFileCacheManager


def safe_json_load(file_path: Path) -> Dict:
    """安全的JSON加载工具函数"""
    logger = logging.getLogger(__name__)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"文件 {file_path} 不存在，将使用默认配置")
        return {}
    except json.JSONDecodeError:
        logger.warning(f"文件 {file_path} 格式错误，将使用默认配置")
        return {}


class UIResourceManager:
    """UI资源管理类"""
    
    def __init__(self, 
        resource_dir: Path = PLUGIN_PATH / "src" / "assets",    
        resources_downloader: ResourcesDownloader = None,
        cache_manager: LocalFileCacheManager = None
     ):
        # 初始化日志记录器
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.resource_dir = resource_dir
        self.resources_downloader = resources_downloader if resources_downloader is not None else ResourcesDownloader()
        self.cache_manager = cache_manager if cache_manager is not None else LocalFileCacheManager()
        
        # 加载精灵表配置
        self.sprite_atlas = safe_json_load(self.resource_dir / "gacha_atlas.json")
                
        # 确保目录存在
        self.resource_dir.mkdir(exist_ok=True)
    
    def _extract_sprite_from_atlas(self, sprite_name: str, remove_transparent_border: bool = False) -> Optional[Image.Image]:
        """从精灵表中提取指定精灵，确保保留完整的透明通道信息"""
        if not self.sprite_atlas or 'frames' not in self.sprite_atlas:
            return None
        
        if sprite_name not in self.sprite_atlas['frames']:
            return None
        
        # 检查缓存
        cache_key = f"sprite_{sprite_name}"
        cached_sprite = self.cache_manager.get_cached_image(cache_key)
        if cached_sprite:
            # 确保返回的图像具有完整的透明通道信息
            if cached_sprite.mode != 'RGBA':
                cached_sprite = cached_sprite.convert('RGBA')
            
            # 如果需要移除透明边界
            if remove_transparent_border:
                cached_sprite = self._remove_transparent_border(cached_sprite)
            
            return cached_sprite
        
        # 加载精灵表图像
        atlas_path = self.resource_dir / "gacha_atlas.png"
        try:
            atlas_img = Image.open(atlas_path)
            # 确保精灵表图像是RGBA模式以保留透明度信息
            if atlas_img.mode != 'RGBA':
                atlas_img = atlas_img.convert('RGBA')
        except FileNotFoundError:
            self.logger.warning(f"精灵表图像 {atlas_path} 不存在")
            return None
        
        # 获取精灵帧信息
        frame_info = self.sprite_atlas['frames'][sprite_name]
        frame = frame_info['frame']
        
        # 从精灵表中裁剪出精灵，保留完整的透明通道信息
        x, y, w, h = frame['x'], frame['y'], frame['w'], frame['h']
        sprite_img = atlas_img.crop((x, y, x+w, y+h))
        
        # 确保提取的精灵具有完整的透明通道信息
        if sprite_img.mode != 'RGBA':
            sprite_img = sprite_img.convert('RGBA')
        
        # 如果需要移除透明边界
        if remove_transparent_border:
            sprite_img = self._remove_transparent_border(sprite_img)
        
        # 缓存提取的精灵
        try:
            self.cache_manager.cache_image(sprite_img, cache_key)
        except Exception as e:
            self.logger.warning(f"Error caching sprite {sprite_name}: {e}")
            # 即使缓存失败，也要返回图像
        
        return sprite_img

    def _ensure_transparency_consistency(self, img: Image.Image) -> Image.Image:
        """确保图像的透明度一致性，消除可能的棋盘格背景"""
        if img.mode != 'RGBA':
            # 如果不是RGBA模式，转换为RGBA模式
            img = img.convert('RGBA')
        
        # 检查图像中是否有透明像素
        alpha_channel = img.split()[-1]  # 获取透明通道
        alpha_data = alpha_channel.getextrema()  # 获取透明度范围
        
        # 如果透明度范围显示有透明区域，确保透明区域完全透明
        if alpha_data[0] < 255:  # 存在透明像素
            # 确保透明区域完全透明（值为0），避免棋盘格背景
            alpha_channel = alpha_channel.point(lambda x: 0 if x < 128 else x)
            r, g, b = img.split()[:3]
            img = Image.merge('RGBA', (r, g, b, alpha_channel))
        
        return img

    def _remove_transparent_border(self, img: Image.Image) -> Image.Image:
        """移除图像周围的透明边界，返回实际内容区域"""
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # 获取alpha通道
        alpha = img.split()[-1]
        
        # 获取非透明区域的边界框
        bbox = alpha.getbbox()
        
        if bbox:
            # 裁剪到实际内容区域
            return img.crop(bbox)
        else:
            # 如果整个图像都是透明的，返回原始图像
            return img

    def _composite_sprites_with_transparency(self, base_img: Image.Image, overlay_img: Image.Image, 
                                           position: tuple, opacity: float = 1.0) -> Image.Image:
        """使用正确的透明度混合叠加精灵图层"""
        # 确保基础图像和覆盖图像都是RGBA模式
        if base_img.mode != 'RGBA':
            base_img = base_img.convert('RGBA')
        if overlay_img.mode != 'RGBA':
            overlay_img = overlay_img.convert('RGBA')
        
        # 如果需要调整透明度
        if opacity < 1.0:
            # 调整覆盖图像的透明度
            r, g, b, a = overlay_img.split()
            # 根据指定的不透明度调整alpha通道
            a = a.point(lambda x: int(x * opacity))
            overlay_img = Image.merge('RGBA', (r, g, b, a))
        
        # 创建新的基础图像副本用于叠加
        result_img = base_img.copy()
        
        # 使用正确的透明度混合方法进行叠加
        result_img.paste(overlay_img, position, overlay_img)
        
        return result_img

    def _load_resource_mapping(self) -> Dict[str, str]:
        """从gacha_data.csv或其他数据源加载资源映射配置"""
        # 构建资源映存字典
        resource_mapping = {}
        for char_name in ItemManager.get_all_character_names():
            try:
                char_details = ItemManager.get_item_details(char_name)  
                # 优先使用portrait_path作为资源路径，如果不存在则使用resource_path
                resource_path = char_details.get('portrait_path', char_details.get('resource_path', f'characters/{char_name}.png'))
                resource_mapping[char_name] = resource_path
            except ValueError:
                # 如果角色不存在详细信息，使用默认路径
                resource_mapping[char_name] = f'characters/{char_name}.png'
        
        return resource_mapping

    def preload_resources(self, resource_types: List[str] = None):
        """预加载指定类型的资源"""
        if resource_types is None:
            resource_types = ['character_images', 'weapon_images', 'backgrounds', 'icons']
        
        self.logger.info(f"开始预加载资源: {resource_types}")
        for resource_type in resource_types:
            self.logger.info(f"预加载 {resource_type}...")
            # 这里可以实现具体的预加载逻辑
            # 例如从本地或远程加载资源到缓存
            self._load_resource_by_type(resource_type)
        self.logger.info("资源预加载完成")

    def _load_resource_by_type(self, resource_type: str):
        """根据资源类型加载资源"""
        # 模拟加载逻辑
        resource_path = self.resource_dir / resource_type
        resource_path.mkdir(exist_ok=True)
        self.logger.debug(f"  - {resource_type} 资源路径: {resource_path}")

    def get_resource_path(self, resource_name: str) -> Optional[str]:
        """获取指定资源的本地路径，优先检查缓存"""
        # 首先尝试从资源映射中获取资源链接
        resource_mapping = self._load_resource_mapping()
        if resource_name in resource_mapping:
            resource_link = resource_mapping[resource_name]
            return self._get_resource_by_link(resource_link, resource_name)
        else:
            # 资源名称未在映射中找到，尝试从item_data获取详细信息
            try:
                char_details = ItemManager.get_item_details(resource_name)
                portrait_path = char_details.get('portrait_path', f'UIResources/Character/Avatar/{resource_name}/Portrait.png')
                return self._get_resource_by_link(portrait_path, resource_name)
            except (ImportError, ValueError):
                # 如果无法获取详细信息，返回占位图
                return self._get_default_resource()
    
    def _get_resource_by_link(self, resource_link: str, resource_name: str) -> str:
        """根据资源链接获取资源路径（统一处理逻辑）"""
        # 使用resource_name作为稳定的缓存标识符，避免路径变化导致的缓存失效
        cache_key = hashlib.md5(resource_name.encode()).hexdigest()
        cached_file_path = self.cache_manager.get_cached_file_path(cache_key)
        
        # 首先检查缓存文件是否存在（基于item_name）
        if cached_file_path:
            return str(cached_file_path)
        else:
            # 缓存不存在，根据资源链接类型下载资源并缓存
            # 规范化路径
            normalized_link = resource_link.replace('\\', '/')
            
            # 检查是否为网络链接
            if normalized_link.startswith(('http://', 'https://')):
                # 是网络链接，直接下载
                self.logger.info(f"资源 {resource_name} 缓存不存在，正在下载...")
                content = self.resources_downloader.download_with_retry(normalized_link)
                if content:
                    # 保存到缓存
                    cached_file_path = self.cache_manager.cache_file(content, cache_key)
                    return str(cached_file_path)
                else:
                    self.logger.warning(f"资源 {resource_name} 下载失败，返回占位图")
                    return self._get_default_resource()
            else:
                # 是相对路径或本地路径，统一通过GitHub下载
                self.logger.info(f"资源 {resource_name} 缓存不存在，正在通过GitHub下载...")
                # 构建完整的GitHub URL
                full_url = self.resources_downloader.get_download_url(normalized_link)
                content = self.resources_downloader.download_with_retry(full_url)
                if content:
                    # 保存到缓存
                    cached_file_path = self.cache_manager.cache_file(content, cache_key)
                    return str(cached_file_path)
                else:
                    self.logger.warning(f"资源 {resource_name} 通过GitHub下载失败，返回占位图")
                    return self._get_default_resource()

    def get_background_for_quality(self, quality: int) -> str:
        """根据品质获取背景路径"""
        # 从精灵表中提取背景精灵
        sprite_name = f"bg_star_{quality}.png"
        sprite_img = self._extract_sprite_from_atlas(sprite_name, remove_transparent_border=True)
        
        if sprite_img is not None:
            # 如果从精灵表成功提取，保存到缓存
            cache_key = f"bg_{quality}star_atlas"
            cached_path = self.cache_manager.cache_image(sprite_img, cache_key)
            return str(cached_path)
        else:
            # 如果无法从精灵表提取，返回默认的背景路径
            default_bg_path = f"assets/backgrounds/bg_{quality}star.png"
            return default_bg_path
    
    def get_resource(self, url_or_path: str, cache_key: Optional[str] = None, is_portrait_path: bool = False):
        """统一的资源下载方法，返回缓存文件路径或None"""
        # 统一处理路径和URL
        normalized_path = url_or_path.replace('\\', '/')
        
        # 检查是否为完整的URL（以http://或https://开头）
        if normalized_path.startswith(('http://', 'https://')):
            # 如果是完整URL，直接使用
            full_url = normalized_path
        elif is_portrait_path:
            # 对于portrait路径，构建完整的GitHub URL
            # 确保路径以正斜杠开头
            if not normalized_path.startswith('/'):
                normalized_path = '/' + normalized_path
            full_url = self.resources_downloader.get_download_url(normalized_path)
        else:
            # 如果是相对路径，直接使用
            full_url = normalized_path
        
        # 清除URL末尾的多余空格，避免因空格导致的404错误
        full_url = full_url.rstrip()
        
        # 生成缓存键
        if cache_key is None:
            cache_key = hashlib.md5(normalized_path.encode()).hexdigest()
        
        # 使用资源下载器下载资源
        content = self.resources_downloader.download_with_retry(full_url)
        if content:
            # 保存到缓存
            cached_file_path = self.cache_manager.cache_file(content, cache_key)
            self.logger.info(f"Successfully saved resource to: {cached_file_path}")
            return cached_file_path
        else:
            self.logger.warning(f"Resource download failed: {full_url}")
        
        # 如果是portrait路径，尝试从本地assets目录查找资源作为降级策略
        if is_portrait_path:
            try:
                local_path = self.resource_dir / normalized_path.replace('UIResources/', '')
                if local_path.exists():
                    self.logger.info(f"Found local resource: {local_path}")
                    # 将本地资源复制到缓存
                    with open(local_path, 'rb') as f:
                        local_content = f.read()
                    cached_file_path = self.cache_manager.cache_file(local_content, cache_key)
                    return cached_file_path
            except Exception as e:
                self.logger.error(f"Error checking local resource: {e}")
        
        return None
    
    def get_resource_path_from_item_name(self, item_name: str) -> str:
        """根据item_name获取资源路径，使用缓存优先策略：先检查缓存，缓存不存在时再获取portrait_path并下载"""
        # 使用item_name作为稳定的缓存标识符，避免路径变化导致的缓存失效
        cache_key = hashlib.md5(item_name.encode()).hexdigest()
        cached_file_path = self.cache_manager.get_cached_file_path(cache_key)
        
        # 首先检查缓存文件是否存在（基于item_name）
        if cached_file_path:
            return str(cached_file_path)
        else:
            # 缓存不存在，需要获取portrait_path并下载
            # 从角色数据管理器获取角色详情以获取portrait_path
            try:
                char_details = ItemManager.get_item_details(item_name)
                portrait_path = char_details.get('portrait_path', f'UIResources/Character/Avatar/{item_name}/Portrait.png')
            except (ImportError, ValueError, AttributeError, TypeError):
                # 如果无法获取角色详情，返回占位图
                self.logger.error(f"Error getting item details for {item_name}")
                return self._get_default_resource()
            
            if not portrait_path:
                return self._get_default_resource()
            
            # 规范化路径
            normalized_path = portrait_path.replace('\\', '/').rstrip()
            
            # 检查是否为完整URL
            if normalized_path.startswith(('http://', 'https://')):
                # 这是一个完整URL，直接下载
                cached_file_path = self.get_resource(normalized_path, cache_key, is_portrait_path=False)
                if cached_file_path:
                    return str(cached_file_path)
                else:
                    self.logger.warning(f"Download failed {normalized_path}: resource unavailable, returning placeholder")
                    return self._get_default_resource()
            # 检查是否为相对路径（需要拼接GitHub URL）
            elif not normalized_path.startswith(('/', str(self.resource_dir))):
                # 这是一个相对路径，需要通过GitHub下载
                self.logger.info(f"本地资源 {normalized_path} 不存在，尝试从GitHub下载...")
                cached_file_path = self.get_resource(normalized_path, cache_key, is_portrait_path=True)
                if cached_file_path:
                    return str(cached_file_path)
                else:
                    # 构建并清理URL，避免因空格导致的错误信息不准确
                    error_url = self.resources_downloader.get_download_url(normalized_path.lstrip('/')).rstrip()
                    self.logger.warning(f"Download failed {error_url}: resource unavailable, returning placeholder")
                    return self._get_default_resource()
            else:
                # 检查是否为真正的本地路径（以资源目录开头）
                if normalized_path.startswith(str(self.resource_dir)):
                    # 是本地路径，检查文件是否存在
                    local_path = Path(normalized_path)
                    if local_path.exists():
                        # 本地文件存在，先下载到缓存以便后续使用
                        with open(local_path, 'rb') as f:
                            local_content = f.read()
                        cached_file_path = self.cache_manager.cache_file(local_content, cache_key)
                        return str(cached_file_path)
                    else:
                        # 本地文件不存在，尝试从GitHub下载
                        self.logger.info(f"本地资源 {normalized_path} 不存在，尝试从GitHub下载...")
                        cached_file_path = self.get_resource(normalized_path, cache_key, is_portrait_path=True)
                        if cached_file_path:
                            return str(cached_file_path)
                        else:
                            # 构建并清理URL，避免因空格导致的错误信息不准确
                            error_url = self.resources_downloader.get_download_url(normalized_path.lstrip('/')).rstrip()
                            self.logger.warning(f"Download failed {error_url}: resource unavailable, returning placeholder")
                            return self._get_default_resource()
                else:
                    # 其他情况，尝试从GitHub下载
                    self.logger.info(f"资源 {normalized_path} 不存在，尝试从GitHub下载...")
                    cached_file_path = self.get_resource(normalized_path, cache_key, is_portrait_path=True)
                    if cached_file_path:
                        return str(cached_file_path)
                    else:
                        # 构建并清理URL，避免因空格导致的错误信息不准确
                        error_url = self.resources_downloader.get_download_url(normalized_path.lstrip('/')).rstrip()
                        self.logger.warning(f"Download failed {error_url}: resource unavailable, returning placeholder")
                        return self._get_default_resource()
                        
    def _get_default_resource(self) -> str:
        """获取默认资源路径（占位图）"""
        # 返回默认占位图路径
        default_path = self.resource_dir / "placeholder.png"
        if not default_path.exists():
            # 如果默认占位图不存在，创建一个简单的占位图
            try:
                img = Image.new('RGBA', (200, 200), (200, 200, 200, 100))  # 灰色占位图
                img.save(default_path)
            except ImportError:
                # 如果PIL不可用，返回空字符串
                return ""
        return str(default_path)
    
    def get_halftone_pattern(self) -> Optional[Image.Image]:
        """获取半调图案"""
        sprite_name = "bandiao.png"
        sprite_img = self._extract_sprite_from_atlas(sprite_name, remove_transparent_border=False)
        if sprite_img:
            return sprite_img
        
        # 如果精灵表中不存在，则从文件系统加载
        halftone_path = self.resource_dir / "bandiao.png"
        if halftone_path.exists():
            return Image.open(halftone_path).convert('RGBA')
        return None
    
    def get_icon_path(self, icon_name: str) -> Optional[str]:
        """获取图标路径"""
        # 构建图标路径
        icon_path = self.resource_dir / "icons" / f'T_{icon_name}.png'
        if icon_path.exists():
            return str(icon_path)
        else:
            # 尝试默认图标
            default_icon_path = self.resource_dir / "icons" / "T_Spectro.png"
            if default_icon_path.exists():
                return str(default_icon_path)
        return None
    
    def get_background_path(self) -> Optional[str]:
        """获取背景路径"""
        bg_path = self.resource_dir / "T_LuckdrawBg.png"
        if bg_path.exists():
            return str(bg_path)
        return None