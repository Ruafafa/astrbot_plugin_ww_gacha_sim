"""
UI资源加载模块
负责抽卡相关的UI资源（如图像、音效、动画文件）的预加载、缓存管理和按需加载逻辑
"""
import os
import sys
import hashlib
import logging
from PIL import Image
from typing import Dict, Optional, List
from src.core.item_data_manager import ItemDataManager
from pathlib import Path
import json

# 添加项目根目录到Python路径，以便正确导入src模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def safe_json_load(file_path: Path) -> Dict:
    """安全的JSON加载工具函数"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"警告: 配置文件 {file_path} 不存在，将使用默认配置")
        return {}
    except json.JSONDecodeError:
        print(f"警告: 配置文件 {file_path} 格式错误，将使用默认配置")
        return {}


class UnifiedCacheManager:
    """统一的缓存管理器"""
    
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.memory_cache = {}
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get(self, key: str) -> Optional[bytes]:
        """从缓存获取数据（优先内存缓存）"""
        if key in self.memory_cache:
            return self.memory_cache[key]
        
        cache_file = self.cache_dir / f"{hashlib.md5(key.encode()).hexdigest()}.cache"
        if cache_file.exists():
            with open(cache_file, 'rb') as f:
                data = f.read()
                self.memory_cache[key] = data
                return data
        return None
    
    def set(self, key: str, data: bytes):
        """设置缓存数据"""
        self.memory_cache[key] = data
        cache_file = self.cache_dir / f"{hashlib.md5(key.encode()).hexdigest()}.cache"
        with open(cache_file, 'wb') as f:
            f.write(data)
    
    def clear(self):
        """清空缓存"""
        import shutil
        self.memory_cache.clear()
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(exist_ok=True)


class UIResourceManager:
    """UI资源管理类"""
    
    def __init__(self, resource_dir: str = "assets", cache_dir: str = "cache", cleanup_interval_hours: int = 24, config_path: str = "config/gacha_config.json"):
        # 初始化日志记录器
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 加载配置
        self.config_path = config_path
        self.config_data = safe_json_load(Path(config_path))
        
        # 从配置中获取缓存目录，如果不存在则使用默认值
        config_cache_dir = self.config_data.get("ui_resources", {}).get("cache_directory", cache_dir)
        # 如果构造函数参数提供了cache_dir且不为默认值，则优先使用参数值
        if cache_dir != "cache":
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path(config_cache_dir)
        
        self.resource_dir = Path(resource_dir)
        self.cleanup_interval_hours = cleanup_interval_hours
        
        # 统一缓存管理
        self.cache_manager = UnifiedCacheManager(self.cache_dir)
        
        # 初始化网络优化器
        from src.rendering.network_optimizer import NetworkOptimizer
        self.network_optimizer = NetworkOptimizer()
        
        # 构建基础下载URL
        base_url = self.config_data.get("ui_resources", {}).get("base_download_url", "https://raw.githubusercontent.com/TomyJan/WutheringWaves-UIResources/")
        version = self.config_data.get("ui_resources", {}).get("version", "3.0")
        self.base_download_url = f'{base_url}{version}/'.rstrip()
        
        # 加载精灵表配置
        self.sprite_atlas = safe_json_load(self.resource_dir / "gacha_atlas.json")
                
        # 确保目录存在
        self.resource_dir.mkdir(exist_ok=True)
        self.cache_dir.mkdir(exist_ok=True)
        
        # 初始化资源映射
        self.resource_mapping = self._load_resource_mapping()

    def _extract_sprite_from_atlas(self, sprite_name: str, remove_transparent_border: bool = False) -> Optional[Image.Image]:
        """从精灵表中提取指定精灵，确保保留完整的透明通道信息"""
        if not self.sprite_atlas or 'frames' not in self.sprite_atlas:
            return None
        
        if sprite_name not in self.sprite_atlas['frames']:
            return None
        
        # 检查缓存
        try:
            cached_data = self.cache_manager.get(f"sprite_{sprite_name}")
            if cached_data:
                from io import BytesIO
                cached_sprite = Image.open(BytesIO(cached_data))
                # 确保返回的图像具有完整的透明通道信息
                if cached_sprite.mode != 'RGBA':
                    cached_sprite = cached_sprite.convert('RGBA')
                
                # 如果需要移除透明边界
                if remove_transparent_border:
                    cached_sprite = self._remove_transparent_border(cached_sprite)
                
                return cached_sprite
        except Exception as e:
            self.logger.warning(f"Error loading cached sprite {sprite_name}: {e}")
            # 如果缓存加载失败，继续尝试从精灵表加载
            pass
        
        # 加载精灵表图像
        atlas_path = self.resource_dir / "gacha_atlas.png"
        try:
            atlas_img = Image.open(atlas_path)
            # 确保精灵表图像是RGBA模式以保留透明度信息
            if atlas_img.mode != 'RGBA':
                atlas_img = atlas_img.convert('RGBA')
        except FileNotFoundError:
            print(f"警告: 精灵表图像 {atlas_path} 不存在")
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
            from io import BytesIO
            buffer = BytesIO()
            sprite_img.save(buffer, format='PNG')
            self.cache_manager.set(f"sprite_{sprite_name}", buffer.getvalue())
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
        # 构建资源映射字典
        resource_mapping = {}
        for char_name in ItemDataManager.get_all_character_names():
            try:
                char_details = ItemDataManager.get_item_details(char_name)  
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
        
        print(f"开始预加载资源: {resource_types}")
        for resource_type in resource_types:
            print(f"预加载 {resource_type}...")
            # 这里可以实现具体的预加载逻辑
            # 例如从本地或远程加载资源到缓存
            self._load_resource_by_type(resource_type)
        print("资源预加载完成")

    def _load_resource_by_type(self, resource_type: str):
        """根据资源类型加载资源"""
        # 模拟加载逻辑
        resource_path = self.resource_dir / resource_type
        resource_path.mkdir(exist_ok=True)
        print(f"  - {resource_type} 资源路径: {resource_path}")

    def get_resource_path(self, resource_name: str) -> Optional[str]:
        """获取指定资源的本地路径，优先检查缓存"""
        # 首先尝试从资源映射中获取资源链接
        if resource_name in self.resource_mapping:
            resource_link = self.resource_mapping[resource_name]
            return self._get_resource_by_link(resource_link, resource_name)
        else:
            # 资源名称未在映射中找到，尝试从item_data获取详细信息
            try:
                char_details = ItemDataManager.get_item_details(resource_name)
                portrait_path = char_details.get('portrait_path', f'UIResources/Character/Avatar/{resource_name}/Portrait.png')
                return self._get_resource_by_link(portrait_path, resource_name)
            except (ImportError, ValueError):
                # 如果无法获取详细信息，返回占位图
                return self._get_default_resource(resource_name)
    
    def _get_resource_by_link(self, resource_link: str, resource_name: str) -> str:
        """根据资源链接获取资源路径（统一处理逻辑）"""
        # 使用resource_name作为稳定的缓存标识符，避免路径变化导致的缓存失效
        cache_filename = f"{hashlib.md5(resource_name.encode()).hexdigest()}.png"
        cached_path = os.path.join(str(self.cache_dir), cache_filename)
        
        # 首先检查缓存文件是否存在（基于item_name）
        if os.path.exists(cached_path):
            return cached_path
        else:
            # 缓存不存在，根据资源链接类型下载资源并缓存
            # 规范化路径
            normalized_link = resource_link.replace('\\', '/')
            
            # 检查是否为网络链接
            if normalized_link.startswith(('http://', 'https://')):
                # 是网络链接，直接下载
                print(f"资源 {resource_name} 缓存不存在，正在下载...")
                success = self.download_resource(normalized_link, cached_path)
                if success:
                    return cached_path
                else:
                    print(f"资源 {resource_name} 下载失败，返回占位图")
                    return self._get_default_resource(resource_name)
            else:
                # 是相对路径或本地路径，统一通过GitHub下载
                print(f"资源 {resource_name} 缓存不存在，正在通过GitHub下载...")
                success = self.download_resource(normalized_link, cached_path, is_portrait_path=True)
                if success:
                    return cached_path
                else:
                    print(f"资源 {resource_name} 通过GitHub下载失败，返回占位图")
                    return self._get_default_resource(resource_name)

    def get_background_for_quality(self, quality: int) -> str:
        """根据品质获取背景路径"""
        # 从精灵表中提取背景精灵
        sprite_name = f"bg_star_{quality}.png"
        sprite_img = self._extract_sprite_from_atlas(sprite_name, remove_transparent_border=True)
        
        if sprite_img is not None:
            # 如果从精灵表成功提取，保存到缓存
            cache_path = self.cache_dir / f"bg_{quality}star_atlas.png"
            sprite_img.save(cache_path)
            return str(cache_path)
        else:
            # 如果无法从精灵表提取，返回默认的背景路径
            default_bg_path = f"assets/backgrounds/bg_{quality}star.png"
            return default_bg_path
    
    def cleanup_cache_if_needed(self):
        """根据配置的时间间隔清理缓存（如果需要）"""
        import time
        current_time = time.time()
        
        # 简化清理逻辑：每次启动时清理旧缓存
        if hasattr(self, 'last_cleanup_time'):
            time_since_last_cleanup = (current_time - self.last_cleanup_time) / 3600
            if time_since_last_cleanup >= self.cleanup_interval_hours:
                print(f"距离上次清理已过去 {time_since_last_cleanup:.2f} 小时，开始清理缓存...")
                self.cache_manager.clear()
                self.last_cleanup_time = current_time
                print("缓存清理完成")
        else:
            self.last_cleanup_time = current_time
    
    def download_resource(self, url_or_path: str, target_path: Optional[str] = None, is_portrait_path: bool = False) -> bool:
        """统一的资源下载方法"""
        # 统一处理路径和URL
        normalized_path = url_or_path.replace('\\', '/')
        
        if is_portrait_path:
            # 对于portrait路径，构建完整的GitHub URL
            # 确保路径以正斜杠开头
            if not normalized_path.startswith('/'):
                normalized_path = '/' + normalized_path
            full_url = self.base_download_url.rstrip('/') + normalized_path
        else:
            # 如果是完整的URL，直接使用
            full_url = normalized_path
        
        # 清除URL末尾的多余空格，避免因空格导致的404错误
        full_url = full_url.rstrip()
        
        # 生成目标路径
        if target_path is None:
            try:
                path_hash = hashlib.md5(normalized_path.encode()).hexdigest()
                ext = os.path.splitext(normalized_path)[1] or '.png'
                target_path = os.path.join(str(self.cache_dir), f"{path_hash}{ext}")
            except Exception as e:
                self.logger.error(f"Error generating target path: {e}")
                print(f"❌ 生成目标路径失败: {e}")
                return False
        
        # 检查是否需要清理缓存
        try:
            self.cleanup_cache_if_needed()
        except Exception as e:
            self.logger.warning(f"Error during cache cleanup: {e}")
            print(f"⚠️  缓存清理失败: {e}")
        
        try:
            # 使用网络优化器下载资源
            content = self.network_optimizer.download_with_retry(full_url)
            if content:
                # 保存到本地
                try:
                    with open(target_path, 'wb') as f:
                        f.write(content)
                    self.logger.info(f"Successfully saved resource to: {target_path}")
                    return True
                except IOError as e:
                    self.logger.error(f"Error saving resource to {target_path}: {e}")
                    print(f"❌ 保存资源失败: {e}")
                    return False
            else:
                self.logger.warning(f"Network optimizer download failed: {full_url}")
                print(f"❌ 网络优化器下载失败: {full_url}")
        except Exception as e:
            self.logger.error(f"Unexpected error during resource download: {e}, URL: {full_url}")
            print(f"❌ 下载资源异常: {e}, URL: {full_url}")
        
        # 如果是portrait路径，尝试从本地assets目录查找资源作为降级策略
        if is_portrait_path:
            try:
                local_path = self.resource_dir / normalized_path.replace('UIResources/', '')
                if local_path.exists():
                    print(f"✅ 在本地找到资源: {local_path}")
                    self.logger.info(f"Found local resource: {local_path}")
                    import shutil
                    try:
                        shutil.copy2(local_path, target_path)
                        return True
                    except IOError as e:
                        self.logger.error(f"Error copying local resource: {e}")
                        print(f"❌ 复制本地资源失败: {e}")
            except Exception as e:
                self.logger.error(f"Error checking local resource: {e}")
                print(f"❌ 检查本地资源失败: {e}")
        
        return False
    
    def get_resource_path_from_item_name(self, item_name: str) -> str:
        """根据item_name获取资源路径，使用缓存优先策略：先检查缓存，缓存不存在时再获取portrait_path并下载"""
        # 使用item_name作为稳定的缓存标识符，避免路径变化导致的缓存失效
        cache_filename = f"{hashlib.md5(item_name.encode()).hexdigest()}.png"
        cached_path = os.path.join(str(self.cache_dir), cache_filename)
        
        # 首先检查缓存文件是否存在（基于item_name）
        if os.path.exists(cached_path):
            return cached_path
        else:
            # 缓存不存在，需要获取portrait_path并下载
            # 从角色数据管理器获取角色详情以获取portrait_path
            try:

                char_details = ItemDataManager.get_item_details(item_name)
                portrait_path = char_details.get('portrait_path', f'UIResources/Character/Avatar/{item_name}/Portrait.png')
            except (ImportError, ValueError, AttributeError, TypeError):
                # 如果无法获取角色详情，返回占位图
                self.logger.error(f"Error getting item details for {item_name}")
                return self._get_default_resource()
            
            if not portrait_path:
                return self._get_default_resource(item_name)
            
            # 规范化路径
            normalized_path = portrait_path.replace('\\', '/').rstrip()
            
            # 检查是否为相对路径（需要拼接GitHub URL）
            if not normalized_path.startswith(('/', str(self.resource_dir), str(self.cache_dir))):
                # 这是一个相对路径，需要通过GitHub下载
                print(f"本地资源 {normalized_path} 不存在，尝试从GitHub下载...")
                success = self.download_resource(normalized_path, cached_path, is_portrait_path=True)
                if success:
                    return cached_path
                else:
                    # 构建并清理URL，避免因空格导致的错误信息不准确
                    error_url = (self.base_download_url.rstrip('/') + '/' + normalized_path.lstrip('/')).rstrip()
                    self.logger.warning(f"Download failed {error_url}: resource unavailable, returning placeholder")
                    print(f"下载资源失败 {error_url}: 资源不可用，返回占位图")
                    return self._get_default_resource(item_name)
            else:
                # 检查是否为真正的本地路径（以资源目录或缓存目录开头）
                if normalized_path.startswith((str(self.resource_dir), str(self.cache_dir))):
                    # 是本地路径，检查文件是否存在
                    local_path = Path(normalized_path)
                    if local_path.exists():
                        # 本地文件存在，先下载到缓存以便后续使用
                        import shutil
                        shutil.copy2(str(local_path), cached_path)
                        return cached_path
                    else:
                        # 本地文件不存在，返回占位图
                        print(f"本地资源 {local_path} 不存在，返回占位图")
                        return self._get_default_resource(item_name)
                else:
                    # 以'/'开头但不在资源目录或缓存目录下，需要拼接GitHub URL下载
                    print(f"本地资源 {normalized_path} 不存在，尝试从GitHub下载...")
                    success = self.download_resource(normalized_path, cached_path, is_portrait_path=True)
                    if success:
                        return cached_path
                    else:
                        # 构建并清理URL，避免因空格导致的错误信息不准确
                        error_url = (self.base_download_url.rstrip('/') + normalized_path).rstrip()
                        self.logger.warning(f"Download failed {error_url}: resource unavailable, returning placeholder")
                        print(f"下载资源失败 {error_url}: 资源不可用，返回占位图")
                        return self._get_default_resource()

    def _get_default_resource(self) -> str:
        """获取默认资源（占位图）"""
        placeholder_path = os.path.join(str(self.cache_dir), "placeholder.png")
        try:
            if not os.path.exists(placeholder_path):
                # 创建一个简单的占位图
                img = Image.new('RGB', (100, 100), (200, 200, 200))
                img.save(placeholder_path)
        except Exception as e:
            self.logger.error(f"Error creating placeholder image: {e}")
            # 如果无法创建占位图，返回一个临时路径
            import tempfile
            temp_path = os.path.join(tempfile.gettempdir(), "gacha_placeholder.png")
            try:
                img = Image.new('RGB', (100, 100), (200, 200, 200))
                img.save(temp_path)
                return temp_path
            except:
                # 万不得已，返回一个不存在的路径，上层需要处理
                return ""
        return placeholder_path