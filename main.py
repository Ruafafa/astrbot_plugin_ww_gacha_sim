import time
from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .src.db.database import CommonDatabase
from .src.db.gacha_db_operations import GachaDBOperations
from .src.db.item_db_operations import ItemDBOperations
from .src.gacha.cardpool_manager import CardPoolManager
from .src.gacha.gacha_flow import GachaFlow
from .src.gacha.gacha_mechanics import GachaMechanics
from .src.item_data.item_manager import ItemManager
from .src.render.gacha_renderer import GachaRenderer
from .src.render.local_file_cache_manager import LocalFileCacheManager
from .src.render.proxy_config import ProxyConfig
from .src.render.resource_loader import ResourceLoader
from .src.render.ui_resources_manager import UIResourceManager

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

        # 初始化代理配置
        proxy_url = self.config.get("proxy_url", "")
        enable_proxy = self.config.get("enable_proxy", False)

        if not enable_proxy:
            proxy_url = None  # 如果未启用代理，强制不使用

        self.proxy_config = ProxyConfig(proxy_url if proxy_url else None)

        if self.enable_rendering:
            logger.info("启用渲染结果输出功能")
            self.lf_cache = LocalFileCacheManager(
                cleanup_interval=self.config.get("cache_cleanup_interval", 12)
            )
            self.rs_loader = ResourceLoader()
            self.ui_rs_manager = UIResourceManager(
                resources_loader=self.rs_loader,
                cache_manager=self.lf_cache,
                proxy_config=self.proxy_config,
            )
            self.renderer = GachaRenderer(self.ui_rs_manager)

        # 初始化抽卡
        self.gacha_mechanics = GachaMechanics(self.item_manager)
        config_storage_path = self.config.get(
            "config_storage_path", "./card_pool_configs"
        )
        config_storage_path = Path(config_storage_path)
        if not config_storage_path.is_absolute():
            config_storage_path = PLUGIN_PATH / config_storage_path
        self.cp_manager = CardPoolManager(config_storage_path)

        # 其他设置
        self.save_rendered_results = self.config.get("save_rendered_results", False)
        self.render_output_path = self.config.get("render_output_path", "./rendered_results")

        # 初始化插件所需的各种组件
        # 例如：数据库连接、配置管理器等
        logger.info("鸣潮模拟抽卡插件已初始化")

    def _save_rendered_image(self, image, user_id: str):
        """
        保存渲染结果图片
        
        Args:
            image: PIL Image 对象
            user_id: 用户ID
        """
        if not self.save_rendered_results:
            return

        try:
            # 获取输出路径配置
            output_path_str = self.render_output_path
            output_path = Path(output_path_str)
            
            # 处理相对路径
            if not output_path.is_absolute():
                # 相对于插件目录
                output_path = PLUGIN_PATH / output_path
            
            # 确保目录存在
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 生成文件名
            timestamp = int(time.time())
            filename = f"gacha_result_{user_id}_{timestamp}.png"
            file_path = output_path / filename
            
            # 保存图片
            image.save(file_path, format="PNG")
            logger.info(f"已保存抽卡结果图片: {file_path}")
            
        except Exception as e:
            logger.error(f"保存抽卡结果图片失败: {e}")

    @filter.command("单抽", alias={"单次抽卡", "抽卡", "单次唤取"})
    async def single_pull(self, event: AstrMessageEvent, pool_identifier: str = ""):
        """
        单次抽卡命令，默认使用用户设置的默认卡池

        参数:
            event: 消息事件对象
            pool_identifier: 卡池标识符（可选），可以是 cp_id、配置文件路径或卡池名称，如果不提供则使用默认卡池
        """
        try:
            sender_id = str(event.get_sender_id())

            # 获取所有可用的卡池配置 cp_id
            config_ids = self.cp_manager.get_config_ids()

            if not config_ids:
                yield event.plain_result(
                    "当前没有可用的卡池配置，请先创建卡池配置文件。"
                )
                return

            # 如果未指定卡池标识符，则从KV存储中获取用户的默认卡池设置（存储的是 cp_id）
            if pool_identifier == "":
                saved_cp_id = await self.get_kv_data(
                    f"user_default_pool_{sender_id}", default=None
                )

                # 检查保存的 cp_id 是否仍然存在于当前的 config_ids 中
                if saved_cp_id and saved_cp_id in config_ids:
                    pool_identifier = saved_cp_id
                else:
                    # cp_id 不存在或用户未设置，使用第一个可用的卡池
                    pool_identifier = config_ids[0]

                    # 如果保存的 cp_id 不存在，清理无效数据
                    if saved_cp_id and saved_cp_id not in config_ids:
                        await self.delete_kv_data(f"user_default_pool_{sender_id}")
                        logger.info(
                            f"用户 {sender_id} 的默认卡池 {saved_cp_id} 不存在，已清理"
                        )

            # 查找匹配的卡池配置
            target_config = None

            # 尝试通过 cp_id (UUID) 查找（优先级最高，因为KV存储的就是cp_id）
            try:
                target_config = self.cp_manager.get_config_by_cp_id(pool_identifier)
                logger.info(f"通过 cp_id 找到卡池: {pool_identifier}")
            except KeyError:
                # cp_id 匹配失败，继续尝试其他匹配方式
                pass

            # 如果没找到，尝试通过相对路径精确匹配
            if target_config is None:
                try:
                    target_config = self.cp_manager.get_config(pool_identifier)
                    logger.info(f"通过相对路径找到卡池: {pool_identifier}")
                except KeyError:
                    pass

            # 如果没找到，尝试通过卡池显示名称匹配
            if target_config is None:
                matched_configs = self.cp_manager.get_config_by_name(pool_identifier)
                if matched_configs:
                    if len(matched_configs) == 1:
                        # 只有一个匹配，直接使用
                        target_config = matched_configs[0]
                        target_cp_id = target_config.cp_id
                        logger.info(
                            f"通过卡池名称找到卡池: {pool_identifier}, cp_id: {target_cp_id}"
                        )
                    else:
                        # 多个匹配，列出可选卡池
                        pool_list = f"找到 {len(matched_configs)} 个名为「{pool_identifier}」的卡池，请选择：\n"
                        for i, config in enumerate(matched_configs, 1):
                            pool_list += f"{i}. {config.name} (ID: {config.cp_id})\n"
                        pool_list += "\n请使用 `/单抽 <卡池ID>` 来指定具体卡池。"

                        yield event.plain_result(pool_list)
                        return

            if target_config is None:
                pool_list = "找不到指定的卡池。可用的卡池有：\n"
                for i, cp_id in enumerate(config_ids, 1):
                    try:
                        config = self.cp_manager.get_config_by_cp_id(cp_id)
                        # 检查配置是否启用
                        if config.enable:
                            pool_list += f"{i}. {config.name} - ID: {config.cp_id}\n"
                    except Exception as e:
                        logger.warning(f"获取卡池 {cp_id} 详情失败: {e}")
                        pool_list += f"{i}. {cp_id} (获取详情失败)\n"

                yield event.plain_result(pool_list)
                return

            # 检查配置是否启用
            if not target_config.enable:
                yield event.plain_result(
                    f"卡池「{target_config.name}」已被禁用，无法进行抽卡。"
                )
                return

            # 根据卡池配置的 config_group 创建对应的 ItemManager
            config_group = getattr(target_config, "config_group", "default")
            item_manager = ItemManager(self.idb_ops, config_group)

            # 创建抽卡流程实例并执行单次抽卡
            gacha_flow = GachaFlow(sender_id, self.gdb_ops, item_manager)

            # 执行单次抽卡
            pull_result = gacha_flow.single_pull(target_config)
            item_obj = pull_result.get("item_obj")

            if not item_obj:
                yield event.plain_result("抽卡过程中出现错误，未能获得有效物品。")
                return

            # 判断是否需要渲染图片
            should_render = self.enable_rendering

            if should_render:
                # 获取发送者昵称
                sender_name = event.get_sender_name() if hasattr(event, "get_sender_name") else "未知用户"
                
                # 渲染抽卡结果图片
                rendered_image = self.renderer.render_single_pull(item_obj, nickname=sender_name, user_id=sender_id)

                # 保存渲染结果
                self._save_rendered_image(rendered_image, sender_id)

                # 将图片转换为字节数据并发送
                import io

                from astrbot.core.message.components import Image

                img_byte_arr = io.BytesIO()
                rendered_image.save(img_byte_arr, format="PNG")
                img_byte_arr.seek(0)

                # 直接使用 Image.fromBytes() 从字节数据创建图片组件
                yield event.chain_result([Image.fromBytes(img_byte_arr.getvalue())])
            else:
                # 发送文本结果
                item_rarity = item_obj.rarity
                star_display = (
                    "★★★★★"
                    if item_rarity == "5star"
                    else "★★★★"
                    if item_rarity == "4star"
                    else "★★★"
                )
                result_text = f"单次抽卡结果：\n{star_display} {item_obj.name}"
                yield event.plain_result(result_text)

        except Exception as e:
            logger.error(f"单次抽卡失败: {e}")
            yield event.plain_result("单次抽卡时发生错误，请检查插件配置或联系管理员。")

    @filter.command("十抽", alias={"十连", "10抽", "10连"})
    async def ten_pulls(self, event: AstrMessageEvent, pool_identifier: str = ""):
        """
        十连抽卡命令，默认使用用户设置的默认卡池

        参数:
            event: 消息事件对象
            pool_identifier: 卡池标识符（可选），可以是 cp_id、配置文件路径或卡池名称，如果不提供则使用默认卡池
        """
        try:
            sender_id = str(event.get_sender_id())

            # 获取所有可用的卡池配置 cp_id
            config_ids = self.cp_manager.get_config_ids()

            if not config_ids:
                yield event.plain_result(
                    "当前没有可用的卡池配置，请先创建卡池配置文件。"
                )
                return

            # 如果未指定卡池标识符，则从KV存储中获取用户的默认卡池设置（存储的是 cp_id）
            if pool_identifier == "":
                saved_cp_id = await self.get_kv_data(
                    f"user_default_pool_{sender_id}", default=None
                )

                # 检查保存的 cp_id 是否仍然存在于当前的 config_ids 中
                if saved_cp_id and saved_cp_id in config_ids:
                    pool_identifier = saved_cp_id
                else:
                    # cp_id 不存在或用户未设置，使用第一个可用的卡池
                    pool_identifier = config_ids[0]

                    # 如果保存的 cp_id 不存在，清理无效数据
                    if saved_cp_id and saved_cp_id not in config_ids:
                        await self.delete_kv_data(f"user_default_pool_{sender_id}")
                        logger.info(
                            f"用户 {sender_id} 的默认卡池 {saved_cp_id} 不存在，已清理"
                        )

            # 查找匹配的卡池配置
            target_config = None

            # 尝试通过 cp_id (UUID) 查找（优先级最高，因为KV存储的就是cp_id）
            try:
                target_config = self.cp_manager.get_config_by_cp_id(pool_identifier)
                logger.info(f"通过 cp_id 找到卡池: {pool_identifier}")
            except KeyError:
                # cp_id 匹配失败，继续尝试其他匹配方式
                pass

            # 如果没找到，尝试通过相对路径精确匹配
            if target_config is None:
                try:
                    target_config = self.cp_manager.get_config(pool_identifier)
                    logger.info(f"通过相对路径找到卡池: {pool_identifier}")
                except KeyError:
                    pass

            # 如果没找到，尝试通过卡池显示名称匹配
            if target_config is None:
                matched_configs = self.cp_manager.get_config_by_name(pool_identifier)
                if matched_configs:
                    if len(matched_configs) == 1:
                        # 只有一个匹配，直接使用
                        target_config = matched_configs[0]
                        target_cp_id = target_config.cp_id
                        logger.info(
                            f"通过卡池名称找到卡池: {pool_identifier}, cp_id: {target_cp_id}"
                        )
                    else:
                        # 多个匹配，列出可选卡池
                        pool_list = f"找到 {len(matched_configs)} 个名为「{pool_identifier}」的卡池，请选择：\n"
                        for i, config in enumerate(matched_configs, 1):
                            pool_list += f"{i}. {config.name} (ID: {config.cp_id})\n"
                        pool_list += "\n请使用 `/十抽 <卡池ID>` 来指定具体卡池。"

                        yield event.plain_result(pool_list)
                        return

            if target_config is None:
                pool_list = "找不到指定的卡池。可用的卡池有：\n"
                for i, cp_id in enumerate(config_ids, 1):
                    try:
                        config = self.cp_manager.get_config_by_cp_id(cp_id)
                        # 检查配置是否启用
                        if config.enable:
                            pool_list += f"{i}. {config.name} - ID: {config.cp_id}\n"
                    except Exception as e:
                        logger.warning(f"获取卡池 {cp_id} 详情失败: {e}")
                        pool_list += f"{i}. {cp_id} (获取详情失败)\n"

                yield event.plain_result(pool_list)
                return

            # 检查配置是否启用
            if not target_config.enable:
                yield event.plain_result(
                    f"卡池「{target_config.name}」已被禁用，无法进行抽卡。"
                )
                return

            # 根据卡池配置的 config_group 创建对应的 ItemManager
            config_group = getattr(target_config, "config_group", "default")
            item_manager = ItemManager(self.idb_ops, config_group)

            # 创建抽卡流程实例并执行十连抽
            gacha_flow = GachaFlow(sender_id, self.gdb_ops, item_manager)

            # 执行十连抽
            item_objs = gacha_flow.ten_consecutive_pulls(target_config)

            if not item_objs:
                yield event.plain_result("抽卡过程中出现错误，未能获得有效物品。")
                return

            # 判断是否需要渲染图片
            should_render = self.enable_rendering

            if should_render:
                # 获取发送者昵称
                sender_name = event.get_sender_name() if hasattr(event, "get_sender_name") else "未知用户"

                # 渲染十连抽结果图片
                rendered_image = self.renderer.render_ten_pulls(item_objs, nickname=sender_name, user_id=sender_id)

                # 保存渲染结果
                self._save_rendered_image(rendered_image, sender_id)

                # 将图片转换为字节数据并发送
                import io

                from astrbot.core.message.components import Image

                img_byte_arr = io.BytesIO()
                rendered_image.save(img_byte_arr, format="PNG")
                img_byte_arr.seek(0)

                # 直接使用 Image.fromBytes() 从字节数据创建图片组件
                yield event.chain_result([Image.fromBytes(img_byte_arr.getvalue())])
            else:
                # 发送文本结果
                result_text = "十连抽卡结果：\n"
                for idx, item_obj in enumerate(item_objs, 1):
                    item_rarity = item_obj.rarity
                    star_display = (
                        "★★★★★"
                        if item_rarity == "5star"
                        else "★★★★"
                        if item_rarity == "4star"
                        else "★★★"
                    )
                    result_text += f"{idx}. {star_display} {item_obj.name}\n"
                yield event.plain_result(result_text)

        except Exception as e:
            logger.error(f"十连抽卡失败: {e}")
            yield event.plain_result("十连抽卡时发生错误，请检查插件配置或联系管理员。")

    @filter.command("卡池", alias={"卡池列表", "查看卡池"})
    async def list_card_pools(self, event: AstrMessageEvent):
        """
        查看所有可用卡池

        参数:
            event: 消息事件对象
        """
        try:
            # 获取所有卡池配置 cp_id
            config_ids = self.cp_manager.get_config_ids()

            if not config_ids:
                yield event.plain_result(
                    "当前没有可用的卡池配置，请先创建卡池配置文件。"
                )
                return

            # 格式化卡池列表
            pool_list = "当前可用的卡池：\n"
            for i, cp_id in enumerate(config_ids, 1):
                try:
                    # 获取卡池配置详情
                    config = self.cp_manager.get_config_by_cp_id(cp_id)
                    # 只显示启用的卡池
                    if config.enable:
                        pool_list += f"{i}. {config.name} - ID: {config.cp_id}\n"
                except Exception as e:
                    logger.warning(f"获取卡池 {cp_id} 详情失败: {e}")
                    pool_list += f"{i}. {cp_id} (获取详情失败)\n"

            pool_list += "\n使用 `/单抽 <卡池ID或名称>` 命令开始抽卡。"

            yield event.plain_result(pool_list)

        except Exception as e:
            logger.error(f"获取卡池列表失败: {e}")
            yield event.plain_result(
                "获取卡池列表时发生错误，请检查插件配置或联系管理员。"
            )

    @filter.command("唤取", alias={"选抽", "设置卡池", "选择卡池"})
    async def set_default_pool(
        self, event: AstrMessageEvent, pool_identifier: str = "examples/默认卡池"
    ):
        """
        设置用户默认卡池

        参数:
            event: 消息事件对象
            pool_identifier: 卡池标识符，可以是 cp_id、配置文件路径或卡池名称
        """
        try:
            if not pool_identifier:
                yield event.plain_result(
                    "请指定要设置的卡池名称。使用方法：/唤取 <卡池名称>"
                )
                return

            # 获取所有可用的卡池配置 cp_id
            config_ids = self.cp_manager.get_config_ids()

            if not config_ids:
                yield event.plain_result(
                    "当前没有可用的卡池配置，请先创建卡池配置文件。"
                )
                return

            # 查找匹配的卡池配置
            target_config = None

            # 尝试通过 cp_id (UUID) 查找（优先级最高）
            try:
                target_config = self.cp_manager.get_config_by_cp_id(pool_identifier)
                logger.info(f"通过 cp_id 找到卡池: {pool_identifier}")
            except KeyError:
                # cp_id 匹配失败，继续尝试其他匹配方式
                pass

            # 如果没找到，尝试通过相对路径精确匹配
            if target_config is None:
                try:
                    target_config = self.cp_manager.get_config(pool_identifier)
                    logger.info(f"通过相对路径找到卡池: {pool_identifier}")
                except KeyError:
                    pass

            # 如果没找到，尝试通过卡池显示名称匹配
            if target_config is None:
                matched_configs = self.cp_manager.get_config_by_name(pool_identifier)
                if matched_configs:
                    if len(matched_configs) == 1:
                        # 只有一个匹配，直接使用
                        target_config = matched_configs[0]
                        target_cp_id = target_config.cp_id
                        logger.info(
                            f"通过卡池名称找到卡池: {pool_identifier}, cp_id: {target_cp_id}"
                        )
                    else:
                        # 多个匹配，列出可选卡池
                        pool_list = f"找到 {len(matched_configs)} 个名为「{pool_identifier}」的卡池，请选择：\n"
                        for i, config in enumerate(matched_configs, 1):
                            pool_list += f"{i}. {config.name} (ID: {config.cp_id})\n"
                        pool_list += "\n请使用 `/唤取 <卡池ID>` 来指定具体卡池。"

                        yield event.plain_result(pool_list)
                        return

            if target_config is None:
                pool_list = "找不到指定的卡池。可用的卡池有：\n"
                for i, cp_id in enumerate(config_ids, 1):
                    try:
                        config = self.cp_manager.get_config_by_cp_id(cp_id)
                        # 只显示启用的卡池
                        if config.enable:
                            pool_list += f"{i}. {config.name} - ID: {config.cp_id}\n"
                    except Exception as e:
                        logger.warning(f"获取卡池 {cp_id} 详情失败: {e}")
                        pool_list += f"{i}. {cp_id} (获取详情失败)\n"

                yield event.plain_result(pool_list)
                return

            # 检查配置是否启用
            if not target_config.enable:
                yield event.plain_result(
                    f"卡池「{target_config.name}」已被禁用，无法设置为默认卡池。"
                )
                return

            # 获取发送者ID作为用户标识
            sender_id = str(event.get_sender_id())

            # 使用KV存储保存用户的默认卡池设置（保存 cp_id 以支持配置文件移动）
            await self.put_kv_data(
                f"user_default_pool_{sender_id}", target_config.cp_id
            )

            yield event.plain_result(
                f"已设置您的默认卡池为：{target_config.name} (ID: {target_config.cp_id})\n现在您可以使用 `/抽卡` 命令进行抽卡，将默认使用此卡池。"
            )

        except Exception as e:
            logger.error(f"设置默认卡池失败: {e}")
            yield event.plain_result(
                "设置默认卡池时发生错误，请检查插件配置或联系管理员。"
            )

    @filter.command("唤取记录", alias={"抽卡记录", "查看抽卡", "抽卡历史"})
    async def view_pull_history(self, event: AstrMessageEvent, page_or_pool: str = "1"):
        """
        查看当前会话用户的历史抽卡记录

        参数:
            event: 消息事件对象
            page_or_pool: 页码或卡池标识符，默认为1，每页显示10条记录
        """
        try:
            # 获取发送者ID作为用户标识
            sender_id = str(event.get_sender_id())

            # 每页显示10条记录
            page_size = 10

            # 解析参数，判断是页码还是卡池标识符
            page = 1
            pool_identifier = None
            pool_id = None
            pool_name_display = "全部卡池"

            try:
                # 尝试解析为页码
                page = int(page_or_pool)
            except ValueError:
                # 不是页码，作为卡池标识符
                pool_identifier = page_or_pool

                # 查找匹配的卡池
                if pool_identifier:
                    # 获取所有可用的卡池配置 cp_id
                    config_ids = self.cp_manager.get_config_ids()

                    if not config_ids:
                        yield event.plain_result(
                            "当前没有可用的卡池配置，请先创建卡池配置文件。"
                        )
                        return

                    # 尝试通过 cp_id 查找
                    try:
                        target_config = self.cp_manager.get_config_by_cp_id(
                            pool_identifier
                        )
                        pool_id = target_config.cp_id
                        pool_name_display = target_config.name
                        logger.info(f"通过 cp_id 找到卡池: {pool_identifier}")
                    except KeyError:
                        # 尝试通过名称查找
                        matched_configs = self.cp_manager.get_config_by_name(
                            pool_identifier
                        )
                        if matched_configs:
                            if len(matched_configs) == 1:
                                # 只有一个匹配，直接使用
                                target_config = matched_configs[0]
                                pool_id = target_config.cp_id
                                pool_name_display = target_config.name
                                logger.info(
                                    f"通过卡池名称找到卡池: {pool_identifier}, cp_id: {pool_id}"
                                )
                            else:
                                # 多个匹配，列出可选卡池
                                pool_list = f"找到 {len(matched_configs)} 个名为「{pool_identifier}」的卡池，请选择：\n"
                                for i, config in enumerate(matched_configs, 1):
                                    pool_list += (
                                        f"{i}. {config.name} - ID: {config.cp_id}\n"
                                    )
                                pool_list += (
                                    "\n请使用 `/抽卡记录 <卡池ID>` 来指定具体卡池。"
                                )

                                yield event.plain_result(pool_list)
                                return
                        else:
                            # 没有找到匹配的卡池
                            pool_list = f"找不到指定的卡池: {pool_identifier}\n\n可用的卡池有：\n"
                            for i, cp_id in enumerate(config_ids, 1):
                                try:
                                    config = self.cp_manager.get_config_by_cp_id(cp_id)
                                    if config.enable:
                                        pool_list += (
                                            f"{i}. {config.name} - ID: {cp_id}\n"
                                        )
                                except Exception as e:
                                    logger.warning(f"获取卡池 {cp_id} 详情失败: {e}")
                                    pool_list += f"{i}. {cp_id} (获取详情失败)\n"

                            yield event.plain_result(pool_list)
                            return

            # 计算偏移量
            offset = (page - 1) * page_size

            # 获取抽卡历史记录
            pull_history = self.gdb_ops.load_pull_history(
                user_id=sender_id,
                limit=page_size,
                offset=offset,
                order="desc",
                pool_id=pool_id,
            )

            # 获取总记录数
            total_records = self.gdb_ops.get_pull_history_count(
                sender_id, pool_id=pool_id
            )

            # 计算总页数
            total_pages = (total_records + page_size - 1) // page_size

            # 如果没有记录
            if total_records == 0:
                if pool_identifier:
                    yield event.plain_result("您在该卡池还没有任何抽卡记录。")
                else:
                    yield event.plain_result("您还没有任何抽卡记录。")
                return

            # 如果页码超出范围
            if page < 1 or page > total_pages:
                yield event.plain_result(
                    f"页码超出范围。当前共有 {total_records} 条记录，分为 {total_pages} 页。"
                )
                return

            # 如果启用渲染功能，发送图片
            if self.enable_rendering:
                # 丰富记录数据（添加类型信息）
                all_items = self.item_manager.get_all_items()
                name_to_type = {}
                for item_data in all_items.values():
                    name_to_type[item_data["name"]] = item_data["type"]

                enriched_history = []
                for record in pull_history:
                    item_name = record["item"]
                    # 从缓存中查找类型
                    item_type = name_to_type.get(item_name, "unknown")

                    record_copy = record.copy()
                    record_copy["type"] = item_type
                    enriched_history.append(record_copy)

                # 渲染图片
                rendered_image = self.renderer.render_history(
                    enriched_history,
                    page,
                    total_pages,
                    total_records,
                    pool_name=pool_name_display,
                )

                # 发送图片
                import io

                from astrbot.core.message.components import Image

                img_byte_arr = io.BytesIO()
                rendered_image.save(img_byte_arr, format="PNG")
                img_byte_arr.seek(0)

                yield event.chain_result([Image.fromBytes(img_byte_arr.getvalue())])
                return

            # 格式化抽卡记录
            result_text = f"您的历史抽卡记录 (第 {page}/{total_pages} 页，共 {total_records} 条):\n\n"

            for record in pull_history:
                # 格式化稀有度显示
                rarity_display = (
                    "★★★★★"
                    if record["rarity"] == "5star"
                    else "★★★★"
                    if record["rarity"] == "4star"
                    else "★★★"
                )
                # 格式化时间
                pull_time = record["pull_time"]
                # 构建记录行
                result_text += f"{rarity_display} {record['item']} - {pull_time}\n"

            # 添加分页提示
            if total_pages > 1:
                result_text += (
                    f"\n使用 `/抽卡记录 {page + 1}` 查看下一页"
                    if page < total_pages
                    else "\n已经是最后一页"
                )
                if page > 1:
                    result_text += f"，使用 `/抽卡记录 {page - 1}` 查看上一页"

            yield event.plain_result(result_text)

        except Exception as e:
            logger.error(f"查看抽卡历史记录失败: {e}")
            yield event.plain_result(
                "查看抽卡历史记录时发生错误，请检查插件配置或联系管理员。"
            )

    @filter.command("卡池详细")
    async def pool_detail(self, event: AstrMessageEvent, pool_identifier: str):
        """
        查询指定卡池的详细配置信息
        
        参数:
            event: 消息事件对象
            pool_identifier: 卡池ID或名称
        """
        try:
            # 查找匹配的卡池配置
            target_config = None
            
            # 尝试通过 cp_id (UUID) 查找
            try:
                target_config = self.cp_manager.get_config_by_cp_id(pool_identifier)
            except KeyError:
                pass

            # 尝试通过相对路径精确匹配
            if target_config is None:
                try:
                    target_config = self.cp_manager.get_config(pool_identifier)
                except KeyError:
                    pass

            # 尝试通过卡池显示名称匹配
            if target_config is None:
                matched_configs = self.cp_manager.get_config_by_name(pool_identifier)
                if matched_configs:
                    if len(matched_configs) == 1:
                        target_config = matched_configs[0]
                    else:
                        # 多个匹配，提示用户更精确
                        names = [c.name for c in matched_configs]
                        yield event.plain_result(f"找到多个匹配的卡池: {', '.join(names)}，请使用更精确的名称或ID。")
                        return

            if target_config is None:
                yield event.plain_result(f"未找到匹配的卡池: {pool_identifier}")
                return

            if not self.enable_rendering:
                yield event.plain_result("未启用渲染功能，无法生成卡池详情图。")
                return

            # 渲染详情图
            image = self.renderer.render_pool_detail(target_config)
            
            # 发送图片
            import io
            from astrbot.core.message.components import Image as AstrImage
            
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format="PNG")
            img_byte_arr.seek(0)
            
            yield event.chain_result([AstrImage.fromBytes(img_byte_arr.getvalue())])
            
        except Exception as e:
            logger.error(f"查询卡池详情失败: {e}")
            yield event.plain_result(f"查询失败: {e}")

    async def terminate(self):
        """
        插件销毁方法，在插件卸载时调用
        """
        logger.info("鸣潮模拟抽卡插件已卸载")
