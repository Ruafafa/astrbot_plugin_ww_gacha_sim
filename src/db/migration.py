"""
数据库迁移模块

负责在插件升级时执行数据迁移，确保旧数据库与新代码兼容。
迁移策略：每次升级检查 schema_version，按顺序执行未完成的迁移。
"""

from astrbot.api import logger

from ..db.item_db_operations import ItemDBOperations
from ..gacha.cardpool_manager import CardPoolManager
from ..item_data.item_manager import ItemManager
from .database import CommonDatabase


def run_migrations(
    db: CommonDatabase,
    idb_ops: ItemDBOperations,
    item_manager: ItemManager,
    cp_manager: CardPoolManager,
):
    """检查当前数据库版本并执行所有待处理的迁移。"""
    current_version = db.get_schema_version()
    target_version = CommonDatabase.SCHEMA_VERSION

    if current_version >= target_version:
        logger.info(f"数据库已是当前版本 (v{target_version})，无需迁移")
        return

    logger.info(
        f"检测到数据库版本 v{current_version}，开始升级到 v{target_version} ..."
    )

    for version in range(current_version + 1, target_version + 1):
        _run_single_migration(version, db, idb_ops, item_manager, cp_manager)
        db.set_schema_version(version)
        logger.info(f"数据库已升级到 v{version}")

    logger.info(f"数据库迁移完成（v{current_version} → v{target_version}）")


def _run_single_migration(
    version: int,
    db: CommonDatabase,
    idb_ops: ItemDBOperations,
    item_manager: ItemManager,
    cp_manager: CardPoolManager,
):
    """执行单个版本的迁移逻辑。"""
    if version == 1:
        _migrate_v1(idb_ops, item_manager, cp_manager)
        return
    logger.warning(f"未知的迁移版本 v{version}，跳过")


def _migrate_v1(
    idb_ops: ItemDBOperations,
    item_manager: ItemManager,
    cp_manager: CardPoolManager,
):
    """v1 迁移：同步新增物品和预置卡池配置。"""
    logger.info("正在执行 v1 迁移：同步物品数据和预置配置...")

    # 1. 同步物品：将 CSV 中有而数据库表中没有的新物品插入
    table_name = item_manager.table_name
    added = idb_ops.sync_new_items_from_csv(table_name)
    if added > 0:
        # 刷新 ItemManager 内存缓存
        item_manager._item_details = idb_ops.load_all_items(table_name)

    # 2. 同步预置卡池配置：将 presets 中新增的 .json 复制到配置目录
    cp_manager.sync_new_presets()
