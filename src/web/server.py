import argparse
import asyncio
import json
import os
import signal
import sys
import threading
import uuid
import webbrowser
from contextlib import contextmanager
from threading import Timer
from typing import Any

import httpx
from quart import Quart, Response, jsonify, make_response, request, send_from_directory

from astrbot.api import logger

# 导入数据库操作类
from ..db.database import CommonDatabase
from ..db.item_db_operations import ItemDBOperations
from ..gacha.cardpool_manager import CardPoolManager

# 创建数据库实例
db = CommonDatabase()
item_ops = ItemDBOperations(db)

# 创建卡池配置管理器
# 不传递参数，使用 CardPoolManager 内部定义的默认路径 (StarTools.get_data_dir)
cp_manager = CardPoolManager()
DEFAULT_CONFIG_DIR = cp_manager.config_dir

app = Quart(__name__)

# 配置
app.config["DEBUG"] = False  # 默认关闭调试模式，使用 --debug 参数启用


# 处理 CORS（前端与后端同源时不需要，但为开发环境保留）
@app.after_request
async def add_cors_headers(response):
    origin = request.headers.get("Origin", "")
    if app.config["DEBUG"]:
        # 调试模式允许所有来源
        response.headers["Access-Control-Allow-Origin"] = "*"
    elif origin and (
        origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1")
    ):
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        response.headers["Access-Control-Allow-Origin"] = "http://localhost"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


# 配置文件管理
@app.route("/api/configs/directory", methods=["GET", "POST"])
async def config_directory() -> Response:
    """
    配置目录管理接口
    GET: 获取当前默认配置目录
    POST: 验证并返回请求的配置目录

    Returns:
        Response: JSON格式的响应数据
            - success: 操作是否成功
            - directory: 目录路径 (成功时)
            - message: 错误信息 (失败时)
    """
    if request.method == "POST":
        try:
            data = await request.get_json() or {}
            config_dir = data.get("directory")

            if config_dir and os.path.exists(config_dir):
                return jsonify({"success": True, "directory": config_dir})
            return jsonify({"success": False, "message": "目录不存在"})
        except Exception as e:
            logger.error(f"配置目录请求失败: {e}")
            return jsonify({"success": False, "message": f"请求失败: {str(e)}"})

    # 获取配置目录
    return jsonify({"directory": str(DEFAULT_CONFIG_DIR)})


@app.route("/api/configs/list", methods=["GET"])
async def config_list() -> Response:
    # 获取配置文件列表
    config_dir = request.args.get("directory", str(DEFAULT_CONFIG_DIR))

    if not os.path.exists(config_dir):
        return jsonify({"success": False, "message": "目录不存在"})

    configs = []

    # 深度扫描配置目录及其子目录
    for root, dirs, files in os.walk(config_dir):
        for file in files:
            if file.endswith(".json"):
                # 跳过文件名为 .json 的配置文件
                if file == ".json":
                    continue

                file_path = os.path.join(root, file)
                try:
                    with open(file_path, encoding="utf-8") as f:
                        config = json.load(f)

                    # 计算相对于配置目录的路径
                    rel_path = os.path.relpath(file_path, config_dir)
                    filename = rel_path[:-5]  # 移除.json后缀
                    filename = filename.replace("\\", "/")  # 统一路径分隔符

                    configs.append({"filename": filename, "content": config})
                except Exception:
                    continue

    return jsonify({"success": True, "configs": configs})


