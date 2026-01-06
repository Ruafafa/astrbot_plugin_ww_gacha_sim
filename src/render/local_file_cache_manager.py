import hashlib
import json
import time
from pathlib import Path
from typing import Union, Optional
from PIL import Image

from . import PLUGIN_PATH

class LocalFileCacheManager:
    """本地文件缓存管理器"""
    
    def __init__(self, cache_dir: Path(PLUGIN_PATH / "cache")):
        """
        初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录路径
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.meta_file = self.cache_dir / "cache_meta.json"
        self._load_cache_meta()
    
    def _load_cache_meta(self):
        """加载缓存元数据"""
        if self.meta_file.exists():
            try:
                with open(self.meta_file, 'r', encoding='utf-8') as f:
                    self.cache_meta = json.load(f)
            except:
                self.cache_meta = {}
        else:
            self.cache_meta = {}
    
    def _save_cache_meta(self):
        """保存缓存元数据"""
        with open(self.meta_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache_meta, f, ensure_ascii=False, indent=2)
    
    def _generate_cache_key(self, content: Union[str, bytes, Path]) -> str:
        """
        生成缓存键
        
        Args:
            content: 内容（字符串、字节或路径）
            
        Returns:
            缓存键（哈希值）
        """
        if isinstance(content, Path):
            # 如果是路径，使用路径字符串和修改时间
            content_str = f"{str(content)}_{content.stat().st_mtime if content.exists() else 0}"
        elif isinstance(content, bytes):
            content_str = content.hex()
        else:
            content_str = str(content)
        
        return hashlib.md5(content_str.encode('utf-8')).hexdigest()
    
    def get_cached_file_path(self, key: str) -> Optional[Path]:
        """
        获取缓存文件路径
        
        Args:
            key: 缓存键
            
        Returns:
            缓存文件路径（如果存在）
        """
        cache_file = self.cache_dir / f"{key}.cache"
        if cache_file.exists():
            # 检查是否过期
            if self._is_cache_expired(key):
                self._remove_cache(key)
                return None
            return cache_file
        return None
    
    def _is_cache_expired(self, key: str) -> bool:
        """
        检查缓存是否过期
        
        Args:
            key: 缓存键
            
        Returns:
            是否过期
        """
        if key not in self.cache_meta:
            return True
        
        cache_info = self.cache_meta[key]
        if 'expires_at' in cache_info:
            return time.time() > cache_info['expires_at']
        return False
    
    def _remove_cache(self, key: str):
        """删除缓存"""
        # 删除缓存文件
        cache_file = self.cache_dir / f"{key}.cache"
        if cache_file.exists():
            cache_file.unlink()
        
        # 从元数据中移除
        if key in self.cache_meta:
            del self.cache_meta[key]
            self._save_cache_meta()
    
    def cache_file(self, content: Union[str, bytes], key: str = None, expire_time: int = 3600) -> Path:
        """
        缓存文件内容
        
        Args:
            content: 要缓存的内容
            key: 缓存键（如果未提供则自动生成）
            expire_time: 过期时间（秒）
            
        Returns:
            缓存文件路径
        """
        if key is None:
            key = self._generate_cache_key(content)
        
        cache_file = self.cache_dir / f"{key}.cache"
        
        # 写入缓存内容
        if isinstance(content, str):
            with open(cache_file, 'w', encoding='utf-8') as f:
                f.write(content)
        else:
            with open(cache_file, 'wb') as f:
                f.write(content)
        
        # 更新元数据
        self.cache_meta[key] = {
            'created_at': time.time(),
            'expires_at': time.time() + expire_time,
            'size': cache_file.stat().st_size if cache_file.exists() else 0
        }
        self._save_cache_meta()
        
        return cache_file
    
    def cache_image(self, image: Image.Image, key: str = None, expire_time: int = 3600) -> Path:
        """
        缓存图片
        
        Args:
            image: PIL图片对象
            key: 缓存键
            expire_time: 过期时间（秒）
            
        Returns:
            缓存文件路径
        """
        if key is None:
            # 使用图片的哈希值作为键
            image_bytes = self._image_to_bytes(image)
            key = self._generate_cache_key(image_bytes)
        
        cache_file = self.cache_dir / f"{key}.cache"
        
        # 保存图片
        image.save(cache_file, format='PNG')
        
        # 更新元数据
        self.cache_meta[key] = {
            'created_at': time.time(),
            'expires_at': time.time() + expire_time,
            'size': cache_file.stat().st_size if cache_file.exists() else 0,
            'type': 'image'
        }
        self._save_cache_meta()
        
        return cache_file
    
    def _image_to_bytes(self, image: Image.Image) -> bytes:
        """将PIL图片对象转换为字节"""
        import io
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()
    
    def get_cached_image(self, key: str) -> Optional[Image.Image]:
        """
        获取缓存的图片
        
        Args:
            key: 缓存键
            
        Returns:
            PIL图片对象（如果存在且未过期）
        """
        cache_file = self.get_cached_file_path(key)
        if cache_file:
            try:
                return Image.open(cache_file)
            except:
                # 如果图片文件损坏，删除缓存并返回None
                self._remove_cache(key)
                return None
        return None
    
    def clear_expired_cache(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = []
        
        for key, meta in self.cache_meta.items():
            if 'expires_at' in meta and current_time > meta['expires_at']:
                expired_keys.append(key)
        
        for key in expired_keys:
            self._remove_cache(key)
    
    def clear_all_cache(self):
        """清理所有缓存"""
        import shutil
        for cache_file in self.cache_dir.glob("*.cache"):
            cache_file.unlink()
        self.cache_meta = {}
        self._save_cache_meta()
    
    def get_cache_size(self) -> int:
        """获取缓存总大小"""
        total_size = 0
        for cache_file in self.cache_dir.glob("*.cache"):
            total_size += cache_file.stat().st_size
        return total_size