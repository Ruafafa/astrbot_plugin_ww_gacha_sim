"""
统一物品模型
将角色和武器统一视为具有品质属性的抽卡物品
"""
from typing import Dict, Any


class Item:
    """统一物品类，包含所有物品共有的属性"""
    
    def __init__(self, name: str, rarity: int, item_type: str, affiliated_type: str, portrait_path: str):
        """
        初始化物品
        
        Args:
            name: 物品名称
            rarity: 物品稀有度 (3, 4, 5)
            item_type: 物品类型 (character, weapon)
            affiliated_type: 关联类型 (character, weapon)
            portrait_path: 物品立绘路径
        """
        self.name = name
        self.rarity = rarity
        self.type = item_type
        self.affiliated_type = affiliated_type
        self.portrait_path = portrait_path
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "rarity": self.rarity,
            "type": self.type,
            "affiliated_type": self.affiliated_type,
            "portrait_path": self.portrait_path
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Item':
        """根据字典创建实例"""
        # 检查必要字段是否存在
        if not data:
            raise ValueError("Item data dictionary is empty")
        # 验证必要字段
        required_fields = {"name", "rarity", "type", "affiliated_type", "portrait_path"}
        if not required_fields.issubset(data.keys()):
            raise ValueError(f"Missing required fields: {required_fields - set(data.keys())}")

        return cls(
            name=data["name"],
            rarity=data["rarity"],
            item_type=data["type"],
            affiliated_type=data["affiliated_type"],
            portrait_path=data["portrait_path"]
        )