@app.route("/api/configs/<path:filename>", methods=["GET", "POST", "DELETE", "PUT"])
async def config_file(filename: str) -> Response:
    config_dir = request.args.get("directory", str(DEFAULT_CONFIG_DIR))

    # 根据请求方法处理不同的逻辑
    if request.method == "GET":
        # 获取配置文件内容
        # 验证文件路径安全性，防止路径遍历攻击
        filename = (
            os.path.basename(filename)
            .replace("..", "")
            .replace("/", "")
            .replace("\\", "")
        )
        if not filename:
            return jsonify({"success": False, "message": "无效的文件名"})

        # 首先尝试直接路径
        file_path = os.path.join(config_dir, filename)

        # 如果文件不存在，尝试查找匹配的文件
        if not os.path.exists(file_path):
            found = False
            # 深度搜索配置目录
            for root, dirs, files in os.walk(config_dir):
                if filename in files:
                    file_path = os.path.join(root, filename)
                    found = True
                    break

            if not found:
                return jsonify({"success": False, "message": "文件不存在"})

        try:
            with open(file_path, encoding="utf-8") as f:
                config = json.load(f)
            return jsonify({"success": True, "content": config})
        except Exception as e:
            return jsonify({"success": False, "message": f"读取文件失败: {str(e)}"})

    elif request.method == "POST":
        # 创建或更新配置文件
        data = await request.get_json()
        content = data.get("content")

        # 获取 config_group，默认为 'default'
        config_group = content.get("config_group", "default") if content else "default"

        # 构建文件路径：根据 config_group 创建对应的子目录
        # 如果 filename 已经包含路径（如 default2/新配置.json），则使用该路径
        # 否则，将文件保存到 config_group 对应的子目录下
        if "/" in filename or "\\" in filename:
            # filename 已经包含路径，直接使用
            file_path = os.path.join(config_dir, filename)
        else:
            # filename 不包含路径，根据 config_group 创建子目录
            file_path = os.path.join(config_dir, config_group, filename)

        # 确保文件名有 .json 后缀
        if not file_path.endswith(".json"):
            file_path = file_path + ".json"

        try:
            # 创建必要的目录
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
            logger.info(f"配置文件已保存: {file_path}")
            return jsonify({"success": True, "message": "保存成功"})
        except Exception as e:
            logger.error(f"保存配置文件失败: {file_path} - {e}")
            return jsonify({"success": False, "message": f"保存失败: {str(e)}"})

    elif request.method == "PUT":
        # 启用或禁用配置
        data = await request.get_json()
        enable = data.get("enable", True)

        try:
            # 使用 CardPoolManager 来更新配置
            file_path_without_ext = (
                filename[:-5] if filename.endswith(".json") else filename
            )
            updated_config = cp_manager.set_config_enable(file_path_without_ext, enable)
            return jsonify(
                {
                    "success": True,
                    "message": f"已{'启用' if enable else '禁用'}配置",
                    "content": updated_config.to_dict(),
                }
            )
        except KeyError as e:
            return jsonify({"success": False, "message": str(e)})
        except Exception as e:
            return jsonify({"success": False, "message": f"操作失败: {str(e)}"})

    elif request.method == "DELETE":
        # 删除配置文件
        # 简单过滤 ../ 防止遍历上级目录
        filename = filename.replace("..", "")
        if not filename:
            return jsonify({"success": False, "message": "无效的文件名"})

        # 规范化路径分隔符
        filename = filename.replace("\\", "/")

        # 构建完整路径
        file_path = os.path.join(config_dir, filename)

        # 确保文件名有 .json 后缀
        if not file_path.endswith(".json"):
            file_path = file_path + ".json"

        # 检查文件是否存在
        if not os.path.exists(file_path):
            # 尝试深度搜索作为回退 (Backward compatibility)
            # 仅当文件名不包含路径分隔符时尝试搜索
            if "/" not in filename:
                found = False
                for root, dirs, files in os.walk(config_dir):
                    target = (
                        filename + ".json"
                        if not filename.endswith(".json")
                        else filename
                    )
                    if target in files:
                        file_path = os.path.join(root, target)
                        found = True
                        break
                if not found:
                    logger.warning(f"删除配置文件不存在: {file_path}")
                    return jsonify({"success": False, "message": "文件不存在"})
            else:
                logger.warning(f"删除配置文件不存在: {file_path}")
                return jsonify({"success": False, "message": "文件不存在"})

        try:
            os.remove(file_path)
            logger.info(f"配置文件已删除: {file_path}")
            return jsonify({"success": True, "message": "删除成功"})
        except Exception as e:
            logger.error(f"删除配置文件失败: {file_path} - {e}")
            return jsonify({"success": False, "message": f"删除失败: {str(e)}"})

    else:
        return jsonify({"success": False, "message": "不支持的请求方法"})


