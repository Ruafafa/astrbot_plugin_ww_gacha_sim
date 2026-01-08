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
        self.enable_rendering = self.config.get("enable_rendering", True)

        if self.enable_rendering:
            logger.info("启用渲染结果输出功能")
            self.lf_cache = LocalFileCacheManager(cleanup_interval=self.config.get("cache_cleanup_interval", 12))
            self.download_sources = self.config.get("download_sources", None)
            if self.download_sources is None:
                self.primary_url = "https://raw.githubusercontent.com/TomyJan/WutheringWaves-UIResources/3.0/"
                self.mirror_url = ["https://gitee.com", "https://hub.fastgit.org", "https://ghproxy.com"]
            else:
                self.primary_url = self.download_sources.get("primary_sources_url", None)
                self.mirror_url = self.download_sources.get("mirror_sources_url", [])
            self.rs_downloader = ResourcesDownloader(self.primary_url, self.mirror_url)
            self.ui_rs_manager = UIResourceManager(resources_downloader=self.rs_downloader, cache_manager=self.lf_cache)
            self.renderer = GachaRenderer(self.ui_rs_manager)

        # 初始化抽卡
        self.gacha_mechanics = GachaMechanics(self.item_manager)
        config_storage_path = self.config.get("config_storage_path", "./card_pool_configs")
        config_storage_path = Path(config_storage_path)
        if not config_storage_path.is_absolute():
            config_storage_path = PLUGIN_PATH / config_storage_path
        self.cp_manager = CardPoolManager(config_storage_path)

        # 其他设置
        self.save_rendered_results = self.config.get("save_rendered_results", False)

        # 初始化插件所需的各种组件
        # 例如：数据库连接、配置管理器等
        logger.info("鸣潮模拟抽卡插件已初始化")


    @filter.command("单抽", alias={"单次抽卡"})
    async def single_pull(self, event: AstrMessageEvent, pool_identifier: str = ''):
        """
        单次抽卡命令，默认使用用户设置的默认卡池
        
        参数:
            event: 消息事件对象
            pool_identifier: 卡池标识符（可选），可以是 cp_id、配置文件路径或卡池名称，如果不提供则使用默认卡池
        """
        try:
            sender_id = str(event.get_sender_id())

            # 获取所有可用的卡池配置名称
            config_names = self.cp_manager.get_config_names()
            
            if not config_names:
                yield event.plain_result("当前没有可用的卡池配置，请先创建卡池配置文件。")
                return
            
            # 如果未指定卡池标识符，则从KV存储中获取用户的默认卡池设置（存储的是 cp_id）
            if pool_identifier == '':
                pool_identifier = str(await self.get_kv_data(f"user_default_pool_{sender_id}", default=config_names[0]))
            
        
            # 查找匹配的卡池配置
            target_config_name = None
            target_config = None
            
            # 尝试通过 cp_id (UUID) 查找
            try:
                target_config_name, target_config = self.cp_manager.get_config_by_cp_id(pool_identifier)
                logger.info(f"通过 cp_id 找到卡池: {pool_identifier}, 配置文件: {target_config_name}")
            except KeyError:
                # cp_id 匹配失败，继续尝试其他匹配方式
                pass
            
            # 如果没找到，尝试通过卡池显示名称匹配
            if target_config is None:
                matched_configs = self.cp_manager.find_all_configs_by_name(pool_identifier)
                if matched_configs:
                    if len(matched_configs) == 1:
                        # 只有一个匹配，直接使用
                        target_config_name, target_config = matched_configs[0]
                        logger.info(f"通过卡池名称找到卡池: {pool_identifier}, 配置文件: {target_config_name}")
                    else:
                        # 多个匹配，列出可选卡池
                        pool_list = f"找到 {len(matched_configs)} 个名为「{pool_identifier}」的卡池，请选择：\n"
                        for i, (config_name, config) in enumerate(matched_configs, 1):
                            pool_list += f"{i}. {config.name} (ID: {config.cp_id})\n   路径: {config_name}\n"
                        pool_list += "\n请使用 `/单抽 <卡池ID>` 来指定具体卡池。"
                        
                        yield event.plain_result(pool_list)
                        return
            
            if target_config is None:
                pool_list = "找不到指定的卡池。可用的卡池有：\n"
                for i, config_name in enumerate(config_names, 1):
                    try:
                        config = self.cp_manager.get_config(config_name)
                        pool_list += f"{i}. {config.name} - ID: {config.cp_id}\n   路径: {config_name}\n"
                    except Exception as e:
                        logger.warning(f"获取卡池 {config_name} 详情失败: {e}")
                        pool_list += f"{i}. {config_name} (获取详情失败)\n"
                
                yield event.plain_result(pool_list)
                return
            
            # 创建抽卡流程实例并执行单次抽卡
            from .src.gacha.gacha_flow import GachaFlow
            gacha_flow = GachaFlow(sender_id, self.gdb_ops, self.item_manager)
            
            # 执行单次抽卡
            pull_result = gacha_flow.single_pull(target_config)
            item_obj = pull_result.get('item_obj')
            
            if not item_obj:
                yield event.plain_result("抽卡过程中出现错误，未能获得有效物品。")
                return
            
            # 判断是否需要渲染图片
            should_render = self.enable_rendering
            
            if should_render:
                # 渲染抽卡结果图片
                rendered_image = self.renderer.render_single_pull(item_obj)
                
                # 将图片转换为字节数据并发送
                import io
                from astrbot.core.message.components import Image
                
                img_byte_arr = io.BytesIO()
                rendered_image.save(img_byte_arr, format='PNG')
                img_byte_arr.seek(0)
                
                # 直接使用 Image.fromBytes() 从字节数据创建图片组件
                yield event.chain_result([Image.fromBytes(img_byte_arr.getvalue())])
            else:
                # 发送文本结果
                item_rarity = item_obj.rarity
                star_display = "★★★★★" if item_rarity == "5star" else "★★★★" if item_rarity == "4star" else "★★★"
                result_text = f"单次抽卡结果：\n{star_display} {item_obj.name}"
                yield event.plain_result(result_text)
                
        except Exception as e:
            logger.error(f"单次抽卡失败: {e}")
            yield event.plain_result("单次抽卡时发生错误，请检查插件配置或联系管理员。")


    @filter.command("卡池", alias={"卡池列表", "查看卡池"})
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
                    pool_list += f"{i}. {config.name} - ID: {config.cp_id}\n   路径: {config_name}\n"
                except Exception as e:
                    logger.warning(f"获取卡池 {config_name} 详情失败: {e}")
                    pool_list += f"{i}. {config_name} (获取详情失败)\n"
            
            pool_list += "\n使用 `/抽卡 [卡池ID或名称]` 命令开始抽卡。"
            
            yield event.plain_result(pool_list)
            
        except Exception as e:
            logger.error(f"获取卡池列表失败: {e}")
            yield event.plain_result("获取卡池列表时发生错误，请检查插件配置或联系管理员。")
            

    @filter.command("唤取", alias={"选抽", "设置卡池", "选择卡池"})
    async def set_default_pool(self, event: AstrMessageEvent, pool_identifier: str = "默认卡池"):
        """
        设置用户默认卡池
        
        参数:
            event: 消息事件对象
            pool_identifier: 卡池标识符，可以是 cp_id、配置文件路径或卡池名称
        """
        try:
            if not pool_identifier:
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
            
            # 尝试通过 cp_id (UUID) 查找（优先级最高）
            try:
                target_config_name, target_config = self.cp_manager.get_config_by_cp_id(pool_identifier)
                logger.info(f"通过 cp_id 找到卡池: {pool_identifier}, 配置文件: {target_config_name}")
            except KeyError:
                # cp_id 匹配失败，继续尝试其他匹配方式
                pass
            
            # 如果没找到，尝试通过相对路径精确匹配
            if target_config is None:
                try:
                    target_config = self.cp_manager.get_config(pool_identifier)
                    target_config_name = pool_identifier
                    logger.info(f"通过相对路径找到卡池: {pool_identifier}")
                except KeyError:
                    pass
            
            # 如果没找到，尝试通过卡池显示名称匹配
            if target_config is None:
                matched_configs = self.cp_manager.find_all_configs_by_name(pool_identifier)
                if matched_configs:
                    if len(matched_configs) == 1:
                        # 只有一个匹配，直接使用
                        target_config_name, target_config = matched_configs[0]
                        logger.info(f"通过卡池名称找到卡池: {pool_identifier}, 配置文件: {target_config_name}")
                    else:
                        # 多个匹配，列出可选卡池
                        pool_list = f"找到 {len(matched_configs)} 个名为「{pool_identifier}」的卡池，请选择：\n"
                        for i, (config_name, config) in enumerate(matched_configs, 1):
                            pool_list += f"{i}. {config.name} (ID: {config.cp_id})\n   路径: {config_name}\n"
                        pool_list += "\n请使用 `/唤取 <卡池ID>` 或 `/唤取 <配置路径>` 来指定具体卡池。"
                        
                        yield event.plain_result(pool_list)
                        return
            
            if target_config is None:
                pool_list = "找不到指定的卡池。可用的卡池有：\n"
                for i, config_name in enumerate(config_names, 1):
                    try:
                        config = self.cp_manager.get_config(config_name)
                        pool_list += f"{i}. {config.name} - ID: {config.cp_id}\n   路径: {config_name}\n"
                    except Exception as e:
                        logger.warning(f"获取卡池 {config_name} 详情失败: {e}")
                        pool_list += f"{i}. {config_name} (获取详情失败)\n"
                
                yield event.plain_result(pool_list)
                return
            
            # 获取发送者ID作为用户标识
            sender_id = str(event.get_sender_id())
            
            # 使用KV存储保存用户的默认卡池设置（保存 cp_id 以支持配置文件移动）
            await self.put_kv_data(f"user_default_pool_{sender_id}", target_config.cp_id)
            
            yield event.plain_result(f"已设置您的默认卡池为：{target_config.name} (ID: {target_config.cp_id})\n现在您可以使用 `/抽卡` 命令进行抽卡，将默认使用此卡池。")
            
        except Exception as e:
            logger.error(f"设置默认卡池失败: {e}")
            yield event.plain_result("设置默认卡池时发生错误，请检查插件配置或联系管理员。")


    async def terminate(self):
        """
        插件销毁方法，在插件卸载时调用
        """
        logger.info("鸣潮模拟抽卡插件已卸载")