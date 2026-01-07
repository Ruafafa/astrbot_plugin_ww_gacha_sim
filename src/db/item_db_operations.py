"""
物品数据数据库操作模块
负责从数据库加载物品数据并提供物品数据管理功能，包括角色和武器
"""
import logging
from typing import Dict, Any, List, Optional
from .database import CommonDatabase

# 配置日志
logger = logging.getLogger(__name__)


class ItemDBOperations:
    """
    物品数据数据库操作类
    提供数据库驱动的物品数据管理功能
    使用 CommonDatabase 作为底层数据库交互组件
    """
    
    def __init__(self, db: CommonDatabase = CommonDatabase()):
        """
        初始化数据库操作管理器
        
        Args:
            db: 数据库实例
        """
        self.db = db
        self._init_tables()
        logger.info("物品数据库操作管理器初始化完成")
    
    def _init_tables(self, table_name='items'):
        """初始化物品相关的数据库表结构
        
        Args:
            table_name: 物品表名称，默认为'items'
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 创建物品表
                cursor.execute(f'''
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        rarity TEXT NOT NULL,
                        type TEXT NOT NULL,
                        affiliated_type TEXT,
                        portrait_path TEXT
                    )
                ''')
                logger.debug(f"创建或验证{table_name}表")
                
                # 创建物品表索引
                cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{table_name}_name ON {table_name}(name)')
                cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{table_name}_rarity ON {table_name}(rarity)')
                logger.debug(f"创建{table_name}表索引")
                
                conn.commit()
        except Exception as e:
            logger.error(f"初始化物品表失败: {e}")
            raise
    
    def _map_row_to_item(self, row) -> Dict[str, Any]:
        """
        将数据库行映射为物品字典
        
        Args:
            row: 数据库查询结果行
            
        Returns:
            物品字典
        """
        return {
            'id': str(row['id']),
            'name': row['name'],
            'rarity': row['rarity'],
            'type': row['type'],
            'affiliated_type': row['affiliated_type'],
            'portrait_path': row['portrait_path']
        }
    
    def load_all_items(self, table_name='items') -> Dict[str, Dict[str, Any]]:
        """
        从数据库加载所有物品信息
        
        Args:
            table_name: 物品表名称，默认为'items'
            
        Returns:
            包含所有物品信息的字典，键为物品ID
        """
        try:
            logger.debug(f"加载{table_name}表的所有物品")
            rows = self.db.execute_query(f'SELECT * FROM {table_name} ORDER BY id')
            
            items = {}
            for row in rows:
                item_id = str(row['id'])
                items[item_id] = self._map_row_to_item(row)
            
            logger.debug(f"成功加载 {len(items)} 个物品")
            return items
        except Exception as e:
            logger.error(f"加载所有物品失败: {e}")
            raise
    
    def get_item_by_id(self, item_id: str, table_name='items') -> Optional[Dict[str, Any]]:
        """
        根据物品ID获取物品详细信息
        
        Args:
            item_id: 物品ID
            table_name: 物品表名称，默认为'items'
            
        Returns:
            物品详细信息字典，如果不存在则返回None
        """
        try:
            logger.debug(f"根据ID获取物品: {item_id}, 表: {table_name}")
            row = self.db.execute_query_single(f'SELECT * FROM {table_name} WHERE id = ?', (item_id,))
            return self._map_row_to_item(row) if row else None
        except Exception as e:
            logger.error(f"获取物品失败: {item_id}, 表: {table_name}, 错误: {e}")
            raise
    
    def item_exists(self, item_id: str, table_name='items') -> bool:
        """
        检查物品是否存在于数据库中
        
        Args:
            item_id: 物品ID
            table_name: 物品表名称，默认为'items'
            
        Returns:
            如果物品存在返回True，否则返回False
        """
        try:
            logger.debug(f"检查物品是否存在: {item_id}, 表: {table_name}")
            row = self.db.execute_query_single(f'SELECT COUNT(*) as count FROM {table_name} WHERE id = ?', (item_id,))
            return row['count'] > 0 if row else False
        except Exception as e:
            logger.error(f"检查物品存在性失败: {item_id}, 表: {table_name}, 错误: {e}")
            raise
    
    def add_item(self, item_data: Dict[str, Any], table_name='items') -> bool:
        """
        添加物品到数据库
        
        Args:
            item_data: 包含物品信息的字典，应包含name, rarity, type
            table_name: 物品表名称，默认为'items'
            
        Returns:
            成功返回True，失败返回False
        """
        # 初始化表
        self._init_tables(table_name)
        
        required_fields = {'name', 'rarity', 'type'}
        missing_fields = required_fields - set(item_data.keys())
        if missing_fields:
            raise ValueError(f"缺少必需字段: {missing_fields}")
        
        try:
            logger.debug(f"添加物品: {item_data['name']}, 表: {table_name}")
            
            # 统一稀有度格式为{number}star
            rarity = item_data['rarity']
            if isinstance(rarity, int):
                formatted_rarity = f"{rarity}star"
            elif rarity in ('3', '4', '5'):
                formatted_rarity = f"{rarity}star"
            else:
                formatted_rarity = str(rarity)
            
            result = self.db.execute_update(f'''
                INSERT INTO {table_name} 
                (name, rarity, type, affiliated_type, portrait_path) 
                VALUES (?, ?, ?, ?, ?)
            ''', (
                item_data['name'],
                formatted_rarity,
                item_data['type'],
                item_data.get('affiliated_type', ''),
                item_data.get('portrait_path', '')
            ))
            return result >= 0
        except Exception as e:
            logger.error(f"添加物品失败: {item_data.get('name', '未知')}, 表: {table_name}, 错误: {e}")
            return False
    
    def add_items_batch(self, items_data: List[Dict[str, Any]], table_name='items') -> bool:
        """
        批量添加物品到数据库
        
        Args:
            items_data: 包含多个物品信息字典的列表
            table_name: 物品表名称，默认为'items'
            
        Returns:
            成功返回True，失败返回False
        """
        if not items_data:
            logger.debug("没有物品需要添加")
            return True
        
        # 初始化表
        self._init_tables(table_name)
        
        required_fields = {'name', 'rarity', 'type'}
        for item_data in items_data:
            missing_fields = required_fields - set(item_data.keys())
            if missing_fields:
                raise ValueError(f"缺少必需字段: {missing_fields} 物品: {item_data.get('name', '未知')}")
        
        try:
            logger.debug(f"批量添加 {len(items_data)} 个物品到表: {table_name}")
            params_list = []
            
            for item in items_data:
                # 统一稀有度格式为{number}star
                rarity = item['rarity']
                if isinstance(rarity, int):
                    formatted_rarity = f"{rarity}star"
                elif rarity in ('3', '4', '5'):
                    formatted_rarity = f"{rarity}star"
                else:
                    formatted_rarity = str(rarity)
                
                params_list.append((
                    item['name'],
                    formatted_rarity,
                    item['type'],
                    item.get('affiliated_type', ''),
                    item.get('portrait_path', '')
                ))
            
            result = self.db.execute_many(f'''
                INSERT INTO {table_name} 
                (name, rarity, type, affiliated_type, portrait_path) 
                VALUES (?, ?, ?, ?, ?)
            ''', params_list)
            logger.debug(f"成功添加 {result} 个物品")
            return result >= 0
        except Exception as e:
            logger.error(f"批量添加物品失败: {table_name}, 错误: {e}")
            return False
    
    def update_item(self, item_id: str, update_data: Dict[str, Any], table_name='items') -> bool:
        """
        更新物品信息
        
        Args:
            item_id: 要更新的物品ID
            update_data: 包含要更新字段的字典
            table_name: 物品表名称，默认为'items'
            
        Returns:
            成功返回True，失败返回False
        """
        if not update_data:
            logger.debug(f"没有更新数据，跳过更新: {item_id}")
            return True
        
        try:
            logger.debug(f"更新物品: {item_id}, 表: {table_name}, 更新字段: {list(update_data.keys())}")
            
            # 构建动态更新语句
            valid_fields = ['name', 'rarity', 'type', 'affiliated_type', 'portrait_path']
            fields = []
            values = []
            
            for field, value in update_data.items():
                if field in valid_fields:
                    # 统一稀有度格式为{number}star
                    if field == 'rarity':
                        rarity = value
                        if isinstance(rarity, int):
                            formatted_rarity = f"{rarity}star"
                        elif rarity in ('3', '4', '5'):
                            formatted_rarity = f"{rarity}star"
                        else:
                            formatted_rarity = str(rarity)
                        values.append(formatted_rarity)
                    else:
                        values.append(value)
                    fields.append(f"{field} = ?")
            
            if not fields:
                logger.debug(f"没有有效字段需要更新: {item_id}")
                return False
            
            values.append(item_id)
            set_clause = ', '.join(fields)
            
            result = self.db.execute_update(f'UPDATE {table_name} SET {set_clause} WHERE id = ?', values)
            logger.debug(f"成功更新 {result} 个物品")
            return result > 0
        except Exception as e:
            logger.error(f"更新物品失败: {item_id}, 表: {table_name}, 错误: {e}")
            return False
    
    def delete_item(self, item_id: str, table_name='items') -> bool:
        """
        从数据库中删除物品
        
        Args:
            item_id: 要删除的物品ID
            table_name: 物品表名称，默认为'items'
            
        Returns:
            成功返回True，失败返回False
        """
        try:
            logger.debug(f"删除物品: {item_id}, 表: {table_name}")
            result = self.db.execute_update(f'DELETE FROM {table_name} WHERE id = ?', (item_id,))
            logger.debug(f"成功删除 {result} 个物品")
            return result > 0
        except Exception as e:
            logger.error(f"删除物品失败: {item_id}, 表: {table_name}, 错误: {e}")
            return False
    
    def delete_items_batch(self, item_ids: List[str], table_name='items') -> bool:
        """
        批量删除物品
        
        Args:
            item_ids: 要删除的物品ID列表
            table_name: 物品表名称，默认为'items'
            
        Returns:
            成功返回True，失败返回False
        """
        if not item_ids:
            logger.debug("没有物品需要删除")
            return True
        
        try:
            logger.debug(f"批量删除 {len(item_ids)} 个物品，表: {table_name}")
            # 构建参数列表
            params_list = [(item_id,) for item_id in item_ids]
            result = self.db.execute_many(f'DELETE FROM {table_name} WHERE id = ?', params_list)
            logger.debug(f"成功删除 {result} 个物品")
            return result >= 0
        except Exception as e:
            logger.error(f"批量删除物品失败: {table_name}, 错误: {e}")
            return False
    
    def get_items_by_rarity(self, rarity: str, table_name='items') -> List[Dict[str, Any]]:
        """
        根据稀有度获取物品列表
        
        Args:
            rarity: 稀有度（'5star', '4star', '3star'等）
            table_name: 物品表名称，默认为'items'
            
        Returns:
            符合条件的物品列表
        """
        try:
            logger.debug(f"根据稀有度获取物品: {rarity}, 表: {table_name}")
            rows = self.db.execute_query(f'SELECT * FROM {table_name} WHERE rarity = ? ORDER BY id', (rarity,))
            
            items = [self._map_row_to_item(row) for row in rows]
            logger.debug(f"找到 {len(items)} 个稀有度为 {rarity} 的物品")
            return items
        except Exception as e:
            logger.error(f"根据稀有度获取物品失败: {rarity}, 表: {table_name}, 错误: {e}")
            raise
    
    def get_items_by_type(self, item_type: str, table_name='items') -> List[Dict[str, Any]]:
        """
        根据物品类型获取物品列表
        
        Args:
            item_type: 物品类型（character, weapon等）
            table_name: 物品表名称，默认为'items'
            
        Returns:
            符合条件的物品列表
        """
        try:
            logger.debug(f"根据类型获取物品: {item_type}, 表: {table_name}")
            rows = self.db.execute_query(f'SELECT * FROM {table_name} WHERE type = ? ORDER BY id', (item_type,))
            
            items = [self._map_row_to_item(row) for row in rows]
            logger.debug(f"找到 {len(items)} 个类型为 {item_type} 的物品")
            return items
        except Exception as e:
            logger.error(f"根据类型获取物品失败: {item_type}, 表: {table_name}, 错误: {e}")
            raise
    
    def search_items_by_name(self, name: str, table_name='items', limit: int = 100) -> List[Dict[str, Any]]:
        """
        根据名称搜索物品
        
        Args:
            name: 要搜索的物品名称
            table_name: 物品表名称，默认为'items'
            limit: 返回结果的最大数量
            
        Returns:
            匹配的物品列表
        """
        try:
            logger.debug(f"搜索物品: {name}, 表: {table_name}")
            rows = self.db.execute_query(
                f'SELECT * FROM {table_name} WHERE name LIKE ? ORDER BY id LIMIT ?', 
                (f'%{name}%', limit)
            )
            
            items = [self._map_row_to_item(row) for row in rows]
            logger.debug(f"找到 {len(items)} 个匹配的物品")
            return items
        except Exception as e:
            logger.error(f"搜索物品失败: {name}, 表: {table_name}, 错误: {e}")
            raise
    
    def get_items_by_filters(self, filters: Dict[str, Any], table_name='items') -> List[Dict[str, Any]]:
        """
        根据多个条件筛选物品
        
        Args:
            filters: 筛选条件字典，支持rarity, type
            table_name: 物品表名称，默认为'items'
            
        Returns:
            符合条件的物品列表
        """
        try:
            logger.debug(f"根据条件筛选物品: {filters}, 表: {table_name}")
            
            # 构建查询条件
            conditions = []
            params = []
            
            if 'rarity' in filters:
                conditions.append('rarity = ?')
                params.append(filters['rarity'])
            
            if 'type' in filters:
                conditions.append('type = ?')
                params.append(filters['type'])
            
            query = f'SELECT * FROM {table_name}'
            if conditions:
                query += ' WHERE ' + ' AND '.join(conditions)
            query += ' ORDER BY id'
            
            rows = self.db.execute_query(query, tuple(params))
            
            items = [self._map_row_to_item(row) for row in rows]
            logger.debug(f"找到 {len(items)} 个符合条件的物品")
            return items
        except Exception as e:
            logger.error(f"根据条件筛选物品失败: {table_name}, 错误: {e}")
            raise
    
    def get_items_count(self, table_name='items') -> int:
        """
        获取物品总数
        
        Args:
            table_name: 物品表名称，默认为'items'
            
        Returns:
            物品总数
        """
        try:
            logger.debug(f"获取{table_name}表的物品总数")
            row = self.db.execute_query_single(f'SELECT COUNT(*) as count FROM {table_name}')
            count = row['count'] if row else 0
            logger.debug(f"物品总数: {count}")
            return count
        except Exception as e:
            logger.error(f"获取物品总数失败: {table_name}, 错误: {e}")
            raise
    
    def clear_table(self, table_name='items') -> bool:
        """
        清空物品表中的所有数据
        
        Args:
            table_name: 物品表名称，默认为'items'
            
        Returns:
            成功返回True，失败返回False
        """
        try:
            logger.debug(f"清空{table_name}表中的所有数据")
            result = self.db.execute_update(f'TRUNCATE TABLE {table_name}')
            return result >= 0
        except Exception as e:
            logger.error(f"清空表失败: {table_name}, 错误: {e}")
            # 如果TRUNCATE失败，尝试使用DELETE
            try:
                result = self.db.execute_update(f'DELETE FROM {table_name}')
                logger.debug(f"使用DELETE方式清空{table_name}表")
                return result >= 0
            except Exception as delete_error:
                logger.error(f"使用DELETE方式清空表失败: {table_name}, 错误: {delete_error}")
                return False
    
    def get_items_list(self, table_name='items') -> List[Dict[str, Any]]:
        """
        获取物品列表
        
        Args:
            table_name: 物品表名称，默认为'items'
            
        Returns:
            物品列表
        """
        try:
            logger.debug(f"获取{table_name}表的物品列表")
            
            # 初始化表（如果不存在则创建）
            self._init_tables(table_name)
            
            rows = self.db.execute_query(f'SELECT * FROM {table_name} ORDER BY id')
            return [self._map_row_to_item(row) for row in rows]
        except Exception as e:
            logger.error(f"获取物品列表失败: {table_name}, 错误: {e}")
            # 如果是表不存在的错误，返回空列表
            if 'no such table' in str(e):
                return []
            raise