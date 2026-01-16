"""
抽卡流程模块
实现抽卡流程控制逻辑，包括用户状态管理、抽卡执行和结果统计
"""

from datetime import datetime
from typing import Any

from astrbot.api import logger
from ..db.gacha_db_operations import GachaDBOperations
from ..item_data.item_manager import Item, ItemManager
from .cardpool_manager import CardPoolConfig
from .gacha_mechanics import GachaMechanics


class GachaFlow:
    """抽卡流程管理类

    负责管理用户的抽卡状态、执行抽卡逻辑、处理数据库操作和结果渲染
    使用异步机制提高性能，支持单抽和十连抽两种模式
    """

    def __init__(
        self,
        user_id: str,
        db_ops: GachaDBOperations = GachaDBOperations(),
        item_data_manager: ItemManager = ItemManager(),
    ):
        """
        初始化抽卡流程管理器

        Args:
            user_id: 用户唯一标识符
        """
        self.user_id = user_id
        self.db_ops = db_ops
        self.item_data_manager = item_data_manager
        # 初始化抽卡机制
        self.gacha_mechanics = GachaMechanics(self.item_data_manager)

        # 从数据库加载用户状态，如果不存在则使用默认值
        user_state = self.db_ops.load_user_state(user_id)
        if user_state:
            # 加载已保存的用户状态（保留用户特定的数据）
            self.pity_5star = user_state["pity_5star"]
            self.pity_4star = user_state["pity_4star"]
            self._5star_guaranteed = user_state["_5star_guaranteed"]
            self._4star_guaranteed = user_state["_4star_guaranteed"]
            self.pull_count = user_state["pull_count"]
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

    def _save_pull_data(self, pull_data: dict[str, Any]):
        """
        直接保存抽卡数据到数据库

        Args:
            pull_data: 包含抽卡结果的字典
        """
        # 保存用户状态到数据库
        state_data = {
            "pity_5star": self.pity_5star,
            "pity_4star": self.pity_4star,
            "_5star_guaranteed": self._5star_guaranteed,
            "_4star_guaranteed": self._4star_guaranteed,
            "pull_count": self.pull_count,
        }
        self.db_ops.save_user_state(self.user_id, state_data)

        # 保存抽卡记录到数据库
        self.db_ops.save_pull_history(self.user_id, pull_data)

    def pull(self, pool_config: CardPoolConfig) -> Item | None:
        """
        执行单次抽卡逻辑

        Args:
            pool_config: 卡池配置对象，包含概率、UP物品等信息

        Returns:
            Optional[Item]: 抽取到的物品对象，可能为None
        """
        # 根据卡池配置的 config_group 切换物品管理器的表
        if hasattr(pool_config, "config_group"):
            self.item_data_manager.set_config_group(pool_config.config_group)

        # 执行抽卡核心逻辑，获取物品和更新后的状态
        (
            item,
            new_pity_5star,
            new_pity_4star,
            new__5star_guaranteed,
            new__4star_guaranteed,
        ) = self.gacha_mechanics.execute_pull(
            pool_config,
            self.pity_5star,
            self.pity_4star,
            self._5star_guaranteed,
            self._4star_guaranteed,
        )

        # 更新当前用户状态
        self.pity_5star = new_pity_5star
        self.pity_4star = new_pity_4star
        self._5star_guaranteed = new__5star_guaranteed
        self._4star_guaranteed = new__4star_guaranteed
        self.pull_count += 1

        return item

    def single_pull(self, pool_config: CardPoolConfig) -> dict[str, Any]:
        """
        执行单次抽卡并返回结果

        Args:
            pool_config: 卡池配置对象，包含概率、UP物品等信息

        Returns:
            Dict[str, Any]: 包含抽卡结果的字典
        """
        # 执行抽卡逻辑
        try:
            item_obj = self.pull(pool_config)
        except ValueError as e:
            logger.error(f"抽卡时发生值错误: {e}")
            raise
        except Exception as e:
            logger.error(f"抽卡时发生未知错误: {e}")
            raise

        # 创建抽卡结果字典
        pull_result = {
            "item": item_obj.name if item_obj else "未知物品",
            "rarity": item_obj.rarity if item_obj else "3star",
            "item_obj": item_obj,
        }

        # 保存抽卡数据到数据库
        try:
            self._save_pull_data(
                {
                    "item": pull_result["item"],
                    "rarity": pull_result["rarity"],
                    "pool_id": getattr(pool_config, "cp_id", ""),
                    "pull_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        except Exception as e:
            logger.error(f"保存抽卡数据失败: {e}")

        return pull_result

    def ten_consecutive_pulls(self, pool_config: CardPoolConfig) -> list[Item]:
        """
        执行十连抽卡并返回结果

        Args:
            pool_config: 卡池配置对象，包含概率、UP物品等信息

        Returns:
            List[Item]: 包含十次抽卡结果的物品列表
        """
        # 根据卡池配置的 config_group 切换物品管理器的表
        if hasattr(pool_config, "config_group"):
            self.item_data_manager.set_config_group(pool_config.config_group)

        pull_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        items = []
        pull_history_batch = []  # 批量保存的抽卡历史

        # 执行十次抽卡，但跳过单次数据库操作以提高性能
        try:
            retry_count = 0
            max_retries = 20  # 最大尝试次数，避免死循环（正常只需要10次，多给10次作为容错）
            
            # 确保获取到10个物品
            while len(items) < 10:
                retry_count += 1
                if retry_count > max_retries:
                    logger.error(f"十连抽卡重试次数过多 ({max_retries})，可能存在配置错误或物品缺失")
                    break
                    
                try:
                    # 直接调用execute_pull，跳过pull方法中的数据库操作
                    (
                        item,
                        new_pity_5star,
                        new_pity_4star,
                        new__5star_guaranteed,
                        new__4star_guaranteed,
                    ) = self.gacha_mechanics.execute_pull(
                        pool_config,
                        self.pity_5star,
                        self.pity_4star,
                        self._5star_guaranteed,
                        self._4star_guaranteed,
                    )

                    # 更新状态
                    self.pity_5star = new_pity_5star
                    self.pity_4star = new_pity_4star
                    self._5star_guaranteed = new__5star_guaranteed
                    self._4star_guaranteed = new__4star_guaranteed
                    self.pull_count += 1

                    # 从数据库获取物品详细信息并转换为Item对象
                    if item and hasattr(item, "external_id"):
                        # 如果item已经是Item对象
                        items.append(item)

                        # 记录抽卡历史，用于批量保存
                        pull_history_batch.append(
                            {
                                "item": item.name
                                if item and hasattr(item, "name")
                                else (item if item else "未知物品"),
                                "rarity": item.rarity
                                if item and hasattr(item, "rarity")
                                else "3star",
                                "pool_id": getattr(pool_config, "cp_id", ""),
                                "pull_time": pull_time,
                            }
                        )
                    else:
                        logger.warning(f"抽卡返回无效物品: {item}，将重试")
                except ValueError as e:
                    # 单次抽卡失败（如物品列表为空），重试该次抽卡
                    logger.warning(f"十连抽卡中某次抽卡失败: {e}，将重试")
                    continue
        except ValueError as e:
            logger.error(f"十连抽卡时发生值错误: {e}")
            raise
        except Exception as e:
            logger.error(f"十连抽卡时发生未知错误: {e}")
            raise

        # 一次性保存用户状态和抽卡历史到数据库
        state_data = {
            "pity_5star": self.pity_5star,
            "pity_4star": self.pity_4star,
            "_5star_guaranteed": self._5star_guaranteed,
            "_4star_guaranteed": self._4star_guaranteed,
            "pull_count": self.pull_count,
        }
        self.db_ops.save_user_state(self.user_id, state_data)
        self.db_ops.save_pull_history_batch(self.user_id, pull_history_batch)

        # 按星级和类型排序：星级高的在前，星级相同的角色在前
        def sort_key(item):
            # 星级高的在前（降序），角色优先于武器（角色=0，武器=1）
            # 将稀有度转换为数值进行比较
            rarity_value = {"5star": 5, "4star": 4, "3star": 3}.get(item.rarity, 0)
            return (-rarity_value, 0 if item.type == "character" else 1)

        # 排序结果
        sorted_items = sorted(items, key=sort_key)

        return sorted_items
