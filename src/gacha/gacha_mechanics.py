"""
抽卡机制模块
实现核心的随机抽取算法，包括概率计算、保底机制、稀有度分布逻辑等核心业务规则
"""
import random
import logging
from typing import Tuple
from .cardpool_manager import CardPoolConfig
from ..item_data.item_manager import ItemManager

logger = logging.getLogger(__name__)


class GachaMechanics:
    """抽卡机制类，负责核心的概率和保底逻辑"""

    
    def __init__(self, item_data_manager: ItemManager = ItemManager()):
        """初始化抽卡机制"""
        self.item_data_manager = item_data_manager

    
    def caculate_rate_5star(self, rate_number: int, pool_config: CardPoolConfig) -> float:
        """
        计算当前抽卡的五星概率
        参数：
            rate_number: 距上个五星为第几抽
            pool_config: 卡池概率配置
        返回：
            float: 本次抽到五星的概率
        """
        # 使用配置管理器的 calculate_5star_rate 方法，该方法已经支持特定卡池
        final_prob = pool_config.probability_settings.get('base_5star_rate', 0.008)
    
        # 1. 确保区间按起始位置排序（防止 JSON 数据乱序）
        sorted_pity = pool_config.probability_progression['5star']['soft_pity']
        sorted_pity = sorted(sorted_pity, key=lambda x: x["start_pull"])
        
        # 2. 遍历每一个区间
        for interval in sorted_pity:
            start = interval["start_pull"]
            end = interval["end_pull"]
            increment = interval["increment"]
            
            if rate_number >= start:
                # 计算在当前区间内走过的步数
                # 如果当前抽数超过了区间终点，则取区间全长；否则取当前抽数到起点的距离
                steps_in_this_interval = min(rate_number, end) - start + 1
                
                # 累加增量
                final_prob += steps_in_this_interval * increment
                
                # 如果 target_pull 还没达到这个区间的终点，说明增量计算到此为止
                if rate_number <= end:
                    break
            else:
                # 如果 target_pull 还没到这个区间的起点，因为是有序的，后续区间也不用看了
                break
            
        # 3. 概率最高为 100% (1.0)
        return min(final_prob, 1.0)
        


    def caculate_rate_4star(self, rate_number: int, pool_config: CardPoolConfig) -> float:
        """
        计算当前抽卡的四星概率
        参数：
            rate_number: 距上个四星为第几抽
            pool_config: 卡池概率配置
        返回：
            float: 本次抽到四星的概率
        """
        probs = pool_config.probability_progression['4star']
        hard_pity_pull = probs.get('hard_pity_pull', 0)
        hard_pity_rate = probs.get('hard_pity_rate', 1)

        base_4star_rate = pool_config.probability_settings.get('base_4star_rate', 0.06)

        local_rate = 0
        if rate_number < hard_pity_pull:
            local_rate = base_4star_rate
        elif rate_number == hard_pity_pull:
            local_rate = hard_pity_rate
        else:
            raise ValueError(f'四星保底计数错误：{rate_number}')
        return local_rate
        

    def execute_pull(
        self,
        cardpool_config: CardPoolConfig,
        pity_5star: int,
        pity_4star: int,
        _5star_guaranteed: bool,
        _4star_guaranteed: bool,
    ) -> Tuple[str, int, int, bool, bool]:
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
        up_5star_rate = prob_settings.get('up_5star_rate', 0.5)
        up_4star_rate = prob_settings.get('up_4star_rate', 0.5)
        _4star_role_rate = prob_settings.get('_4star_role_rate', 0.06)
        _4star_hard_pity_pull = pool_config.probability_progression['4star'].get('hard_pity_pull', 10)
        _5star_hard_pity_pull = pool_config.probability_progression['5star'].get('hard_pity_pull', 80)

        # 变量初始化
        local_item = None


        # 变量复制
        new_pity_5star = pity_5star
        new_pity_4star = pity_4star

        # 获取包含物品配置
        included_item_ids = pool_config.included_item_ids

        # 根据包含的物品，筛选出允许的物品
        rate_up_5star_ids = pool_config.rate_up_item_ids.get('5star', [])
        rate_up_4star_ids = pool_config.rate_up_item_ids.get('4star', [])
        
        # 获取包含物品
        items = {}
        for rarity in included_item_ids:
            for item_id in included_item_ids[rarity]:
                items[item_id] = self.item_data_manager.get_item(item_id)
        
        # 过滤掉无效的物品详情
        items = {k: v for k, v in items.items() if v}
        
        # >核心抽卡逻辑<
        # 1.检查是否抽到五星物品
        if self.caculate_rate_5star(pity_5star + 1, pool_config) > local_random:
            # 抽到五星，重置五星保底计数
            new_pity_5star = 0
            
            # 如果本次同时满足四星保底，重置四星保底计数
            if new_pity_4star == _4star_hard_pity_pull:
                new_pity_4star = 0
            
            # 1.1检查抽到的是常驻五星还是限定五星物品
            # 从物品列表中获取所有五星物品
            five_star_items = [item for item in items.values() if item.rarity == '5star']
            
            if not five_star_items:
                logger.info("[NOTICE] 五星物品列表为空")
                # 降级为四星物品
                new_pity_5star += 1
                new_pity_4star = 0
                # 从四星物品中随机选择
                four_star_items = [item for item in items.values() if item.rarity == '4star']
                local_item = random.choice(four_star_items) if four_star_items else None
            else:
                # 过滤掉UP物品（基于ID匹配）
                not_up_5star_items = [item for item in five_star_items if item.unique_id not in rate_up_5star_ids]
                
                if not _5star_guaranteed and random.random() < (1 - up_5star_rate) and not_up_5star_items:
                    # 抽到非up五星物品
                    # 设置大保底，下次五星必定为本期限定五星物品
                    _5star_guaranteed = True
                    local_item = random.choice(not_up_5star_items)
                else:
                    # 抽到up五星物品
                    # 重置大保底
                    _5star_guaranteed = False
                    # 从所有up五星物品中随机选择一个，如果up列表为空则从所有五星物品中选择
                    if rate_up_5star_ids:
                        up_5star_item_id = random.choice(rate_up_5star_ids)
                        local_item = self.item_data_manager.get_item(up_5star_item_id)
                    else:
                        local_item = random.choice(five_star_items)
        # 2.检查是否抽到四星物品
        elif self.caculate_rate_4star(pity_4star + 1, pool_config) > local_random:
            # 抽到四星物品，重置四星保底计数
            new_pity_4star = 0
            # 五星保底计数+1
            new_pity_5star += 1
            # 从物品列表中获取所有四星物品
            four_star_items = [item for item in items.values() if item.rarity == '4star']
            
            if not four_star_items:
                logger.info("[NOTICE] 四星物品列表为空")
                # 降级为三星物品
                new_pity_4star += 1
                new_pity_5star += 1
                # 从三星物品中随机选择
                three_star_items = [item for item in items.values() if item.rarity == '3star']
                local_item = random.choice(three_star_items) if three_star_items else None
            else:
                # 检测是否抽到了四星角色
                item_type = 'character'
                if random.random() > _4star_role_rate:
                    item_type = 'weapon'
                
                # 2.1检测是否抽到了up四星物品
                if rate_up_4star_ids and random.random() < up_4star_rate:
                    # 抽到概率up四星角色
                    _4star_guaranteed = False
                    # 从UP四星物品列表中随机选择一个
                    up4items = [item for item in four_star_items if item.unique_id in rate_up_4star_ids and item.type == item_type]
                    if up4items:
                        local_item = random.choice(up4items)
                    else:
                        # 如果没有符合条件的UP物品，从所有四星物品中选择
                        same_type_4star_items = [item for item in four_star_items if item.type == item_type]
                        local_item = random.choice(same_type_4star_items) if same_type_4star_items else random.choice(four_star_items)
                else:
                    # 抽到非概率up四星物品
                    _4star_guaranteed = True
                    # 从非UP四星物品列表中随机选择
                    non_up_4star_items = [item for item in four_star_items if item.unique_id not in rate_up_4star_ids and item.type == item_type]
                    if non_up_4star_items:
                        local_item = random.choice(non_up_4star_items)
                    else:
                        # 如果没有非UP物品，从所有四星物品中选择
                        same_type_4star_items = [item for item in four_star_items if item.type == item_type]
                        local_item = random.choice(same_type_4star_items) if same_type_4star_items else random.choice(four_star_items)
        # 3.既没抽到五星物品，也没抽到四星物品，则抽取到三星武器
        else:
            # 四星和五星保底计数+1
            new_pity_4star += 1
            new_pity_5star += 1
            
            # 从物品列表中获取所有三星物品
            three_star_items = [item for item in items.values() if item and item.rarity == '3star']
            # 随机选择一个三星物品
            if three_star_items:
                local_item = random.choice(three_star_items)
            else:
                logger.info("[NOTICE] 三星物品列表为空")
                local_item = None

        # 返回更新后的状态
        return local_item, new_pity_5star, new_pity_4star, _5star_guaranteed, _4star_guaranteed