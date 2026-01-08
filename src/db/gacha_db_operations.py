"""
抽卡数据库操作模块
处理抽卡相关的数据库异步操作，避免死锁
包含业务逻辑相关的数据库操作方法
"""
import concurrent.futures
import logging
from typing import Dict, List, Optional, Any
from .database import CommonDatabase

# 配置日志
logger = logging.getLogger(__name__)


class GachaDBOperations:
    """
    抽卡数据库操作类
    处理抽卡相关的数据库异步操作，避免死锁
    包含业务逻辑相关的数据库操作方法
    """
    
    def __init__(self, db: CommonDatabase = CommonDatabase()):
        """
        初始化抽卡数据库操作管理器
        
        Args:
            db: 数据库实例
        """
        self.db = db
        # 初始化业务相关的数据库表结构
        self._init_business_tables()
        # 使用线程池进行异步数据库操作，提高响应速度，避免死锁
        self._db_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=2, 
            thread_name_prefix="GachaDB-"
        )  # 数据库操作线程池

    def _init_business_tables(self):
        """初始化业务相关的数据库表结构"""
        try:
            # 使用CommonDatabase的上下文管理器确保连接正确关闭
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 创建用户表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id TEXT PRIMARY KEY,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                logger.debug("创建或验证users表")
                
                # 创建抽卡状态表（存储用户当前的抽卡状态）
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS gacha_states (
                        user_id TEXT PRIMARY KEY,
                        pity_5star INTEGER DEFAULT 0,
                        pity_4star INTEGER DEFAULT 0,
                        _5star_guaranteed BOOLEAN DEFAULT 0,
                        _4star_guaranteed BOOLEAN DEFAULT 0,
                        pull_count INTEGER DEFAULT 0,
                        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                    )
                ''')
                logger.debug("创建或验证gacha_states表")
                
                # 创建抽卡历史记录表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS pull_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT,
                        item TEXT,
                        rarity TEXT,
                        pull_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                    )
                ''')
                logger.debug("创建或验证pull_history表")
                
                # 创建索引，提高查询性能
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_pull_history_user ON pull_history(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_pull_history_time ON pull_history(pull_time)')
                logger.debug("创建pull_history表索引")
                
                conn.commit()
        except Exception as e:
            logger.error(f"初始化业务表失败: {e}")
            raise

    # 用户相关操作
    def create_user(self, user_id: str):
        """创建新用户"""
        logger.debug(f"创建用户: {user_id}")
        self.db.execute_update('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))

    def save_user_state(self, user_id: str, state_data: Dict[str, Any]):
        """
        保存用户抽卡状态
        
        Args:
            user_id: 用户ID
            state_data: 包含用户状态信息的字典
        """
        try:
            logger.debug(f"保存用户状态: {user_id}, 状态: {state_data}")
            
            # 使用INSERT OR REPLACE简化逻辑，无需单独检查用户是否存在
            self.db.execute_update('''
                INSERT OR REPLACE INTO users (user_id) VALUES (?)
            ''', (user_id,))
            
            self.db.execute_update('''
                INSERT OR REPLACE INTO gacha_states 
                (user_id, pity_5star, pity_4star, _5star_guaranteed, _4star_guaranteed, pull_count)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                state_data['pity_5star'],
                state_data['pity_4star'],
                int(state_data['_5star_guaranteed']),
                int(state_data['_4star_guaranteed']),
                state_data['pull_count']
            ))
        except Exception as e:
            logger.error(f"保存用户状态失败: {user_id}, 错误: {e}")
            raise

    def load_user_state(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        加载用户抽卡状态
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户状态字典，如果不存在则返回None
        """
        try:
            logger.debug(f"加载用户状态: {user_id}")
            row = self.db.execute_query_single('''
                SELECT pity_5star, pity_4star, _5star_guaranteed, _4star_guaranteed, pull_count
                FROM gacha_states
                WHERE user_id = ?
            ''', (user_id,))
            
            if not row:
                return None
            
            return {
                'pity_5star': row['pity_5star'],
                'pity_4star': row['pity_4star'],
                '_5star_guaranteed': bool(row['_5star_guaranteed']),
                '_4star_guaranteed': bool(row['_4star_guaranteed']),
                'pull_count': row['pull_count']
            }
        except Exception as e:
            logger.error(f"加载用户状态失败: {user_id}, 错误: {e}")
            raise

    def save_pull_history(self, user_id: str, pull_data: Dict[str, Any]):
        """
        保存单次抽卡记录
        
        Args:
            user_id: 用户ID
            pull_data: 抽卡记录数据
        """
        try:
            logger.debug(f"保存抽卡记录: {user_id}, 物品: {pull_data['item']}")
            self.db.execute_update('''
                INSERT INTO pull_history 
                (user_id, item, rarity, pull_time)
                VALUES (?, ?, ?, ?)
            ''', (
                user_id,
                pull_data['item'],
                pull_data.get('rarity', '未知'),  # 从数据中获取稀有度，默认未知
                pull_data['pull_time']
            ))
        except Exception as e:
            logger.error(f"保存抽卡记录失败: {user_id}, 错误: {e}")
            raise

    def save_pull_history_batch(self, user_id: str, pull_history_list: List[Dict[str, Any]]):
        """
        批量保存抽卡记录
        
        Args:
            user_id: 用户ID
            pull_history_list: 抽卡记录列表
        """
        try:
            logger.debug(f"批量保存抽卡记录: {user_id}, 数量: {len(pull_history_list)}")
            
            # 确保用户存在
            self.db.execute_update('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
            
            params_list = [
                (user_id, record['item'], 
                 record.get('rarity', '未知'),  # 从数据中获取稀有度，默认未知
                 record['pull_time']) for record in pull_history_list
            ]
            
            self.db.execute_many('''
                INSERT INTO pull_history 
                (user_id, item, rarity, pull_time)
                VALUES (?, ?, ?, ?)
            ''', params_list)
        except Exception as e:
            logger.error(f"批量保存抽卡记录失败: {user_id}, 错误: {e}")
            raise

    def load_pull_history(self, user_id: str, limit: Optional[int] = None, order: str = 'desc') -> List[Dict[str, Any]]:
        """
        加载用户抽卡历史
        
        Args:
            user_id: 用户ID
            limit: 返回记录的最大数量
            order: 排序方式，'asc'或'desc'
            
        Returns:
            抽卡历史记录列表
        """
        try:
            logger.debug(f"加载抽卡历史: {user_id}, 限制: {limit}, 排序: {order}")
            
            query = 'SELECT id, item, rarity, pull_time FROM pull_history WHERE user_id = ? ORDER BY id'
            params = [user_id]
            
            if order.lower() == 'desc':
                query += ' DESC'
            else:
                query += ' ASC'
            
            if limit:
                query += ' LIMIT ?'
                params.append(limit)
            
            rows = self.db.execute_query(query, tuple(params))
            
            return [{
                'id': row['id'],
                'item': row['item'],
                'rarity': row['rarity'],
                'pull_time': row['pull_time']
            } for row in rows]
        except Exception as e:
            logger.error(f"加载抽卡历史失败: {user_id}, 错误: {e}")
            raise

    def get_user_statistics(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户统计数据
        
        Args:
            user_id: 用户ID
            
        Returns:
            包含统计信息的字典
        """
        try:
            logger.debug(f"获取用户统计: {user_id}")
            
            # 获取总抽卡次数
            total_pulls_row = self.db.execute_query_single('''
                SELECT COUNT(*) as total_pulls
                FROM pull_history
                WHERE user_id = ?
            ''', (user_id,))
            
            # 获取5星和4星抽卡次数
            rarity_stats_row = self.db.execute_query_single('''
                SELECT 
                    COUNT(CASE WHEN rarity = '5star' THEN 1 END) as five_star_pulls,
                    COUNT(CASE WHEN rarity = '4star' THEN 1 END) as four_star_pulls
                FROM pull_history
                WHERE user_id = ?
            ''', (user_id,))
            
            return {
                'total_pulls': total_pulls_row['total_pulls'] if total_pulls_row else 0,
                'five_star_pulls': rarity_stats_row['five_star_pulls'] if rarity_stats_row else 0,
                'four_star_pulls': rarity_stats_row['four_star_pulls'] if rarity_stats_row else 0
            }
        except Exception as e:
            logger.error(f"获取用户统计失败: {user_id}, 错误: {e}")
            raise

    def clear_user_data(self, user_id: str):
        """
        清除用户所有数据
        
        Args:
            user_id: 用户ID
        """
        try:
            logger.debug(f"清除用户数据: {user_id}")
            # 由于外键约束设置了ON DELETE CASCADE，删除用户会自动删除相关的抽卡状态和历史记录
            self.db.execute_update('DELETE FROM users WHERE user_id = ?', (user_id,))
        except Exception as e:
            logger.error(f"清除用户数据失败: {user_id}, 错误: {e}")
            raise

    # 异步操作方法
    def save_user_state_async(self, user_id: str, state_data: Dict[str, Any]):
        """
        异步保存用户状态到数据库
        
        Args:
            user_id: 用户ID
            state_data: 包含用户状态信息的字典
        """
        def save_state():
            try:
                self.save_user_state(user_id, state_data)
                logger.debug(f"异步保存用户状态成功: {user_id}")
            except Exception as e:
                logger.error(f"异步保存用户状态失败: {user_id}, 错误: {e}")
        
        self._db_executor.submit(save_state)

    def save_pull_history_batch_async(self, user_id: str, batch_data: List[Dict[str, Any]]):
        """
        异步批量保存抽卡记录到数据库
        
        Args:
            user_id: 用户ID
            batch_data: 包含多个抽卡记录的列表
        """
        def save_batch():
            try:
                self.save_pull_history_batch(user_id, batch_data)
                logger.debug(f"异步批量保存抽卡记录成功: {user_id}, 数量: {len(batch_data)}")
            except Exception as e:
                logger.error(f"异步批量保存抽卡记录失败: {user_id}, 错误: {e}")
        
        self._db_executor.submit(save_batch)

    def close(self):
        """
        关闭线程池资源
        """
        logger.info("关闭数据库操作线程池")
        self._db_executor.shutdown(wait=True)