import asyncio
import hashlib
import io
import threading
import time
from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools
from astrbot.core.message.components import Image

from .src.db.database import CommonDatabase
from .src.db.gacha_db_operations import GachaDBOperations
from .src.db.item_db_operations import ItemDBOperations
from .src.gacha.cardpool_manager import CardPoolConfig, CardPoolManager
from .src.gacha.gacha_flow import GachaFlow
from .src.gacha.gacha_mechanics import GachaMechanics
from .src.item_data.item_manager import ItemManager
from .src.db.migration import run_migrations
from .src.render.gacha_renderer import GachaRenderer
from .src.render.local_file_cache_manager import LocalFileCacheManager
from .src.render.proxy_config import ProxyConfig
from .src.render.resource_loader import ResourceLoader
from .src.render.ui_resources_manager import UIResourceManager
from .src.web.server import stop_server, run as run_webui, run_async as run_webui_async, stop_server_async


class WutheringWavesGachaPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)

        self.config = config

        self.cdb = CommonDatabase()
        self.gdb_ops = GachaDBOperations(self.cdb)
        self.idb_ops = ItemDBOperations(self.cdb)
        self.item_manager = ItemManager(self.idb_ops)

        self.enable_rendering = self.config.get("enable_rendering", True)

        proxy_url = self.config.get("proxy_url", "")
        enable_proxy = self.config.get("enable_proxy", False)
        if not enable_proxy:
            proxy_url = None
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

        self.gacha_mechanics = GachaMechanics(self.item_manager)
        self.cp_manager = CardPoolManager()

        self.save_rendered_results = self.config.get("save_rendered_results", False)

        # 数据库迁移：确保升级后数据兼容
        try:
            run_migrations(
                self.cdb, self.idb_ops, self.item_manager, self.cp_manager
            )
        except Exception as e:
            logger.error(f"数据库迁移失败（非致命错误）: {e}")

        # WebUI 自动启动
        self._webui_thread = None
        self._webui_task = None
        if self.config.get("enable_webui", False):
            webui_port = int(self.config.get("webui_port", 5000))
            logger.info(f"WebUI 配置已启用，正在启动 (0.0.0.0:{webui_port})...")
            try:
                # 优先使用 asyncio 任务（主事件循环），避免线程下
                # signal.set_wakeup_fd / add_signal_handler 的限制
                try:
                    loop = asyncio.get_running_loop()
                    self._webui_task = loop.create_task(
                        run_webui_async(host="0.0.0.0", port=webui_port, debug=False)
                    )
                    logger.info(f"WebUI 已通过 asyncio 任务启动 (0.0.0.0:{webui_port})")
                except RuntimeError:
                    # 没有运行中的事件循环，回退到线程方式
                    self._webui_thread = threading.Thread(
                        target=run_webui,
                        kwargs={"host": "0.0.0.0", "port": webui_port, "debug": False},
                        daemon=True,
                    )
                    self._webui_thread.start()
                    logger.info(f"WebUI 已通过后台线程启动 (0.0.0.0:{webui_port})")
            except Exception as e:
                logger.error(f"WebUI 后台服务启动失败: {e}")
        else:
            logger.info("WebUI 未启用 (enable_webui=False)")

        logger.info("鸣潮模拟抽卡插件已初始化")

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _user_kv_key(sender_id: str) -> str:
        return f"user_default_pool_{hashlib.md5(sender_id.encode()).hexdigest()[:8]}"

    def _save_rendered_image(self, image, user_id: str):
        if not self.save_rendered_results:
            return
        try:
            output_path = (
                Path(StarTools.get_data_dir("astrbot_plugin_ww_gacha_sim"))
                / "rendered_results"
            )
            output_path.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time())
            filename = f"gacha_result_{user_id}_{timestamp}.png"
            file_path = output_path / filename
            image.save(file_path, format="PNG")
            logger.info(f"已保存抽卡结果图片: {file_path}")
        except Exception as e:
            logger.error(f"保存抽卡结果图片失败: {e}")

    @staticmethod
    def _image_as_chain(image) -> list:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)
        return [Image.fromBytes(buf.getvalue())]

    @staticmethod
    def _rarity_stars(rarity: str) -> str:
        return (
            "★★★★★"
            if rarity == "5star"
            else "★★★★"
            if rarity == "4star"
            else "★★★"
        )

    def _find_pool_config(self, pool_identifier: str) -> CardPoolConfig | list[CardPoolConfig] | None:
        """查找卡池配置，返回 None 表示未找到，返回 list 表示多个重名结果"""
        matched = self.cp_manager.get_config_by_name(pool_identifier)
        if len(matched) > 1:
            return matched
        if len(matched) == 1:
            return matched[0]
        return self.cp_manager.find_config_by_identifier(pool_identifier)

    async def _resolve_pool_config(self, event, pool_identifier: str):
        sender_id = str(event.get_sender_id())
        kv_key = self._user_kv_key(sender_id)
        config_ids = self.cp_manager.get_config_ids()

        if not config_ids:
            return None, event.plain_result("当前没有可用的卡池配置，请先创建卡池配置文件。")

        if pool_identifier == "":
            saved_cp_id = await self.get_kv_data(kv_key, default=None)
            if saved_cp_id and saved_cp_id in config_ids:
                pool_identifier = saved_cp_id
            else:
                pool_identifier = config_ids[0]
                if saved_cp_id and saved_cp_id not in config_ids:
                    await self.delete_kv_data(kv_key)
                    logger.info(
                        f"用户 {sender_id} 的默认卡池 {saved_cp_id} 不存在，已清理"
                    )

        target_config = self.cp_manager.find_config_by_identifier(pool_identifier)

        if target_config is None:
            pool_list = "找不到指定的卡池。可用的卡池有：\n"
            for i, cp_id in enumerate(config_ids, 1):
                try:
                    config = self.cp_manager.get_config_by_cp_id(cp_id)
                    if config.enable:
                        pool_list += f"{i}. {config.name} - ID: {config.cp_id}\n"
                except Exception as e:
                    logger.warning(f"获取卡池 {cp_id} 详情失败: {e}")
                    pool_list += f"{i}. {cp_id} (获取详情失败)\n"
            return None, event.plain_result(pool_list)

        if not target_config.enable:
            return None, event.plain_result(
                f"卡池「{target_config.name}」已被禁用，无法进行抽卡。"
            )

        return target_config, None

    # ------------------------------------------------------------------
    # 命令处理器
    # ------------------------------------------------------------------

    @filter.command("单抽", alias={"单次抽卡", "抽卡", "单次唤取"})
    async def single_pull(self, event: AstrMessageEvent, pool_identifier: str = ""):
        try:
            target_config, error_msg = await self._resolve_pool_config(
                event, pool_identifier
            )
            if error_msg:
                yield error_msg
                return

            sender_id = str(event.get_sender_id())
            gacha_flow = GachaFlow(sender_id, self.gdb_ops, self.item_manager)
            pull_result = gacha_flow.single_pull(target_config)
            item_obj = pull_result.get("item_obj")

            if not item_obj:
                yield event.plain_result("抽卡过程中出现错误，未能获得有效物品。")
                return

            if self.enable_rendering:
                sender_name = (
                    event.get_sender_name()
                    if hasattr(event, "get_sender_name")
                    else "未知用户"
                )
                rendered_image = await asyncio.to_thread(
                    self.renderer.render_single_pull,
                    item_obj,
                    nickname=sender_name,
                    user_id=sender_id,
                )
                self._save_rendered_image(rendered_image, sender_id)
                yield event.chain_result(self._image_as_chain(rendered_image))
            else:
                yield event.plain_result(
                    f"单次抽卡结果：\n{self._rarity_stars(item_obj.rarity)} {item_obj.name}"
                )

        except Exception as e:
            logger.error(f"单次抽卡失败: {e}")
            yield event.plain_result("单次抽卡时发生错误，请检查插件配置或联系管理员。")

    @filter.command("十抽", alias={"十连", "10抽", "10连"})
    async def ten_pulls(self, event: AstrMessageEvent, pool_identifier: str = ""):
        try:
            target_config, error_msg = await self._resolve_pool_config(
                event, pool_identifier
            )
            if error_msg:
                yield error_msg
                return

            sender_id = str(event.get_sender_id())
            gacha_flow = GachaFlow(sender_id, self.gdb_ops, self.item_manager)
            item_objs = gacha_flow.ten_consecutive_pulls(target_config)

            if not item_objs:
                yield event.plain_result("抽卡过程中出现错误，未能获得有效物品。")
                return

            if self.enable_rendering:
                sender_name = (
                    event.get_sender_name()
                    if hasattr(event, "get_sender_name")
                    else "未知用户"
                )
                rendered_image = await asyncio.to_thread(
                    self.renderer.render_ten_pulls,
                    item_objs,
                    nickname=sender_name,
                    user_id=sender_id,
                )
                self._save_rendered_image(rendered_image, sender_id)
                yield event.chain_result(self._image_as_chain(rendered_image))
            else:
                lines = ["十连抽卡结果："]
                for idx, obj in enumerate(item_objs, 1):
                    lines.append(f"{idx}. {self._rarity_stars(obj.rarity)} {obj.name}")
                yield event.plain_result("\n".join(lines))

        except Exception as e:
            logger.error(f"十连抽卡失败: {e}")
            yield event.plain_result("十连抽卡时发生错误，请检查插件配置或联系管理员。")

    @filter.command("卡池", alias={"卡池列表", "查看卡池"})
    async def list_card_pools(self, event: AstrMessageEvent):
        try:
            config_ids = self.cp_manager.get_config_ids()
            if not config_ids:
                yield event.plain_result("当前没有可用的卡池配置，请先创建卡池配置文件。")
                return

            lines = ["当前可用的卡池："]
            for i, cp_id in enumerate(config_ids, 1):
                try:
                    config = self.cp_manager.get_config_by_cp_id(cp_id)
                    if config.enable:
                        lines.append(
                            f"{i}. {config.name} - ID: {config.cp_id}"
                        )
                except Exception as e:
                    logger.warning(f"获取卡池 {cp_id} 详情失败: {e}")
                    lines.append(f"{i}. {cp_id} (获取详情失败)")

            lines.append("使用 `/单抽 <卡池ID或名称>` 命令开始抽卡。")
            yield event.plain_result("\n".join(lines))

        except Exception as e:
            logger.error(f"获取卡池列表失败: {e}")
            yield event.plain_result("获取卡池列表时发生错误，请检查插件配置或联系管理员。")

    @filter.command("唤取", alias={"选抽", "设置卡池", "选择卡池"})
    async def set_default_pool(
        self, event: AstrMessageEvent, pool_identifier: str = "examples/默认卡池"
    ):
        try:
            if not pool_identifier:
                yield event.plain_result("请指定要设置的卡池名称。使用方法：/唤取 <卡池名称>")
                return

            config_ids = self.cp_manager.get_config_ids()
            if not config_ids:
                yield event.plain_result("当前没有可用的卡池配置，请先创建卡池配置文件。")
                return

            found = self._find_pool_config(pool_identifier)
            if isinstance(found, list):
                lines = [f"找到 {len(found)} 个名为「{pool_identifier}」的卡池，请选择："]
                for i, c in enumerate(found, 1):
                    lines.append(f"{i}. {c.name} (ID: {c.cp_id})")
                lines.append("请使用 `/唤取 <卡池ID>` 来指定具体卡池。")
                yield event.plain_result("\n".join(lines))
                return

            if found is None:
                lines = ["找不到指定的卡池。可用的卡池有："]
                for i, cp_id in enumerate(config_ids, 1):
                    try:
                        config = self.cp_manager.get_config_by_cp_id(cp_id)
                        if config.enable:
                            lines.append(
                                f"{i}. {config.name} - ID: {config.cp_id}"
                            )
                    except Exception as e:
                        logger.warning(f"获取卡池 {cp_id} 详情失败: {e}")
                        lines.append(f"{i}. {cp_id} (获取详情失败)")
                yield event.plain_result("\n".join(lines))
                return

            if not found.enable:
                yield event.plain_result(
                    f"卡池「{found.name}」已被禁用，无法设置为默认卡池。"
                )
                return

            sender_id = str(event.get_sender_id())
            kv_key = self._user_kv_key(sender_id)
            await self.put_kv_data(kv_key, found.cp_id)

            yield event.plain_result(
                f"已设置您的默认卡池为：{found.name} (ID: {found.cp_id})\n现在您可以使用 `/抽卡` 命令进行抽卡，将默认使用此卡池。"
            )

        except Exception as e:
            logger.error(f"设置默认卡池失败: {e}")
            yield event.plain_result("设置默认卡池时发生错误，请检查插件配置或联系管理员。")

    @filter.command("唤取记录", alias={"抽卡记录", "查看抽卡", "抽卡历史"})
    async def view_pull_history(
        self, event: AstrMessageEvent, page_or_pool: str = "1"
    ):
        try:
            sender_id = str(event.get_sender_id())
            page_size = 10
            page = 1
            pool_identifier = None
            pool_id = None
            pool_name_display = "全部卡池"

            try:
                page = int(page_or_pool)
            except ValueError:
                pool_identifier = page_or_pool
                if pool_identifier:
                    config_ids = self.cp_manager.get_config_ids()
                    if not config_ids:
                        yield event.plain_result(
                            "当前没有可用的卡池配置，请先创建卡池配置文件。"
                        )
                        return

                    found = self._find_pool_config(pool_identifier)
                    if isinstance(found, list):
                        lines = [
                            f"找到 {len(found)} 个名为「{pool_identifier}」的卡池，请选择："
                        ]
                        for i, c in enumerate(found, 1):
                            lines.append(f"{i}. {c.name} - ID: {c.cp_id}")
                        lines.append(
                            "请使用 `/抽卡记录 <卡池ID>` 来指定具体卡池。"
                        )
                        yield event.plain_result("\n".join(lines))
                        return
                    if found is not None:
                        pool_id = found.cp_id
                        pool_name_display = found.name
                    else:
                        lines = [
                            f"找不到指定的卡池: {pool_identifier}\n\n可用的卡池有："
                        ]
                        for i, cp_id in enumerate(config_ids, 1):
                            try:
                                config = self.cp_manager.get_config_by_cp_id(cp_id)
                                if config.enable:
                                    lines.append(
                                        f"{i}. {config.name} - ID: {cp_id}"
                                    )
                            except Exception as e:
                                logger.warning(f"获取卡池 {cp_id} 详情失败: {e}")
                                lines.append(f"{i}. {cp_id} (获取详情失败)")
                        yield event.plain_result("\n".join(lines))
                        return

            offset = (page - 1) * page_size
            pull_history = self.gdb_ops.load_pull_history(
                user_id=sender_id,
                limit=page_size,
                offset=offset,
                order="desc",
                pool_id=pool_id,
            )

            total_records = self.gdb_ops.get_pull_history_count(
                sender_id, pool_id=pool_id
            )
            total_pages = (total_records + page_size - 1) // page_size

            if total_records == 0:
                yield event.plain_result(
                    "您在该卡池还没有任何抽卡记录。"
                    if pool_identifier
                    else "您还没有任何抽卡记录。"
                )
                return

            if page < 1 or page > total_pages:
                yield event.plain_result(
                    f"页码超出范围。当前共有 {total_records} 条记录，分为 {total_pages} 页。"
                )
                return

            if self.enable_rendering:
                all_items = self.item_manager.get_all_items()
                name_to_type = {
                    d["name"]: d["type"] for d in all_items.values()
                }
                enriched_history = []
                for record in pull_history:
                    r = record.copy()
                    r["type"] = name_to_type.get(record["item"], "unknown")
                    enriched_history.append(r)

                rendered_image = await asyncio.to_thread(
                    self.renderer.render_history,
                    enriched_history,
                    page,
                    total_pages,
                    total_records,
                    pool_name=pool_name_display,
                )
                yield event.chain_result(self._image_as_chain(rendered_image))
                return

            lines = [
                f"您的历史抽卡记录 (第 {page}/{total_pages} 页，共 {total_records} 条):\n"
            ]
            for record in pull_history:
                lines.append(
                    f"{self._rarity_stars(record['rarity'])} {record['item']} - {record['pull_time']}"
                )
            if total_pages > 1:
                if page < total_pages:
                    lines.append(f"\n使用 `/抽卡记录 {page + 1}` 查看下一页")
                else:
                    lines.append("\n已经是最后一页")
                if page > 1:
                    lines.append(f"使用 `/抽卡记录 {page - 1}` 查看上一页")

            yield event.plain_result("\n".join(lines))

        except Exception as e:
            logger.error(f"查看抽卡历史记录失败: {e}")
            yield event.plain_result(
                "查看抽卡历史记录时发生错误，请检查插件配置或联系管理员。"
            )

    @filter.command("卡池详细")
    async def pool_detail(
        self, event: AstrMessageEvent, pool_identifier: str
    ):
        try:
            found = self._find_pool_config(pool_identifier)
            if isinstance(found, list):
                names = [c.name for c in found]
                yield event.plain_result(
                    f"找到多个匹配的卡池: {', '.join(names)}，请使用更精确的名称或ID。"
                )
                return
            if found is None:
                yield event.plain_result(
                    f"未找到匹配的卡池: {pool_identifier}"
                )
                return

            if not self.enable_rendering:
                yield event.plain_result("未启用渲染功能，无法生成卡池详情图。")
                return

            image = await asyncio.to_thread(
                self.renderer.render_pool_detail, found
            )
            yield event.chain_result(self._image_as_chain(image))

        except Exception as e:
            logger.error(f"查询卡池详情失败: {e}")
            yield event.plain_result(f"查询失败: {e}")

    @filter.command("重载卡池", alias={"刷新卡池", "reload_pools"})
    async def reload_pools(self, event: AstrMessageEvent):
        try:
            configs = self.cp_manager.reload_all()
            yield event.plain_result(f"已重新加载 {len(configs)} 个卡池配置。")
        except Exception as e:
            logger.error(f"重载卡池配置失败: {e}")
            yield event.plain_result("重载卡池配置时发生错误。")

    @filter.command("wgs_help", alias={"抽卡帮助", "鸣潮帮助"})
    async def wgs_help(self, event: AstrMessageEvent):
        try:
            from astrbot.core.star.star_handler import star_handlers_registry
            from astrbot.core.star.filter.command import CommandFilter

            handlers = star_handlers_registry.get_handlers_by_module_name(
                self.__module__
            )

            lines = ["鸣潮模拟抽卡插件 - 可用命令：\n"]
            parts = []

            for handler in handlers:
                for f in handler.event_filters:
                    if not isinstance(f, CommandFilter):
                        continue
                    names = f.get_complete_command_names()
                    if not names:
                        continue
                    primary = names[0]
                    aliases = [n for n in names[1:] if n != primary][:3]
                    desc = handler.desc or "无说明"
                    alias_str = (
                        f"（{'/'.join(aliases)}）" if aliases else ""
                    )
                    parts.append(f"  /{primary} {alias_str}\n    {desc}")

            parts.sort()
            lines.extend(parts)

            yield event.plain_result("\n".join(lines))
        except Exception as e:
            logger.error(f"获取帮助失败: {e}")
            yield event.plain_result("获取帮助信息时发生错误。")

    async def terminate(self):
        if self._webui_task:
            logger.info("正在停止 WebUI (asyncio 任务)...")
            await stop_server_async()
            try:
                await asyncio.wait_for(self._webui_task, timeout=10)
            except asyncio.TimeoutError:
                logger.warning("WebUI 关闭超时，强制取消任务")
                self._webui_task.cancel()
                try:
                    await self._webui_task
                except asyncio.CancelledError:
                    pass
            except asyncio.CancelledError:
                pass
            self._webui_task = None
        if self._webui_thread and self._webui_thread.is_alive():
            logger.info("正在停止 WebUI (后台线程)...")
            stop_server()
            self._webui_thread = None
        logger.info("鸣潮模拟抽卡插件已卸载")