# 数据库与物品管理
@app.route("/api/db/items", methods=["GET", "POST", "PUT", "DELETE"])
async def items() -> Response:
    # 获取请求数据
    data = await request.get_json() if request.method in ["POST", "PUT"] else None

    # 确定config_group：优先使用请求体中的config_group，其次使用URL参数，默认使用default
    if request.method == "GET":
        config_group = request.args.get("config_group", "default")
    elif request.method == "POST":
        if isinstance(data, list):
            if len(data) > 0 and data[0] and "config_group" in data[0]:
                config_group = data[0]["config_group"]
            else:
                config_group = request.args.get("config_group", "default")
        elif data:
            config_group = data.get(
                "config_group", request.args.get("config_group", "default")
            )
        else:
            config_group = request.args.get("config_group", "default")
    elif request.method == "PUT":
        if data:
            config_group = data.get(
                "config_group", request.args.get("config_group", "default")
            )
        else:
            config_group = request.args.get("config_group", "default")
    elif request.method == "DELETE":
        # 删除操作时，需要先根据id获取物品，再确定其config_group
        # 检查是否是清空表的请求，如果是则跳过item_id检查
        if request.args.get("clear_all") != "true":
            item_id = request.args.get("external_id")
            if not item_id:
                return jsonify(
                    {"success": False, "message": "缺少物品ID (external_id)"}
                )

            # 尝试从所有可能的表中查找物品
            config_group = "default"  # 默认值
            found = False

            # 先尝试使用URL参数中的config_group
            if request.args.get("config_group"):
                temp_config_group = request.args.get("config_group")
                temp_table_name = f"{temp_config_group}_items"
                try:
                    items_list = item_ops.get_items_list(temp_table_name)
                    if items_list:
                        # 使用external_id查找
                        found = any(
                            str(item.get("external_id", "")) == item_id
                            for item in items_list
                        )
                        if found:
                            config_group = temp_config_group
                except Exception:
                    pass

            # 如果没找到，尝试从请求体中获取config_group
            if not found and data:
                temp_config_group = data.get("config_group")
                if temp_config_group:
                    temp_table_name = f"{temp_config_group}_items"
                    try:
                        items_list = item_ops.get_items_list(temp_table_name)
                        if items_list:
                            # 使用external_id查找
                            found = any(
                                str(item.get("external_id", "")) == item_id
                                for item in items_list
                            )
                            if found:
                                config_group = temp_config_group
                    except Exception:
                        pass
        else:
            # 清空表操作时，使用URL参数中的config_group
            config_group = request.args.get("config_group", "default")
    else:
        config_group = request.args.get("config_group", "default")

    table_name = f"{config_group}_items"

    # 记录导入操作日志
    import datetime

    log_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if request.method == "GET":
        # 获取物品列表
        try:
            items_list = item_ops.get_items_list(table_name)
            return jsonify({"success": True, "items": items_list})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})

    elif request.method == "POST":
        # 添加物品
        try:
            if isinstance(data, list):
                # 批量添加
                result = item_ops.add_items_batch(data, table_name)
                if result:
                    # 记录批量导入日志
                    print(
                        f"[IMPORT_LOG] [{log_time}] 批量导入: 成功添加 {len(data)} 个物品到表 {table_name}"
                    )
                    return jsonify(
                        {"success": True, "message": f"成功添加 {len(data)} 个物品"}
                    )
                else:
                    return jsonify({"success": False, "message": "批量添加物品失败"})
            else:
                # 单个添加
                if data:
                    result = item_ops.add_item(data, table_name)
                    if result:
                        # 记录单个导入日志
                        print(
                            f"[IMPORT_LOG] [{log_time}] 单个导入: 成功添加物品 {data.get('name', '未知')} 到表 {table_name}"
                        )
                        # 获取刚添加的物品ID
                        items_list = item_ops.get_items_list(table_name)
                        item_id = items_list[-1]["external_id"] if items_list else 1
                        return jsonify({"success": True, "item_id": item_id})
                    else:
                        return jsonify({"success": False, "message": "添加物品失败"})
                else:
                    return jsonify({"success": False, "message": "缺少物品数据"})
        except Exception as e:
            print(f"[IMPORT_LOG] [{log_time}] 添加物品失败: {str(e)}")
            return jsonify({"success": False, "message": str(e)})

    elif request.method == "PUT":
        # 更新物品
        try:
            if not data:
                return jsonify({"success": False, "message": "缺少请求数据"})

            # 处理 data 可能是列表或字典的情况
            if isinstance(data, list):
                if not data or not data[0]:
                    return jsonify({"success": False, "message": "缺少请求数据"})
                item_id = str(data[0].get("external_id", ""))
                if not item_id:
                    return jsonify(
                        {"success": False, "message": "缺少物品ID (external_id)"}
                    )
                # 移除external_id字段，只保留要更新的字段
                update_data = {k: v for k, v in data[0].items() if k != "external_id"}
            else:
                item_id = str(data.get("external_id", ""))
                if not item_id:
                    return jsonify(
                        {"success": False, "message": "缺少物品ID (external_id)"}
                    )
                # 移除external_id字段，只保留要更新的字段
                update_data = {k: v for k, v in data.items() if k != "external_id"}

            result = item_ops.update_item(
                item_id,
                update_data,
                table_name,
                update_configs=True,
                config_manager=cp_manager,
            )
            if result:
                print(
                    f"[IMPORT_LOG] [{log_time}] 更新物品: 成功更新物品 {item_id} 到表 {table_name}"
                )
            return jsonify({"success": result})
        except Exception as e:
            print(f"[IMPORT_LOG] [{log_time}] 更新物品失败: {str(e)}")
            return jsonify({"success": False, "message": str(e)})

    elif request.method == "DELETE":
        # 删除物品
        try:
            # 检查是否是清空表的请求
            if request.args.get("clear_all") == "true":
                # 暂时使用 clear_table 方法，因为 clear_table_with_transaction 可能未被类型检查器识别
                result = item_ops.clear_table(table_name)
                if result:
                    print(f"[IMPORT_LOG] [{log_time}] 清空表: 成功清空表 {table_name}")
                else:
                    print(f"[IMPORT_LOG] [{log_time}] 清空表失败: {table_name}")
                return jsonify({"success": result})
            else:
                # 单个或批量删除物品
                # 支持多种删除方式：通过ID列表、通过ID单个
                item_ids = None

                # 方式1: 从URL参数获取单个ID
                url_id = request.args.get("external_id") or request.args.get("id")
                if url_id:
                    item_ids = [str(url_id)]

                # 方式2: 从URL参数获取ID列表
                if not item_ids:
                    url_ids = request.args.get("ids")
                    if url_ids:
                        # 支持逗号分隔的ID列表
                        if isinstance(url_ids, str):
                            item_ids = [
                                id.strip() for id in url_ids.split(",") if id.strip()
                            ]
                        elif isinstance(url_ids, list):
                            item_ids = url_ids

                # 方式3: 从请求体获取ID列表
                if not item_ids and data:
                    if isinstance(data, list) and len(data) > 0:
                        # 检查第一个元素是否是ID列表
                        if "ids" in data[0]:
                            item_ids = data[0]["ids"]
                            # 支持逗号分隔的ID字符串
                            if isinstance(item_ids, str):
                                item_ids = [
                                    id.strip()
                                    for id in item_ids.split(",")
                                    if id.strip()
                                ]
                            elif isinstance(item_ids, list):
                                item_ids = item_ids

                # 方式4: 从请求体获取单个ID
                if not item_ids and data:
                    if isinstance(data, dict) and "id" in data:
                        item_ids = [str(data["id"])]

                # 如果没有提供任何ID，返回错误
                if not item_ids:
                    print(f"[IMPORT_LOG] [{log_time}] 删除物品失败: 缺少物品ID")
                    return jsonify({"success": False, "message": "缺少物品ID"})

                # 执行删除操作
                deleted_count = 0
                failed_ids = []

                for item_id in item_ids:
                    result = item_ops.delete_item(
                        item_id,
                        table_name,
                        update_configs=True,
                        config_manager=cp_manager,
                    )
                    if result:
                        deleted_count += 1
                        print(
                            f"[IMPORT_LOG] [{log_time}] 删除物品: 成功删除物品 {item_id} 从表 {table_name}"
                        )
                    else:
                        failed_ids.append(item_id)
                        print(
                            f"[IMPORT_LOG] [{log_time}] 删除物品失败: {item_id} 从表 {table_name}"
                        )

                # 返回结果
                if deleted_count > 0:
                    return jsonify(
                        {"success": True, "message": f"成功删除 {deleted_count} 个物品"}
                    )
                elif failed_ids:
                    return jsonify(
                        {
                            "success": False,
                            "message": f"删除失败 {len(failed_ids)} 个物品，失败的ID: {', '.join(failed_ids)}",
                        }
                    )
                else:
                    return jsonify({"success": False, "message": "没有物品被删除"})
        except Exception as e:
            print(f"[IMPORT_LOG] [{log_time}] 删除物品失败: {str(e)}")
            return jsonify({"success": False, "message": str(e)})
    else:
        return jsonify({"success": False, "message": "不支持的请求方法"})


