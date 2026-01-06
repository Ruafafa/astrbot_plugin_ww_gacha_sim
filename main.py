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
        self.cp_manager = CardPoolManager(self.gdb_ops)

        # 初始化插件所需的各种组件
        # 例如：数据库连接、配置管理器等
        logger.info("鸣潮模拟抽卡插件已初始化")


    @filter.command("hello", "示例命令")
    async def hello(self, event: AstrMessageEvent):
        """
        示例命令处理函数
        """
        yield event.plain_result("Hello, AstrBot!")

    async def terminate(self):
        """
        插件销毁方法，在插件卸载时调用
        """
        logger.info("鸣潮模拟抽卡插件已卸载")