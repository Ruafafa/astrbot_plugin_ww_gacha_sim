from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import json
from pathlib import Path

# 定义插件路径
PLUGIN_PATH = Path(__file__).parent.parent.parent
DEFAULT_CONFIG_DIR = PLUGIN_PATH / 'card_pool_configs'

# 添加项目根目录到Python路径，以便导入db模块
import sys
sys.path.insert(0, str(PLUGIN_PATH))

# 导入数据库操作类
from src.db.database import CommonDatabase
from src.db.item_db_operations import ItemDBOperations

# 创建数据库实例
db = CommonDatabase()
item_ops = ItemDBOperations(db)

app = Flask(__name__)
CORS(app)  # 启用CORS支持

# 配置文件管理
@app.route('/api/configs/directory', methods=['GET', 'POST'])
def config_directory():
    if request.method == 'POST':
        # 设置配置目录
        data = request.get_json()
        config_dir = data.get('directory')
        if config_dir and os.path.exists(config_dir):
            return jsonify({'success': True, 'directory': config_dir})
        return jsonify({'success': False, 'message': '目录不存在'})
    
    # 获取配置目录
    return jsonify({'directory': str(DEFAULT_CONFIG_DIR)})

@app.route('/api/configs/list', methods=['GET'])
def config_list():
    # 获取配置文件列表
    config_dir = request.args.get('directory', str(DEFAULT_CONFIG_DIR))
    
    if not os.path.exists(config_dir):
        return jsonify({'success': False, 'message': '目录不存在'})
    
    configs = []
    for file in os.listdir(config_dir):
        if file.endswith('.json'):
            file_path = os.path.join(config_dir, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                configs.append({
                    'filename': file,
                    'content': config
                })
            except Exception as e:
                continue
    
    return jsonify({'success': True, 'configs': configs})

@app.route('/api/configs/<filename>', methods=['GET', 'POST', 'DELETE'])
def config_file(filename):
    config_dir = request.args.get('directory', str(DEFAULT_CONFIG_DIR))
    file_path = os.path.join(config_dir, filename)
    
    if request.method == 'GET':
        # 获取配置文件内容
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return jsonify({'success': True, 'content': config})
            except Exception as e:
                return jsonify({'success': False, 'message': '读取文件失败'})
        return jsonify({'success': False, 'message': '文件不存在'})
    
    elif request.method == 'POST':
        # 创建或更新配置文件
        data = request.get_json()
        content = data.get('content')
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
            return jsonify({'success': True, 'message': '保存成功'})
        except Exception as e:
            return jsonify({'success': False, 'message': '保存失败'})
    
    elif request.method == 'DELETE':
        # 删除配置文件
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                return jsonify({'success': True, 'message': '删除成功'})
            except Exception as e:
                return jsonify({'success': False, 'message': '删除失败'})
        return jsonify({'success': False, 'message': '文件不存在'})

# 数据库与物品管理
@app.route('/api/db/items', methods=['GET', 'POST', 'PUT', 'DELETE'])
def items():
    # 获取请求数据
    data = request.get_json() if request.method in ['POST', 'PUT'] else None
    
    # 确定config_group：优先使用请求体中的config_group，其次使用URL参数，默认使用default
    if request.method == 'GET':
        config_group = request.args.get('config_group', 'default')
    elif request.method == 'POST':
        if isinstance(data, list):
            if len(data) > 0 and 'config_group' in data[0]:
                config_group = data[0]['config_group']
            else:
                config_group = request.args.get('config_group', 'default')
        else:
            config_group = data.get('config_group', request.args.get('config_group', 'default'))
    elif request.method == 'PUT':
        config_group = data.get('config_group', request.args.get('config_group', 'default'))
    elif request.method == 'DELETE':
        # 删除操作时，需要先根据id获取物品，再确定其config_group
        item_id = request.args.get('id')
        if not item_id:
            return jsonify({'success': False, 'message': '缺少物品ID'})
        
        # 尝试从所有可能的表中查找物品
        config_group = 'default'  # 默认值
        found = False
        
        # 先尝试使用URL参数中的config_group
        if request.args.get('config_group'):
            temp_config_group = request.args.get('config_group')
            temp_table_name = f'{temp_config_group}_items'
            try:
                items_list = item_ops.get_items_list(temp_table_name)
                found = any(str(item['id']) == item_id for item in items_list)
                if found:
                    config_group = temp_config_group
            except:
                pass
        
        # 如果没找到，尝试从请求体中获取config_group
        if not found and data:
            temp_config_group = data.get('config_group')
            temp_table_name = f'{temp_config_group}_items'
            try:
                items_list = item_ops.get_items_list(temp_table_name)
                found = any(str(item['id']) == item_id for item in items_list)
                if found:
                    config_group = temp_config_group
            except:
                pass
    
    table_name = f'{config_group}_items'
    
    if request.method == 'GET':
        # 获取物品列表
        try:
            items_list = item_ops.get_items_list(table_name)
            return jsonify({'success': True, 'items': items_list})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
    
    elif request.method == 'POST':
        # 添加物品
        try:
            if isinstance(data, list):
                # 批量添加
                result = item_ops.add_items_batch(data, table_name)
                if result:
                    return jsonify({'success': True, 'message': f'成功添加 {len(data)} 个物品'})
                else:
                    return jsonify({'success': False, 'message': '批量添加物品失败'})
            else:
                # 单个添加
                result = item_ops.add_item(data, table_name)
                if result:
                    # 获取刚添加的物品ID
                    items_list = item_ops.get_items_list(table_name)
                    item_id = items_list[-1]['id'] if items_list else 1
                    return jsonify({'success': True, 'item_id': item_id})
                else:
                    return jsonify({'success': False, 'message': '添加物品失败'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
    
    elif request.method == 'PUT':
        # 更新物品
        try:
            item_id = str(data.get('id'))
            if not item_id:
                return jsonify({'success': False, 'message': '缺少物品ID'})
            
            # 移除id字段，只保留要更新的字段
            update_data = {k: v for k, v in data.items() if k != 'id'}
            result = item_ops.update_item(item_id, update_data, table_name)
            return jsonify({'success': result})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
    
    elif request.method == 'DELETE':
        # 删除物品
        try:
          # 检查是否是清空表的请求
          if request.args.get('clear_all') == 'true':
            result = item_ops.clear_table(table_name)
            return jsonify({'success': result})
          # 单个物品删除
          result = item_ops.delete_item(item_id, table_name)
          return jsonify({'success': result})
        except Exception as e:
          return jsonify({'success': False, 'message': str(e)})

# 静态资源服务
@app.route('/')
def index():
    # 直接指向React项目构建后的dist目录
    dist_dir = os.path.join(os.path.dirname(__file__), 'dev', 'dist')
    return send_from_directory(dist_dir, 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    # 直接指向React项目构建后的dist目录
    dist_dir = os.path.join(os.path.dirname(__file__), 'dev', 'dist')
    return send_from_directory(dist_dir, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