# 库街区Wiki同步
KUROBBS_API_BASE = "https://api.kurobbs.com"
WIKI_CATALOGUES = {"1105": "character", "1106": "weapon"}

# 中文字段名 → 英文类型标识（供前端及CSV使用）
_ZH_TO_EN = {
    # 元素属性
    "气动": "aero",
    "导电": "electro",
    "冷凝": "glacio",
    "热熔": "fusion",
    "衍射": "spectro",
    "湮灭": "havoc",
    # 武器类型
    "长刃": "broadblade",
    "臂铠": "gauntlets",
    "迅刀": "sword",
    "佩枪": "pistols",
    "音感仪": "rectifier",
}


def _generate_devcode() -> str:
    """生成类似 Kurobbs 前端的 devcode（32位hex）"""
    return uuid.uuid4().hex[:32]


def _parse_detail_item(
    data: dict, catalogue_id: str, portrait_fallback: str = "", star_fallback: str = "4"
) -> dict | None:
    """
    解析 getEntryDetail 返回的 data，提取物品信息。

    角色（catalogue 1105）：从 role-component → role.figures[] 取高清立绘，
    从 role.info 中解析"属性：XXX"映射为英文类型标识。

    武器（catalogue 1106）：从 modules[0] → components[0]
    (tabs-component) 的 HTML 表格中提取第一个 <img> 作为立绘，
    从"武器类型"行提取武器类型。

    返回 None 表示无法解析（如 title 为空）。
    """
    import re as _re

    content = data.get("content", {})
    title = content.get("title", "")
    if not title:
        return None

    star = str(content.get("star", star_fallback))
    modules = content.get("modules", [])

    item_type = WIKI_CATALOGUES.get(catalogue_id, "unknown")
    affiliated_type = ""
    portrait_url = content.get("contentUrl", portrait_fallback)

    for module in modules:
        for comp in module.get("components", []):
            comp_type = comp.get("type", "")

            if comp_type == "role-component":
                role = comp.get("role", {})
                item_type = "character"

                figures = role.get("figures", [])
                if figures and figures[0].get("url"):
                    portrait_url = figures[0]["url"]
                elif not portrait_url:
                    portrait_url = role.get("backgroundImage", "")

                for info_item in role.get("info", []):
                    text = info_item.get("text", "")
                    if text.startswith("属性："):
                        cn = text[len("属性：") :]
                        affiliated_type = _ZH_TO_EN.get(cn, cn)

            # 武器：从 modules[0] → components[0] (tabs-component) 的 HTML 中解析
            if catalogue_id == "1106" and not affiliated_type:
                if modules and modules[0].get("components"):
                    first_comp = modules[0]["components"][0]
                    if first_comp.get("type") == "tabs-component":
                        html = first_comp.get("content", "")
                        if not html:
                            continue
                        # 第一个 img src 即为武器立绘
                        if not portrait_url or portrait_url == portrait_fallback:
                            m = _re.search(r'<img[^>]+src="([^"]+)"', html)
                            if m:
                                portrait_url = m.group(1)
                        # 提取"武器类型"行的值（标签可能被 <strong>/<span> 包裹）
                        m = _re.search(
                            r"<tr[^>]*>.*?武器类型.*?</td>\s*<td[^>]*>(.*?)</td>",
                            html,
                            _re.DOTALL,
                        )
                        if m:
                            wt = _re.sub(r"<[^>]+>", "", m.group(1)).strip()
                            affiliated_type = _ZH_TO_EN.get(wt, wt)

    return {
        "name": title,
        "catalogueId": catalogue_id,
        "type": item_type,
        "star": star,
        "contentUrl": portrait_url,
        "affiliated_type": affiliated_type,
    }


