"""
物品数据管理模块
负责从配置文件加载物品数据并提供物品数据管理功能，包括角色和武器
"""
import json
import csv
from typing import Dict, Any, List


# 模块级变量用于存储数据
_config_path = "config/gacha_config.json"
_config_data = None
_item_details = None

class ItemDataManager:
    """物品数据管理类，统一管理物品数据"""
    
    pass  # 静态类不需要实例化

    @staticmethod
    def _initialize_data():
        """初始化数据，加载配置和物品详情"""
        global _config_data, _item_details
        _config_data = ItemDataManager._load_config()
        _item_details = ItemDataManager._load_item_details()
        
    @staticmethod
    def _load_config() -> Dict[str, Any]:
        """从配置文件加载物品数据"""
        try:
            with open(_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"配置文件 {_config_path} 不存在")
        except json.JSONDecodeError:
            raise ValueError(f"配置文件 {_config_path} 格式错误")
    
    @staticmethod
    def _load_item_details() -> Dict[str, Dict[str, Any]]:
        """从CSV文件加载详细物品信息"""
        # 硬编码CSV文件路径
        csv_file_path = "data/optimized_gacha_data.csv"
        
        item_details = {}
        csv_loaded = False
        
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row['name']
                    item_details[name] = {
                        'name': name,
                        'rarity': int(row['rarity']),
                        'type': row['type'],  # 'character' 或 'weapon' 或其他
                        'affiliated_type': row['affiliated_type'],
                        'portrait_path': row['portrait_path']
                    }
                    csv_loaded = True
        except FileNotFoundError:
            print(f"警告: 优化的物品数据CSV文件 {csv_file_path} 不存在，将使用默认值")
        except Exception as e:
            print(f"加载物品数据CSV文件时出错: {e}")
        
        # 如果CSV文件不存在、出错或内容为空，加载默认物品数据
        if not csv_loaded or not item_details:
            print("错误：优化的物品数据CSV文件不存在、出错或内容为空，无法加载物品数据")
            # 不再提供默认物品数据，直接返回空字典
            return {}
            
        return item_details

    
    @staticmethod
    def _get_items_by_criteria(criteria) -> List[str]:
        """根据指定条件获取物品列表"""
        global _item_details
        if _item_details is None:
            ItemDataManager._initialize_data()
        return [name for name, details in _item_details.items() 
                if criteria(details)]
    
    @staticmethod
    def _get_initial_data(item_list: List[str]) -> Dict[str, List[int]]:
        """获取物品的初始数据"""
        return {name: [-1, 0] for name in item_list}


    @staticmethod
    def get_all_item_names() -> List[str]:
        """获取所有物品名称列表"""
        global _item_details
        if _item_details is None:
            ItemDataManager._initialize_data()
        return list(_item_details.keys())
    
    @staticmethod
    def get_all_character_names() -> List[str]:
        """获取所有角色名称列表"""
        return ItemDataManager._get_items_by_criteria(lambda details: details['type'] == 'character')
    
    
    @staticmethod
    def get_item_details(item_name: str) -> Dict[str, Any]:
        """获取物品的详细信息"""
        global _item_details
        if _item_details is None:
            ItemDataManager._initialize_data()
        if item_name in _item_details:
            return _item_details[item_name]
        else:
            print(f"[ERROR] 物品 {item_name} 在CSV数据中不存在")
            return None


# 初始化数据 when module is loaded
ItemDataManager._initialize_data()
