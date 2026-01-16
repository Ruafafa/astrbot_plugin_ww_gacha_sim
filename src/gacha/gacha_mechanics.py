"""
抽卡机制模块
实现核心的随机抽取算法，包括概率计算、保底机制、稀有度分布逻辑等核心业务规则
"""

import random

from astrbot.api import logger

from ..item_data.item_manager import Item, ItemManager
from .cardpool_manager import CardPoolConfig


class GachaMechanics:
    """抽卡机制类，负责核心的概率和保底逻辑"""

    def __init__(self, item_data_manager: ItemManager | None = None):
        """
        初始化抽卡机制

        Args:
            item_data_manager: 物品数据管理器实例
        """
        if item_data_manager is None:
            item_data_manager = ItemManager()
        self.item_data_manager = item_data_manager

    def _filter_items_by_rarity(self, items: dict, rarity: str) -> list:
        """根据稀有度筛选物品

        Args:
            items: 物品字典
            rarity: 稀有度

        Returns:
            符合稀有度的物品列表
        """
        return [item for item in items.values() if item.rarity == rarity]

    def _filter_up_items(self, items: list, up_ids: list) -> list:
        """过滤掉UP物品

        Args:
            items: 物品列表
            up_ids: UP物品external_id列表

        Returns:
            非UP物品列表
        """
        # 使用external_id过滤
        return [
            item for item in items if getattr(item, "external_id", None) not in up_ids
        ]

    def _filter_items_by_type(self, items: list, item_type: str) -> list:
        """根据物品类型筛选物品

        Args:
            items: 物品列表
            item_type: 物品类型

        Returns:
            符合类型的物品列表
        """
        return [item for item in items if item.type == item_type]

    def calculate_rate_5star(
        self, rate_number: int, pool_config: CardPoolConfig
    ) -> float:
        """
        计算当前抽卡的五星概率

        Args:
            rate_number: 距上个五星为第几抽
            pool_config: 卡池概率配置对象

        Returns:
            float: 本次抽到五星的概率 (0.0-1.0)
        """
        # 获取硬保底值
        hard_pity_pull = pool_config.probability_progression["5star"].get(
            "hard_pity_pull", 95
        )
        hard_pity_rate = pool_config.probability_progression["5star"].get(
            "hard_pity_rate", 1.0
        )

        current_number = rate_number + 1
        # 硬保底处理：当达到硬保底次数时，直接返回1.0
        if current_number >= hard_pity_pull:
            return hard_pity_rate

        # 使用配置管理器的 calculate_5star_rate 方法，该方法已经支持特定卡池
        final_prob = pool_config.probability_settings.get("base_5star_rate", 0.008)

        # 1. 软保区间按起始位置排序（防止 JSON 数据乱序）
        sorted_pity = pool_config.probability_progression["5star"]["soft_pity"]
        sorted_pity = sorted(sorted_pity, key=lambda x: x["start_pull"])

        # 2. 遍历每一个区间
        for interval in sorted_pity:
            start = interval["start_pull"]
            end = interval["end_pull"]
            increment = interval["increment"]

            if current_number >= start:
                # 计算在当前区间内走过的步数
                # 如果当前抽数超过了区间终点，则取区间全长；否则取当前抽数到起点的距离
                steps_in_this_interval = min(current_number, end) - start + 1

                # 累加增量
                final_prob += steps_in_this_interval * increment

                # 如果 target_pull 还没达到这个区间的终点，说明增量计算到此为止
                if current_number <= end:
                    break
            else:
                # 如果 target_pull 还没到这个区间的起点，因为是有序的，后续区间也不用看了
                break

        # 3. 概率最高为 100% (1.0)
        return min(final_prob, 1.0)

    def calculate_rate_4star(
        self, rate_number: int, pool_config: CardPoolConfig
    ) -> float:
        """
        计算当前抽卡的四星概率
        参数：
            rate_number: 距上个四星为第几抽
            pool_config: 卡池概率配置
        返回：
            float: 本次抽到四星的概率
        """
        probs = pool_config.probability_progression["4star"]
        hard_pity_pull = probs.get("hard_pity_pull", 0)
        hard_pity_rate = probs.get("hard_pity_rate", 1)

        base_4star_rate = pool_config.probability_settings.get("base_4star_rate", 0.06)

        current_number = rate_number + 1
        local_rate = 0
        if current_number < hard_pity_pull:
            local_rate = base_4star_rate
        elif current_number == hard_pity_pull:
            local_rate = hard_pity_rate
        else:
            raise ValueError(f"四星保底计数错误：{current_number}")
        return local_rate

    def execute_pull(
        self,
        cardpool_config: CardPoolConfig,
        pity_5star: int,
        pity_4star: int,
        _5star_guaranteed: bool,
        _4star_guaranteed: bool,
    ) -> tuple[Item | None, int, int, bool, bool]:
        """
        执行一次抽卡（简化版本，基于统一物品模型）
        参数：
            cardpool_config: 卡池配置
            pity_5star: 当前五星保底计数
            pity_4star: 当前四星保底计数
            _5star_guaranteed: 是否已触发五星保底
            _4star_guaranteed: 是否已触发四星保底
        返回：
            tuple: (抽取到的物品, 更新后的五星保底, 更新后的四星保底, 更新后的五星保底状态, 更新后的四星保底状态)
        """

        # 用于对抽取物判断的随机浮点数，区间[0, 1)
        local_random = random.random()
        # 从配置获取
        pool_config = cardpool_config
        prob_settings = pool_config.probability_settings
        up_5star_rate = prob_settings.get("up_5star_rate", 0.5)
        up_4star_rate = prob_settings.get("up_4star_rate", 0.5)
        _4star_role_rate = prob_settings.get("_4star_role_rate", 0.06)
        _4star_hard_pity_pull = pool_config.probability_progression["4star"].get(
            "hard_pity_pull", 10
        )
        _5star_hard_pity_pull = pool_config.probability_progression["5star"].get(
            "hard_pity_pull", 80
        )

        # 变量初始化
        local_item = None

        # 变量复制
        new_pity_5star = pity_5star
        new_pity_4star = pity_4star

        # 获取包含物品配置
        included_item_ids = pool_config.included_item_ids

        # 根据包含的物品，筛选出允许的物品
        rate_up_5star_ids = pool_config.rate_up_item_ids.get("5star", [])
        rate_up_4star_ids = pool_config.rate_up_item_ids.get("4star", [])

        # 获取包含物品 - 从ItemManager获取所有物品对象
        all_items = self.item_data_manager.get_item_objects()

        # 根据卡池配置筛选物品
        items = {}

        # 筛选物品
        for rarity in included_item_ids:
            for config_item_id in included_item_ids[rarity]:
                if config_item_id in all_items:
                    items[config_item_id] = all_items[config_item_id]

        # 按稀有度分组物品
        items_by_rarity = {
            "5star": [item for item in items.values() if item.rarity == "5star"],
            "4star": [item for item in items.values() if item.rarity == "4star"],
            "3star": [item for item in items.values() if item.rarity == "3star"],
        }

        # 按稀有度和UP状态分组物品
        up_items_by_rarity = {
            "5star": [
                item
                for item in items_by_rarity["5star"]
                if getattr(item, "external_id", None) in rate_up_5star_ids
            ],
            "4star": [
                item
                for item in items_by_rarity["4star"]
                if getattr(item, "external_id", None) in rate_up_4star_ids
            ],
        }

        # >核心抽卡逻辑<
        # 1.检查是否抽到五星物品
        if self.calculate_rate_5star(pity_5star + 1, pool_config) > local_random:
            # 抽到五星，重置五星保底计数
            new_pity_5star = 0

            # 如果本次同时满足四星保底，重置四星保底计数
            if new_pity_4star == _4star_hard_pity_pull:
                new_pity_4star = 0

            # 尝试获取五星物品
            local_item = self._get_item_with_fallback(
                base_rarity="5star",
                is_up=(not _5star_guaranteed and random.random() < up_5star_rate),
                items_by_rarity=items_by_rarity,
                up_items_by_rarity=up_items_by_rarity,
                fallback_path=["4star", "3star"],
            )

            # 更新保底状态
            if (
                local_item
                and getattr(local_item, "external_id", None) in rate_up_5star_ids
            ):
                _5star_guaranteed = False
            else:
                _5star_guaranteed = True

        # 2.检查是否抽到四星物品
        elif self.calculate_rate_4star(pity_4star + 1, pool_config) > local_random:
            # 抽到四星物品，重置四星保底计数
            new_pity_4star = 0
            # 五星保底计数+1
            new_pity_5star += 1

            # 检测是否抽到了四星角色
            item_type = "character" if random.random() > _4star_role_rate else "weapon"

            # 尝试获取四星物品
            is_up = rate_up_4star_ids and random.random() < up_4star_rate
            local_item = self._get_item_with_fallback(
                base_rarity="4star",
                is_up=is_up,
                items_by_rarity=items_by_rarity,
                up_items_by_rarity=up_items_by_rarity,
                fallback_path=["3star", "5star"],
                item_type=item_type,
            )

            # 更新保底状态
            if is_up:
                _4star_guaranteed = False
            else:
                _4star_guaranteed = True

        # 3.既没抽到五星物品，也没抽到四星物品，则抽取到三星物品
        else:
            # 四星和五星保底计数+1
            new_pity_4star += 1
            new_pity_5star += 1

            # 尝试获取三星物品
            local_item = self._get_item_with_fallback(
                base_rarity="3star",
                is_up=False,
                items_by_rarity=items_by_rarity,
                up_items_by_rarity=up_items_by_rarity,
                fallback_path=["4star", "5star"],
            )

        # 返回更新后的状态
        return (
            local_item,
            new_pity_5star,
            new_pity_4star,
            _5star_guaranteed,
            _4star_guaranteed,
        )

    def _get_item_with_fallback(
        self,
        base_rarity: str,
        is_up: bool,
        items_by_rarity: dict[str, list[Item]],
        up_items_by_rarity: dict[str, list[Item]],
        fallback_path: list[str],
        item_type: str | None = None,
    ) -> Item:
        """
        使用偏移重抽机制获取物品，支持多级回退

        Args:
            base_rarity: 基础稀有度
            is_up: 是否为UP物品
            items_by_rarity: 按稀有度分组的物品列表
            up_items_by_rarity: 按稀有度分组的UP物品列表
            rate_up_ids: UP物品ID列表
            fallback_path: 回退路径，优先级从高到低
            item_type: 物品类型（可选）

        Returns:
            Item: 抽取到的物品，确保返回有效物品
        """

        # 定义物品获取的优先级策略
        # 优先级列表：(稀有度, 是否为UP)
        priority_list = []

        # 1. 基础优先级
        if is_up:
            # 如果是UP物品，优先选择同稀有度的UP物品
            priority_list.append((base_rarity, True))
            # 然后选择同稀有度的非UP物品
            priority_list.append((base_rarity, False))
        else:
            # 如果是非UP物品，优先选择同稀有度的非UP物品
            priority_list.append((base_rarity, False))
            # 然后选择同稀有度的UP物品
            priority_list.append((base_rarity, True))

        # 2. 添加回退路径
        for fallback_rarity in fallback_path:
            priority_list.append((fallback_rarity, False))
            priority_list.append((fallback_rarity, True))

        # 遍历优先级列表，尝试获取物品
        for rarity, is_up_item in priority_list:
            # 获取候选物品列表
            if is_up_item:
                candidates = up_items_by_rarity.get(rarity, [])
            else:
                candidates = items_by_rarity.get(rarity, [])

            # 如果指定了物品类型，进一步筛选
            if item_type:
                filtered_candidates = [
                    item for item in candidates if item.type == item_type
                ]
                if filtered_candidates:
                    candidates = filtered_candidates

            # 如果有候选物品，随机选择一个
            if candidates:
                selected_item = random.choice(candidates)
                return selected_item

        # 所有优先级都尝试过，仍然没有物品，尝试从所有可用物品中随机选择
        all_items = []
        for rarity in items_by_rarity:
            all_items.extend(items_by_rarity[rarity])
        for rarity in up_items_by_rarity:
            all_items.extend(up_items_by_rarity[rarity])

        # 去重
        unique_items = list({item.external_id: item for item in all_items}.values())

        if unique_items:
            selected_item = random.choice(unique_items)
            logger.warning(
                f"[偏移重抽] 所有优先级都尝试过，从所有可用物品中随机选择: {selected_item.name}"
            )
            return selected_item
        else:
            # 极端情况：没有任何物品可用，抛出异常
            logger.error("[偏移重抽] 没有任何物品可用")
            raise ValueError("没有任何物品可用")