def _parse_list_item(
    record: dict, catalogue_id: str, entry_id: str, star_fallback: str = "4"
) -> dict:
    """
    兜底方案：从 getPage 返回的 record 中提取基本数据。
    仅当 getEntryDetail 失败时使用。
    """
    content = record.get("content", {})
    skill_attr = content.get("skillAttr")
    weapon_tags = content.get("relateTagIds", [])

    # 鸣潮角色共鸣属性 -> 英文（用于 fallback）
    _SKILL_ATTR_EN = {
        "2": "aero",
        "3": "electro",
        "4": "glacio",
        "5": "fusion",
        "6": "spectro",
        "7": "havoc",
    }
    # 武器类型 -> 英文（用于 fallback）
    _WEAPON_TYPE_EN = {
        "93": "broadblade",
        "94": "gauntlets",
        "95": "sword",
        "96": "pistols",
        "97": "rectifier",
    }

    item_type = WIKI_CATALOGUES.get(catalogue_id, "unknown")
    affiliated_type = ""

    if weapon_tags and str(weapon_tags[0]) in _WEAPON_TYPE_EN:
        item_type = "weapon"
        affiliated_type = _WEAPON_TYPE_EN.get(str(weapon_tags[0]), "")
    elif skill_attr is not None:
        item_type = "character"
        affiliated_type = _SKILL_ATTR_EN.get(str(skill_attr), "")

    return {
        "name": record.get("name", ""),
        "catalogueId": catalogue_id,
        "type": item_type,
        "star": str(content.get("star", star_fallback)),
        "contentUrl": content.get("contentUrl", ""),
        "affiliated_type": affiliated_type,
    }


@app.route("/api/wiki/sync-list", methods=["POST"])
async def wiki_sync_list() -> Response:
    """
    从库街区Wiki同步角色/武器列表。

    流程：
      1. getPage 获取全量条目列表（含 entryId）
      2. 对每个 entryId 调用 getEntryDetail 获取精确数据
         （角色：role-component → role.info 属性字段 /
           武器：tabs-component/basic-component → HTML 表格武器类型行）
      3. getEntryDetail 失败时降级为 getPage 数据（relateTagIds 兜底武器类型）

    POST body: {"catalogue_ids": ["1105", "1106"]}
    """
    try:
        data = await request.get_json() or {}
        catalogue_ids = data.get("catalogue_ids", ["1105", "1106"])

        devcode = _generate_devcode()
        headers = {
            "source": "h5",
            "wiki_type": "9",
            "devcode": devcode,
            "Content-Type": "application/x-www-form-urlencoded",
        }

        all_items = []
        sem = asyncio.Semaphore(10)

        async def _fetch_detail(
            client: httpx.AsyncClient, entry_id: str, record: dict, cid: str
        ) -> dict | None:
            """并发获取详情，失败则降级。"""
            record_content = record.get("content", {})
            record_star = str(record_content.get("star", "4"))
            record_portrait = record_content.get("contentUrl", "")

            async with sem:
                try:
                    detail_resp = await client.post(
                        f"{KUROBBS_API_BASE}/wiki/core/catalogue/item/getEntryDetail",
                        headers=headers,
                        data=f"id={entry_id}",
                    )
                    detail_data = detail_resp.json()
                    if detail_data.get("code") == 200:
                        parsed = _parse_detail_item(
                            detail_data["data"],
                            cid,
                            portrait_fallback=record_portrait,
                            star_fallback=record_star,
                        )
                        if parsed:
                            # 武器：如果详情页未解析出武器类型，
                            # 从列表数据的 relateTagIds 兜底
                            if cid == "1106" and not parsed.get("affiliated_type"):
                                fallback = _parse_list_item(
                                    record, cid, entry_id, star_fallback=record_star
                                )
                                if fallback.get("affiliated_type"):
                                    parsed["affiliated_type"] = fallback[
                                        "affiliated_type"
                                    ]
                            return parsed
                except Exception as e:
                    logger.error(f"getEntryDetail error (id={entry_id}): {e}")
                return _parse_list_item(
                    record, cid, entry_id, star_fallback=record_star
                )

        async with httpx.AsyncClient(timeout=30) as client:
            for cid in catalogue_ids:
                # Step 1: 获取条目列表
                resp = await client.post(
                    f"{KUROBBS_API_BASE}/wiki/core/catalogue/item/getPage",
                    headers=headers,
                    data=f"catalogueId={cid}&page=1&limit=1000",
                )
                resp_data = resp.json()
                if resp_data.get("code") != 200:
                    logger.error(f"getPage error (catalogueId={cid}): {resp_data}")
                    continue

                records = (
                    resp_data.get("data", {}).get("results", {}).get("records", [])
                )

                # Step 2: 并发获取详情
                tasks = []
                for record in records:
                    content = record.get("content", {})
                    entry_id = str(
                        content.get("linkConfig", {}).get(
                            "entryId", content.get("entryId", "")
                        )
                    )
                    if entry_id:
                        tasks.append(_fetch_detail(client, entry_id, record, cid))

                items = await asyncio.gather(*tasks)
                all_items.extend(i for i in items if i)

        return jsonify({"success": True, "items": all_items})
    except Exception as e:
        logger.error(f"Wiki sync-list failed: {e}")
        return jsonify({"success": False, "message": str(e)})


