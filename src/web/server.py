import argparse
import json
import os
import sys
import webbrowser
from pathlib import Path
from threading import Timer
from typing import Any
from wsgiref.simple_server import make_server

from astrbot.api import logger
from astrbot.api.star import StarTools
from flask import Flask, Response, jsonify, make_response, request, send_from_directory
from flask_cors import CORS
from pydantic import BaseModel


# Pydantic 验证模型
class DirectoryRequest(BaseModel):
    directory: str | None = None


class ConfigContentRequest(BaseModel):
    content: dict[str, Any]
    config_group: str = "default"


class ConfigEnableRequest(BaseModel):
    enable: bool = True


class ItemRequest(BaseModel):
    name: str
    rarity: str
    type: str
    affiliated_type: str | None = None
    portrait_path: str | None = None
    portrait_url: str | None = None
    external_id: str | None = None
    config_group: str = "default"


class ItemUpdateRequest(BaseModel):
    external_id: str
    name: str | None = None
    rarity: str | None = None
    type: str | None = None
    affiliated_type: str | None = None
    portrait_path: str | None = None
    portrait_url: str | None = None
    config_group: str = "default"


# 定义插件路径
PLUGIN_PATH = Path(__file__).parent.parent.parent

# 添加项目根目录到Python路径，以便导入db模块
sys.path.insert(0, str(PLUGIN_PATH))

# 导入数据库操作类
from src.db.database import CommonDatabase
from src.db.item_db_operations import ItemDBOperations
from src.gacha.cardpool_manager import CardPoolManager

# 创建数据库实例
db = CommonDatabase()
item_ops = ItemDBOperations(db)

# 创建卡池配置管理器
# 不传递参数，使用 CardPoolManager 内部定义的默认路径 (StarTools.get_data_dir)
cp_manager = CardPoolManager()
DEFAULT_CONFIG_DIR = cp_manager.config_dir

app = Flask(__name__)
CORS(app)  # 启用CORS支持

# 配置 Flask
app.config["DEBUG"] = False  # 默认关闭调试模式，使用 --debug 参数启用


# 配置文件管理
@app.route("/api/configs/directory", methods=["GET", "POST"])
def config_directory() -> Response:
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
            data = DirectoryRequest(**request.get_json())
            config_dir = data.directory

            if config_dir and os.path.exists(config_dir):
                return jsonify({"success": True, "directory": config_dir})
            return jsonify({"success": False, "message": "目录不存在"})
        except Exception as e:
            logger.error(f"配置目录请求失败: {e}")
            return jsonify({"success": False, "message": f"请求失败: {str(e)}"})

    # 获取配置目录
    return jsonify({"directory": str(DEFAULT_CONFIG_DIR)})


@app.route("/api/configs/list", methods=["GET"])
def config_list() -> Response:
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
def config_file(filename: str) -> Response:
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
        data = request.get_json()
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
        data = request.get_json()
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
def items() -> Response:
    # 获取请求数据
    data = request.get_json() if request.method in ["POST", "PUT"] else None

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
                except:
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
                    except:
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


# 静态资源服务
@app.route("/")
def index() -> Response:
    # 指向 static 目录
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    return send_from_directory(static_dir, "index.html")


@app.route("/<path:filename>")
def static_files(filename: str) -> Response:
    # 指向 static 目录
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    try:
        return send_from_directory(static_dir, filename)
    except FileNotFoundError:
        response = make_response(jsonify({"success": False, "message": "文件不存在"}))
        response.status_code = 404
        return response


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


def run_production_server(host: str, port: int):
    """
    使用标准库 wsgiref 运行服务器，消除警告

    Args:
        host: 监听地址
        port: 监听端口
    """
    print("[*] 鸣潮模拟抽卡插件 Web 服务器启动中...")
    print(f"[*] 运行环境: {sys.platform}")
    print(f"[*] 监听地址: http://{host}:{port}")

    # 创建服务器实例，使用 Flask 的 WSGI 应用
    server = make_server(host, port, app.wsgi_app)

    # 启动成功后，延迟1秒打开浏览器（确保服务器已在监听）
    Timer(1.0, open_browser, args=[port]).start()

    # 开始阻塞运行
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] 服务器已停止")
        sys.exit(0)


if __name__ == "__main__":
    # 解析命令行参数
    args = parse_arguments()

    try:
        # 验证端口号
        validate_port(args.port)

        # 根据参数设置调试模式
        app.config["DEBUG"] = args.debug

        # 运行模式选择
        if args.debug:
            # 调试模式：依然使用 Flask 自带服务器（支持热重载，有红色警告）
            # 同样需要先启动浏览器定时器
            Timer(1.5, open_browser, args=[args.port]).start()
            app.run(host="0.0.0.0", port=args.port, debug=True)
        else:
            # 生产模式：使用 wsgiref（无红色警告，跨平台，标准库）
            run_production_server("0.0.0.0", args.port)

    except Exception as e:
        print(f"启动服务器失败: {e}", file=sys.stderr)
        sys.exit(1)
