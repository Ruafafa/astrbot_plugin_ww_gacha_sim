"""
抽卡流程模块
实现抽卡流程控制逻辑，包括用户状态管理、抽卡执行和结果统计
"""
from datetime import datetime
from src.db.gacha_db_operations import GachaDBOperations
from .gacha_mechanics import GachaMechanics
from typing import Dict, Any
from .cardpool_manager import CardPoolConfig
from ..item_data.item_manager import ItemManager, Item


class GachaFlow:
    """抽卡流程管理类
    
    负责管理用户的抽卡状态、执行抽卡逻辑、处理数据库操作和结果渲染
    使用异步机制提高性能，支持单抽和十连抽两种模式
    """
    
    def __init__(self, user_id: str, 
        db_ops: GachaDBOperations = GachaDBOperations(),
        item_data_manager: ItemManager = ItemManager()
    ):
        """
        初始化抽卡流程管理器
        
        Args:
            user_id: 用户唯一标识符
        """
        self.user_id = user_id
        self.db_ops = db_ops
        self.item_data_manager = item_data_manager
        
        # 从数据库加载用户状态，如果不存在则使用默认值
        user_state = self.db_ops.load_user_state(user_id)
        if user_state:
            # 加载已保存的用户状态（保留用户特定的数据）
            self.pity_5star = user_state['pity_5star']
            self.pity_4star = user_state['pity_4star']
            self._5star_guaranteed = user_state['_5star_guaranteed']
            self._4star_guaranteed = user_state['_4star_guaranteed']
            self.pull_count = user_state['pull_count']
        else:
            # 初始化新用户状态
            self._reset()
            
        # 确保用户在数据库中存在
        self.db_ops.create_user(user_id)
        

    def _reset(self):
        """重置所有状态到初始值"""
        self._5star_guaranteed = False
        self._4star_guaranteed = False
        self.pity_5star = 0
        self.pity_4star = 0
        self.pull_count = 0
        
    
    def _save_pull_data(self, pull_data: Dict[str, Any]):
        """
        直接保存抽卡数据到数据库
        
        Args:
            pull_data: 包含抽卡结果的字典
        """
        # 保存用户状态到数据库
        state_data = {
            'pity_5star': self.pity_5star,
            'pity_4star': self.pity_4star,
            '_5star_guaranteed': self._5star_guaranteed,
            '_4star_guaranteed': self._4star_guaranteed,
            'pull_count': self.pull_count
        }
        self.db_ops.save_user_state(self.user_id, state_data)
        
        # 保存抽卡记录到数据库
        self.db_ops.save_pull_history(self.user_id, pull_data)



    def pull(self, pool_config: CardPoolConfig) -> Item:
        """
        执行单次抽卡逻辑
        
        Args:
            pool_config: 卡池配置对象，包含概率、UP物品等信息
            
        Returns:
            Dict[str, Any]: 包含抽卡结果和相关信息的字典
        """
        # 执行抽卡核心逻辑，获取物品和更新后的状态
        item, new_pity_5star, new_pity_4star, new__5star_guaranteed, new__4star_guaranteed = GachaMechanics.execute_pull(
            pool_config,
            self.pity_5star,
            self.pity_4star,
            self._5star_guaranteed,
            self._4star_guaranteed
        )

        # 更新当前用户状态
        self.pity_5star = new_pity_5star
        self.pity_4star = new_pity_4star
        self._5star_guaranteed = new__5star_guaranteed
        self._4star_guaranteed = new__4star_guaranteed
        self.pull_count += 1

        return item



    def single_pull(self, pool_config: CardPoolConfig) -> Dict[str, Any]:
        """
        执行单次抽卡并返回结果
        
        Args:
            pool_config: 卡池配置对象，包含概率、UP物品等信息
            
        Returns:
            Dict[str, Any]: 包含抽卡结果的字典
        """
        # 执行抽卡逻辑
        item_obj = self.pull(pool_config)

        # 创建抽卡结果字典
        pull_result = {
            'item': item_obj.name if item_obj else "未知物品",
            'rarity': item_obj.rarity if item_obj else '3star',
            'item_obj': item_obj
        }

        # 保存抽卡数据到数据库
        self._save_pull_data({
            'item': pull_result['item'],
            'pull_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        return pull_result
    

    def ten_consecutive_pulls(self, pool_config: CardPoolConfig) -> Dict[str, Any]:
        """
        执行十连抽卡并返回结果
        
        Args:
            pool_config: 卡池配置对象，包含概率、UP物品等信息
            
        Returns:
            Dict[str, Any]: 包含十次抽卡结果和相关信息的字典
        """
        pull_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        items = []
        pull_history_batch = []  # 批量保存的抽卡历史
        
        # 执行十次抽卡，但跳过单次数据库操作以提高性能
        for _ in range(10):
            # 直接调用execute_pull，跳过pull方法中的数据库操作
            item, new_pity_5star, new_pity_4star, new__5star_guaranteed, new__4star_guaranteed = GachaMechanics.execute_pull(
                pool_config,
                self.pity_5star,
                self.pity_4star,
                self._5star_guaranteed,
                self._4star_guaranteed
            )
            
            # 更新状态
            self.pity_5star = new_pity_5star
            self.pity_4star = new_pity_4star
            self._5star_guaranteed = new__5star_guaranteed
            self._4star_guaranteed = new__4star_guaranteed
            self.pull_count += 1
            
            # 从数据库获取物品详细信息并转换为Item对象
            if item and hasattr(item, 'unique_id'):
                # 如果item已经是Item对象
                items.append(item)
            
            # 记录抽卡历史，用于批量保存
            pull_history_batch.append({
                'item': item.name if item and hasattr(item, 'name') else (item if item else "未知物品"),
                'pull_time': pull_time
            })
        
        # 一次性保存用户状态和抽卡历史到数据库
        state_data = {
            'pity_5star': self.pity_5star,
            'pity_4star': self.pity_4star,
            '_5star_guaranteed': self._5star_guaranteed,
            '_4star_guaranteed': self._4star_guaranteed,
            'pull_count': self.pull_count
        }
        self.db_ops.save_user_state(self.user_id, state_data)
        self.db_ops.save_pull_history_batch(self.user_id, pull_history_batch)
        
        return items