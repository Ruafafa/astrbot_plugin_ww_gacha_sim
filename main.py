from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api import AstrBotConfig
from .src.db.database import CommonDatabase
from .src.db.gacha_db_operations import GachaDBOperations
from .src.db.item_db_operations import ItemDBOperations
from .src.render.local_file_cache_manager import LocalFileCacheManager
from .src.render.resources_downloader import ResourcesDownloader
from .src.render.ui_resources_manager import UIResourceManager
from .src.item_data.item_manager import ItemManager
from .src.render.gacha_renderer import GachaRenderer
from .src.gacha.gacha_mechanics import GachaMechanics
from .src.gacha.cardpool_manager import CardPoolManager
from pathlib import Path

PLUGIN_PATH = Path(__file__).parent

@register("鸣潮模拟抽卡", "Ruafafa", "提供鸣潮游戏的模拟抽卡功能", "1.0.0")
class WutheringWavesGachaPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        """
        插件初始化方法
        """
        super().__init__(context)
                
        # 从配置中获取参数
        self.config = config
        
        # 初始化数据库
        self.cdb = CommonDatabase()
        self.gdb_ops = GachaDBOperations(self.cdb)
        self.idb_ops = ItemDBOperations(self.cdb)
        self.item_manager = ItemManager(self.idb_ops)

        # 初始化渲染
        self.lf_cache = LocalFileCacheManager(self.config)
        self.rs_downloader = ResourcesDownloader(self.lf_cache)
        self.ui_rs_manager = UIResourceManager(self.lf_cache, self.rs_downloader)
        self.renderer = GachaRenderer(self.ui_rs_manager, self.item_manager)

        # 初始化抽卡
        self.gacha_mechanics = GachaMechanics(self.item_manager)
        config_dir_path = PLUGIN_PATH / "card_pool_configs"
        self.cp_manager = CardPoolManager(config_dir_path)

        # 初始化插件所需的各种组件
        # 例如：数据库连接、配置管理器等
        logger.info("鸣潮模拟抽卡插件已初始化")


    @filter.command("卡池", alias=["卡池列表", "查看卡池"])
    async def list_card_pools(self, event: AstrMessageEvent):
        """
        查看所有可用卡池
        
        参数:
            event: 消息事件对象
        """
        try:
            # 获取所有卡池配置名称
            config_names = self.cp_manager.get_config_names()
            
            if not config_names:
                yield event.plain_result("当前没有可用的卡池配置，请先创建卡池配置文件。")
                return
            
            # 格式化卡池列表
            pool_list = "当前可用的卡池：\n"
            for i, config_name in enumerate(config_names, 1):
                try:
                    # 获取卡池配置详情
                    config = self.cp_manager.get_config(config_name)
                    pool_list += f"{i}. {config.name} (ID: {config.cp_id})\n"
                except Exception as e:
                    logger.warning(f"获取卡池 {config_name} 详情失败: {e}")
                    pool_list += f"{i}. {config_name} (获取详情失败)\n"
            
            pool_list += "\n使用 `/抽卡 [卡池ID]` 命令开始抽卡。"
            
            yield event.plain_result(pool_list)
            
        except Exception as e:
            logger.error(f"获取卡池列表失败: {e}")
            yield event.plain_result("获取卡池列表时发生错误，请检查插件配置或联系管理员。")

    @filter.command("唤取", alias=["选抽", "设置卡池", "选择卡池"])
    async def set_default_pool(self, event: AstrMessageEvent, pool_name: str = "全角色池"):
        """
        设置用户默认卡池
        
        参数:
            event: 消息事件对象
            pool_name: 卡池名称
        """
        try:
            if not pool_name:
                yield event.plain_result("请指定要设置的卡池名称。使用方法：/唤取 <卡池名称>")
                return
            
            # 获取所有可用的卡池配置名称
            config_names = self.cp_manager.get_config_names()
            
            if not config_names:
                yield event.plain_result("当前没有可用的卡池配置，请先创建卡池配置文件。")
                return
            
            # 查找匹配的卡池配置
            target_config_name = None
            target_config = None
            
            # 首先精确匹配
            for config_name in config_names:
                if config_name == pool_name:
                    target_config_name = config_name
                    target_config = self.cp_manager.get_config(config_name)
                    break
            
            # 如果没找到精确匹配，尝试模糊匹配（匹配卡池显示名称）
            if target_config_name is None:
                for config_name in config_names:
                    config = self.cp_manager.get_config(config_name)
                    if config.name == pool_name or pool_name in config.name:
                        target_config_name = config_name
                        target_config = config
                        break
            
            if target_config is None:
                pool_list = "找不到指定的卡池名称。可用的卡池有：\n"
                for i, config_name in enumerate(config_names, 1):
                    try:
                        config = self.cp_manager.get_config(config_name)
                        pool_list += f"{i}. {config.name} (ID: {config.cp_id})\n"
                    except Exception as e:
                        logger.warning(f"获取卡池 {config_name} 详情失败: {e}")
                        pool_list += f"{i}. {config_name} (获取详情失败)\n"
                
                yield event.plain_result(pool_list)
                return
            
            # 获取发送者ID作为用户标识
            sender_id = str(event.get_sender_id())
            
            # 使用KV存储保存用户的默认卡池设置
            await self.put_kv_data(f"user_default_pool_{sender_id}", target_config_name)
            
            yield event.plain_result(f"已设置您的默认卡池为：{target_config.name} (ID: {target_config.cp_id})\n现在您可以使用 `/抽卡` 命令进行抽卡，将默认使用此卡池。")
            
        except Exception as e:
            logger.error(f"设置默认卡池失败: {e}")
            yield event.plain_result("设置默认卡池时发生错误，请检查插件配置或联系管理员。")


    async def terminate(self):
        """
        插件销毁方法，在插件卸载时调用
        """
        logger.info("鸣潮模拟抽卡插件已卸载")