"""
卡池配置管理模块
负责卡池配置文件的加载、保存和CRUD操作
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List
import os
import logging
from dataclasses import dataclass, asdict


from . import PLUGIN_PATH

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class CardPoolConfig:
    """卡池配置数据类
    
    用于封装卡池配置文件的结构化数据
    """
    cp_id: str  # 卡池ID，用于唯一标识卡池
    name: str  # 卡池名称
    probability_settings: Dict[str, float]  # 概率设置
    rate_up_item_ids: Dict[str, Any]  # UP物品配置
    included_item_ids: Dict[str, List[str]]  # 包含物品配置
    probability_progression: Dict[str, Dict[str, Any]]  # 概率递增配置
    
    def __post_init__(self):
        """初始化后处理"""


    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        # 使用asdict转换为字典
        result = asdict(self)
        
        # 确保rate_up_item_ids中的值是列表类型
        for rarity, items in result.get('rate_up_item_ids', {}).items():
            if isinstance(items, str):
                # 如果是字符串，尝试解析为JSON数组
                try:
                    result['rate_up_item_ids'][rarity] = json.loads(items)
                except (json.JSONDecodeError, TypeError):
                    # 如果解析失败，使用空列表
                    result['rate_up_item_ids'][rarity] = []
            elif items is None:
                result['rate_up_item_ids'][rarity] = []
        
        # 确保included_item_ids中的值是列表类型
        for rarity, items in result.get('included_item_ids', {}).items():
            if isinstance(items, str):
                # 如果是字符串，尝试解析为JSON数组
                try:
                    result['included_item_ids'][rarity] = json.loads(items)
                except (json.JSONDecodeError, TypeError):
                    # 如果解析失败，使用空列表
                    result['included_item_ids'][rarity] = []
            elif items is None:
                result['included_item_ids'][rarity] = []
        
        # 确保probability_progression中的值是正确的字典格式
        for rarity, progression in result.get('probability_progression', {}).items():
            if isinstance(progression, dict):
                # 确保soft_pity是列表类型
                if 'soft_pity' in progression and isinstance(progression['soft_pity'], str):
                    try:
                        progression['soft_pity'] = json.loads(progression['soft_pity'])
                    except (json.JSONDecodeError, TypeError):
                        progression['soft_pity'] = []
            else:
                # 如果是字符串，尝试解析为JSON字典
                try:
                    result['probability_progression'][rarity] = json.loads(progression)
                except (json.JSONDecodeError, TypeError):
                    # 如果解析失败，使用默认值
                    result['probability_progression'][rarity] = {
                        'hard_pity_pull': 80,
                        'hard_pity_rate': 1,
                        'soft_pity': []
                    }
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CardPoolConfig':
        # 只保留CardPoolConfig类支持的字段
        valid_fields = {'cp_id', 'name', 'probability_settings', 'rate_up_item_ids', 'included_item_ids', 'probability_progression'}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)


class CardPoolManager:
    """卡池配置管理类
    
    负责卡池配置文件的加载、保存和CRUD操作
    """
    
    def __init__(self, config_dir_path: Path(PLUGIN_PATH / "card_pool_configs")):
        """初始化卡池配置管理器
        
        参数:
            config_dir: 配置文件所在目录
        """
        self.config_dir = config_dir_path
        self._configs: Dict[str, CardPoolConfig] = {}  # 内存中的配置数据，键为配置id
        # 确保配置目录存在
        self._ensure_dir_exists()
        # 加载所有配置文件到内存
        self.load_all_configs()
    
    def _ensure_dir_exists(self):
        """确保配置目录存在，不存在则创建"""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            logger.info(f"配置目录已确保存在: {self.config_dir}")
        except OSError as e:
            logger.error(f"创建配置目录失败: {e}")
            raise RuntimeError(f"创建配置目录失败: {e}")
    
    def load_all_configs(self) -> Dict[str, CardPoolConfig]:
        """加载指定目录下的所有JSON配置文件到内存
        
        返回:
            加载的配置字典，键为配置名称（不含.json后缀），值为配置数据类实例
        """
        try:
            self._configs.clear()
            
            # 遍历配置目录下的所有文件
            for filename in os.listdir(self.config_dir):
                if filename.endswith('.json'):
                    config_name = filename[:-5]  # 移除.json后缀
                    file_path = os.path.join(self.config_dir, filename)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            config_data = json.load(f)
                            # 确保cp_id存在，使用name或config_name作为默认值
                            if 'cp_id' not in config_data:
                                config_data['cp_id'] = config_data.get('name', config_name)
                            # 转换为数据类实例
                            config_instance = CardPoolConfig.from_dict(config_data)
                            self._configs[config_name] = config_instance
                            logger.info(f"已加载配置文件: {filename}")
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON格式错误: {filename} - {e}")
                        raise ValueError(f"配置文件 {filename} 格式错误: {e}")
                    except IOError as e:
                        logger.error(f"读取文件失败: {filename} - {e}")
                        raise IOError(f"读取配置文件 {filename} 失败: {e}")
                    except Exception as e:
                        logger.error(f"处理配置文件 {filename} 失败: {e}")
                        raise RuntimeError(f"处理配置文件 {filename} 失败: {e}")
            
            logger.info(f"共加载 {len(self._configs)} 个配置文件")
            return self._configs.copy()
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            raise RuntimeError(f"加载配置文件失败: {e}")
    
    
    def get_config_names(self) -> List[str]:
        """获取所有配置文件的名称（无后缀）
        
        返回:
            配置名称列表
        """
        return list(self._configs.keys())
    
    def get_config(self, config_id: str) -> CardPoolConfig:
        """获取指定配置
        
        参数:
            config_id: 配置id
            
        返回:
            配置数据类实例
            
        异常:
            KeyError: 配置不存在
        """
        if config_id not in self._configs:
            logger.error(f"配置不存在: {config_id}")
            raise KeyError(f"配置 {config_id} 不存在")
        return self._configs[config_id]
        
    
    def add_config(self, config_id: str, config_data: Dict[str, Any]) -> CardPoolConfig:
        """添加新配置文件
        
        参数:
            config_id: 配置id
            config_data: 配置数据字典
            
        返回:
            创建的配置数据类实例
            
        异常:
            ValueError: 配置已存在或数据格式错误
            IOError: 保存文件失败
        """
        if config_id in self._configs:
            logger.error(f"配置已存在: {config_id}")
            raise ValueError(f"配置 {config_id} 已存在")
        
        try:
            # 创建配置数据类实例
            config_instance = CardPoolConfig.from_dict(config_data)
            
            # 保存到文件
            self._save_config(config_id, config_instance)
            
            # 添加到内存
            self._configs[config_id] = config_instance
            
            logger.info(f"已添加配置: {config_id}")
            return config_instance
        except Exception as e:
            logger.error(f"添加配置失败: {config_id} - {e}")
            raise RuntimeError(f"添加配置 {config_id} 失败: {e}")
    
    def update_config(self, config_name: str, config_data: Dict[str, Any]) -> CardPoolConfig:
        """更新现有配置文件
        
        参数:
            config_name: 配置名称（不含.json后缀）
            config_data: 新的配置数据字典
            
        返回:
            更新后的配置数据类实例
            
        异常:
            KeyError: 配置不存在
            ValueError: 数据格式错误
            IOError: 保存文件失败
        """
        if config_name not in self._configs:
            logger.error(f"配置不存在: {config_name}")
            raise KeyError(f"配置 {config_name} 不存在")
        
        try:
            # 创建配置数据类实例
            config_instance = CardPoolConfig.from_dict(config_data)
            
            # 保存到文件
            self._save_config(config_name, config_instance)
            
            # 更新内存中的配置
            self._configs[config_name] = config_instance
            
            logger.info(f"已更新配置: {config_name}")
            return config_instance
        except Exception as e:
            logger.error(f"更新配置失败: {config_name} - {e}")
            raise RuntimeError(f"更新配置 {config_name} 失败: {e}")
    
    def update_config_property(self, config_name: str, property_path: str, value: Any) -> CardPoolConfig:
        """修改配置文件内的属性
        
        参数:
            config_name: 配置名称（不含.json后缀）
            property_path: 属性路径，如 "rate_up_items.5star" 或 "probability_settings.base_5star_rate"
            value: 新的属性值
            
        返回:
            更新后的配置数据类实例
            
        异常:
            KeyError: 配置不存在
            ValueError: 属性路径无效
            IOError: 保存文件失败
        """
        if config_name not in self._configs:
            logger.error(f"配置不存在: {config_name}")
            raise KeyError(f"配置 {config_name} 不存在")
        
        try:
            # 获取当前配置
            config_instance = self._configs[config_name]
            
            # 将数据类转换为字典以便修改
            config_dict = asdict(config_instance)
            
            # 处理属性路径
            keys = property_path.split('.')
            current = config_dict
            
            # 遍历属性路径，直到最后一个键
            for i, key in enumerate(keys[:-1]):
                if key not in current:
                    raise ValueError(f"属性路径无效: {property_path} (在 {key} 处找不到)")
                current = current[key]
                
                if not isinstance(current, dict):
                    raise ValueError(f"属性路径无效: {property_path} (在 {key} 处不是字典)")
            
            # 设置属性值
            last_key = keys[-1]
            current[last_key] = value
            
            # 转换回数据类实例
            updated_instance = CardPoolConfig.from_dict(config_dict)
            
            # 保存到文件
            self._save_config(config_name, updated_instance)
            
            # 更新内存中的配置
            self._configs[config_name] = updated_instance
            
            logger.info(f"已修改配置属性: {config_name}.{property_path}")
            return updated_instance
        except Exception as e:
            logger.error(f"修改配置属性失败: {config_name}.{property_path} - {e}")
            if isinstance(e, (KeyError, ValueError)):
                raise
            raise RuntimeError(f"修改配置属性 {config_name}.{property_path} 失败: {e}")
    
    
    def delete_config(self, config_name: str) -> bool:
        """删除配置文件
        
        参数:
            config_name: 配置名称（不含.json后缀）
            
        返回:
            删除是否成功
            
        异常:
            KeyError: 配置不存在
            IOError: 删除文件失败
        """
        if config_name not in self._configs:
            logger.error(f"配置不存在: {config_name}")
            raise KeyError(f"配置 {config_name} 不存在")
        
        try:
            # 删除配置文件
            file_path = os.path.join(self.config_dir, f"{config_name}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"已删除配置文件: {config_name}.json")
            else:
                logger.warning(f"配置文件不存在: {config_name}.json")
            
            # 从内存中删除
            del self._configs[config_name]
            logger.info(f"已删除配置: {config_name}")
            return True
        except Exception as e:
            logger.error(f"删除配置失败: {config_name} - {e}")
            raise RuntimeError(f"删除配置 {config_name} 失败: {e}")
    
    def _save_config(self, config_name: str, config_instance: CardPoolConfig):
        """保存配置到文件
        
        参数:
            config_name: 配置名称（不含.json后缀）
            config_instance: 配置数据类实例
            
        异常:
            IOError: 保存文件失败
        """
        try:
            # 转换为字典
            config_dict = asdict(config_instance)
            
            # 保存到文件
            file_path = os.path.join(self.config_dir, f"{config_name}.json")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存配置: {config_name} 到 {file_path}")
        except IOError as e:
            logger.error(f"保存配置失败: {config_name} - {e}")
            raise IOError(f"保存配置 {config_name} 失败: {e}")
        except Exception as e:
            logger.error(f"保存配置时发生错误: {config_name} - {e}")
            raise RuntimeError(f"保存配置 {config_name} 时发生错误: {e}")
    
    def exists(self, config_name: str) -> bool:
        """检查配置是否存在
        
        参数:
            config_name: 配置名称（不含.json后缀）
            
        返回:
            配置是否存在
        """
        return config_name in self._configs
    
    def save_config(self, config_name: str, config_instance: CardPoolConfig):
        """保存配置到文件
        
        参数:
            config_name: 配置名称（不含.json后缀）
            config_instance: 配置数据类实例
            
        异常:
            IOError: 保存文件失败
        """
        self._save_config(config_name, config_instance)
    
    def reload_config(self, config_name: str) -> CardPoolConfig:
        """重新加载指定配置文件
        
        参数:
            config_name: 配置名称（不含.json后缀）
            
        返回:
            重新加载的配置数据类实例
            
        异常:
            KeyError: 配置不存在
            ValueError: JSON格式错误
            IOError: 读取文件失败
        """
        if config_name not in self._configs:
            logger.error(f"配置不存在: {config_name}")
            raise KeyError(f"配置 {config_name} 不存在")
        
        file_path = os.path.join(self.config_dir, f"{config_name}.json")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                config_instance = CardPoolConfig.from_dict(config_data)
                self._configs[config_name] = config_instance
                logger.info(f"已重新加载配置: {config_name}")
                return config_instance
        except json.JSONDecodeError as e:
            logger.error(f"JSON格式错误: {config_name} - {e}")
            raise ValueError(f"配置文件 {config_name} 格式错误: {e}")
        except IOError as e:
            logger.error(f"读取文件失败: {config_name} - {e}")
            raise IOError(f"读取配置文件 {config_name} 失败: {e}")