# 前端处理后的立绘上传保存（纯存储，不做任何像素处理）
@app.route("/api/items/upload-portrait", methods=["POST"])
async def upload_portrait() -> Response:
    """接收前端已裁剪/缩剪/渐变处理完毕的立绘 PNG blob，保存到本地。
    文件名由原始 portrait_url 的哈希决定，同一来源始终只有一份处理结果。
    """
    import base64
    import hashlib

    try:
        data = await request.get_json()
        b64_str = data.get("image", "")
        portrait_url = data.get("portrait_url", "") or ""
        config_group = data.get("config_group", "default")

        content = base64.b64decode(b64_str)
        data_dir = DEFAULT_CONFIG_DIR.parent
        portraits_dir = data_dir / "portraits" / config_group
        portraits_dir.mkdir(parents=True, exist_ok=True)

        # 用原始 URL 的哈希作为文件名，同一来源多次处理只保留最新结果
        if portrait_url:
            key = hashlib.md5(portrait_url.encode()).hexdigest()[:12]
        else:
            key = hashlib.md5(content).hexdigest()[:12]
        file_path = portraits_dir / f"{key}.png"

        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(f"[upload-portrait] 已保存立绘: {file_path} ({len(content)} bytes)")
        relative_path = f"{config_group}/{file_path.name}"
        return jsonify(
            {
                "success": True,
                "path": str(file_path),
                "relative_path": relative_path,
                "url": f"/api/portraits/{relative_path}",
            }
        )
    except Exception as e:
        logger.error(f"[upload-portrait] 保存失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/portraits/<path:filename>", methods=["GET"])
async def portraits_static(filename: str) -> Response:
    """提供本地存储的处理后立绘文件访问"""
    portraits_dir = DEFAULT_CONFIG_DIR.parent / "portraits"
    try:
        return await send_from_directory(str(portraits_dir), filename)
    except FileNotFoundError:
        response = await make_response(
            jsonify({"success": False, "message": "文件不存在"})
        )
        response.status_code = 404
        return response


# 静态资源服务

_UNPACK_OWNER = "TomyJan"
_UNPACK_REPO = "WutheringWaves-UIResources"
_UNPACK_PORTRAIT_PATH = "UIResources/Common/Image/Luckdraw"
_UNPACK_GH_PROXY = "https://gh-proxy.com/"


async def _github_api_get_json(client: httpx.AsyncClient, api_path: str) -> Any:
    """调用 GitHub REST API 并返回 JSON，含友好的错误处理。"""
    url = f"https://api.github.com/repos/{_UNPACK_OWNER}/{_UNPACK_REPO}{api_path}"
    logger.info(f"[unpack] 请求 URL: {url}")
    resp = await client.get(
        url, headers={"User-Agent": "astrbot-ww-gacha-sim"}, follow_redirects=True
    )
    logger.info(
        f"[unpack] 响应状态码: {resp.status_code}, content-type: {resp.headers.get('content-type', 'unknown')}"
    )
    if resp.status_code == 403:
        raise Exception("GitHub API 速率限制已达，请稍后再试")
    content_type = resp.headers.get("content-type", "")
    text_preview = resp.text[:200]
    if resp.status_code == 404:
        raise Exception(f"路径不存在 (HTTP 404): {text_preview}")
    if resp.status_code != 200:
        raise Exception(f"请求失败 (HTTP {resp.status_code}): {text_preview}")
    if "json" not in content_type:
        raise Exception(f"响应非 JSON (content-type: {content_type}): {text_preview}")
    return resp.json()


@app.route("/api/unpack-source/portraits", methods=["POST"])
async def unpack_source_portraits() -> Response:
    """
    连接仓库并直接获取默认分支下的抽卡立绘文件列表。

    不再分两步（获取版本→选版本→加载立绘），
    改为直接访问默认分支上的 Luckdraw 目录。
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            logger.info("[unpack] 开始获取仓库信息…")
            repo_data = await _github_api_get_json(client, "")
            default_branch = repo_data.get("default_branch", "master")
            logger.info(f"[unpack] 仓库默认分支: {default_branch}")

            api_path = f"/contents/{_UNPACK_PORTRAIT_PATH}?ref={default_branch}"
            logger.info(f"[unpack] 直接访问立绘目录: GET {api_path}")
            items = await _github_api_get_json(client, api_path)
            if not isinstance(items, list):
                items = [items]
            logger.info(f"[unpack] GitHub API 返回 {len(items)} 个条目")

            image_ext = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
            portraits = []
            skipped_dirs = 0
            skipped_ext = 0
            skipped_pattern = 0

            import re as _re

            _luckdraw_pattern = _re.compile(r"^T_Luckdraw.+_UI\.png$")

            for item in items:
                if item.get("type") != "file":
                    skipped_dirs += 1
                    continue
                ext = os.path.splitext(item["name"])[1].lower()
                if ext not in image_ext:
                    skipped_ext += 1
                    continue
                if not _luckdraw_pattern.match(item["name"]):
                    skipped_pattern += 1
                    continue
                raw_url = (
                    f"{_UNPACK_GH_PROXY}"
                    f"https://raw.githubusercontent.com"
                    f"/{_UNPACK_OWNER}/{_UNPACK_REPO}"
                    f"/{default_branch}/{item['path']}"
                )
                logger.info(f"[unpack] 构造立绘URL(gh-proxy): {raw_url}")
                portraits.append(
                    {
                        "name": item["name"],
                        "raw_url": raw_url,
                        "size": item.get("size", 0),
                    }
                )

            logger.info(
                f"[unpack] 过滤结果: {len(portraits)} 个立绘文件"
                f" (跳过 {skipped_dirs} 个目录, {skipped_ext} 个非图片文件, {skipped_pattern} 个非Luckdraw立绘)"
            )
            return jsonify(
                {
                    "success": True,
                    "portraits": portraits,
                    "default_branch": default_branch,
                }
            )
    except Exception as e:
        logger.error(f"[unpack] 获取立绘列表失败: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route("/", methods=["GET"])
async def index() -> Response:
    # 指向 static 目录
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    return await send_from_directory(static_dir, "index.html")


@app.route("/<path:filename>", methods=["GET"])
async def static_files(filename: str) -> Response:
    logger.info(f"[static] GET /{filename}")
    # 指向 static 目录
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    try:
        return await send_from_directory(static_dir, filename)
    except FileNotFoundError:
        response = await make_response(
            jsonify({"success": False, "message": "文件不存在"})
        )
        response.status_code = 404
        return response


@contextmanager
def _patch_signal_for_thread():
    """
    非主线程中 Hypercorn 注册信号处理器会失败。
    将 signal.signal / signal.set_wakeup_fd 包装为静默降级，避免 ValueError / RuntimeError。
    """
    original_signal = signal.signal
    original_set_wakeup_fd = signal.set_wakeup_fd

    def _patched_signal(signalnum, handler, /):
        try:
            return original_signal(signalnum, handler)
        except ValueError:
            return None

    def _patched_set_wakeup_fd(fd, /, *, warn_on_full_buffer=True):
        try:
            return original_set_wakeup_fd(fd, warn_on_full_buffer=warn_on_full_buffer)
        except RuntimeError:
            return -1

    signal.signal = _patched_signal
    signal.set_wakeup_fd = _patched_set_wakeup_fd
    try:
        yield
    finally:
        signal.signal = original_signal
        signal.set_wakeup_fd = original_set_wakeup_fd


# WebUI 关闭信号（由插件 terminate 调用）
shutdown_event = threading.Event()
# 记录运行中的事件循环，供主线程主动停止
_running_loop: asyncio.AbstractEventLoop | None = None


async def _start_checker():
    """在 Quart 启动前注册：记录运行中的事件循环，供主线程主动停止。"""
    global _running_loop
    _running_loop = asyncio.get_running_loop()
    logger.info(
        f"WebUI 服务器已就绪，正在监听 {app.config.get('SERVER_HOST', '0.0.0.0')}:{app.config.get('SERVER_PORT', 5000)}"
    )


app.before_serving(_start_checker)


def stop_server():
    """设置关闭信号，并主动停止 server 的事件循环。"""
    logger.info("正在停止 WebUI 服务...")
    shutdown_event.set()
    if _running_loop and _running_loop.is_running():
        logger.debug("正在向事件循环发送停止信号...")
        _running_loop.call_soon_threadsafe(_running_loop.stop)
    else:
        logger.warning("WebUI 事件循环未运行，跳过停止")


def run(host: str = "0.0.0.0", port: int = 5000, debug: bool = False):
    """运行 Quart Web 服务器（同步入口，用于在线程中启动）。"""
    app.config["DEBUG"] = debug
    app.config["SERVER_HOST"] = host
    app.config["SERVER_PORT"] = port

    logger.info(f"WebUI 服务器正在启动，监听 {host}:{port}")

    with _patch_signal_for_thread():
        try:
            # 在非主线程中使用 new_event_loop 替代 asyncio.run
            # asyncio.run() 在 Python 3.12+ 的非主线程中会抛出 RuntimeError
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(app.run_task(host=host, port=port, debug=debug))
        except Exception as e:
            logger.error(f"WebUI 服务器运行异常: {e}")
            raise
        finally:
            loop.close()

    _running_loop = None
    logger.info("WebUI 服务器已停止")


async def run_async(host: str = "0.0.0.0", port: int = 5000, debug: bool = False):
    """
    以 asyncio 任务形式运行 WebUI 服务器。
    在主事件循环中使用，通过 asyncio.create_task 或类似机制调用。
    避免线程方式下 signal.set_wakeup_fd / add_signal_handler 的限制。
    """
    app.config["DEBUG"] = debug
    app.config["SERVER_HOST"] = host
    app.config["SERVER_PORT"] = port

    logger.info(f"WebUI 服务器正在启动，监听 {host}:{port}")

    # 存储 shutdown 事件到 app.config，供 stop_server_async 触发停止
    _shutdown_event = asyncio.Event()
    app.config["_SHUTDOWN_EVENT"] = _shutdown_event

    try:
        await app.run_task(
            host=host,
            port=port,
            debug=debug,
            shutdown_trigger=lambda: _shutdown_event.wait(),
        )
    except asyncio.CancelledError:
        logger.info("WebUI 服务器任务已取消")
        raise
    except Exception as e:
        logger.error(f"WebUI 服务器运行异常: {e}")
        raise
    finally:
        logger.info("WebUI 服务器已停止")
        app.config.pop("_SHUTDOWN_EVENT", None)


async def stop_server_async():
    """停止异步运行的 WebUI 服务器（设置 shutdown_trigger 事件）。"""
    logger.info("正在停止 WebUI 服务...")
    _shutdown_event = app.config.get("_SHUTDOWN_EVENT")
    if _shutdown_event:
        _shutdown_event.set()
    else:
        logger.warning("未找到 WebUI shutdown 事件，可能服务未运行")
    if _shutdown_event:
        _shutdown_event.set()
    else:
        logger.warning("未找到 WebUI shutdown 事件")


def parse_arguments():
    """
    解析命令行参数

    Returns:
        argparse.Namespace: 包含解析后参数的命名空间
    """
    parser = argparse.ArgumentParser(description="鸣潮模拟抽卡插件Web服务器")
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=5000,
        help="指定服务器运行端口（范围：1-65535），默认5000",
    )
    parser.add_argument(
        "--debug", "-d", action="store_true", help="启用调试模式（默认关闭，生产环境）"
    )
    return parser.parse_args()


def validate_port(port: int) -> None:
    """
    验证端口号的有效性

    Args:
        port: 要验证的端口号

    Raises:
        ValueError: 如果端口号无效
    """
    if not (1 <= port <= 65535):
        raise ValueError(f"无效的端口号: {port}。端口号必须在1-65535范围内。")


def open_browser(port: int):
    """
    自动打开浏览器

    Args:
        port: 服务器端口号
    """
    url = f"http://127.0.0.1:{port}"
    print(f"[*] 正在自动打开界面: {url}")
    webbrowser.open(url)


if __name__ == "__main__":
    # 解析命令行参数
    args = parse_arguments()

    try:
        # 验证端口号
        validate_port(args.port)

        # 根据参数设置调试模式
        app.config["DEBUG"] = args.debug

        print("[*] 鸣潮模拟抽卡插件 Web 服务器启动中...")
        print(f"[*] 运行环境: {sys.platform}")
        print(f"[*] 监听地址: http://0.0.0.0:{args.port}")

        # 启动成功后在异步事件循环开启后打开浏览器
        Timer(1.5, open_browser, args=[args.port]).start()

        # 使用 Quart 的异步运行
        asyncio.run(app.run_task(host="0.0.0.0", port=args.port, debug=args.debug))
    except Exception as e:
        print(f"启动服务器失败: {e}", file=sys.stderr)
        sys.exit(1)
