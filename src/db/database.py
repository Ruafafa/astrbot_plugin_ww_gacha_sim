"""
数据库交互模块
负责所有与数据库相关的操作，包括数据查询、插入、更新和删除
"""
import sqlite3
from contextlib import contextmanager
from typing import Dict, List, Optional, Any


class GachaDatabase:
    def __init__(self, db_path='data/gacha_data.db'):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建抽卡状态表（存储用户当前的抽卡状态）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gacha_states (
                user_id TEXT PRIMARY KEY,
                pity_5star INTEGER DEFAULT 0,
                pity_4star INTEGER DEFAULT 0,
                _5star_guaranteed BOOLEAN DEFAULT 0,
                _4star_guaranteed BOOLEAN DEFAULT 0,
                pull_count INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # 创建抽卡历史记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pull_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                item TEXT,
                rarity TEXT,
                pull_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        conn.commit()
        conn.close()

    @contextmanager
    def get_connection(self):
        """数据库连接上下文管理器，确保连接正确关闭"""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def create_user(self, user_id: str):
        """创建新用户"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
            conn.commit()

    def save_user_state(self, user_id: str, state_data: Dict[str, Any]):
        """保存用户抽卡状态"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 检查用户是否存在，不存在则创建
            cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
            if not cursor.fetchone():
                cursor.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
            
            cursor.execute('''
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
            
            conn.commit()

    def load_user_state(self, user_id: str) -> Optional[Dict[str, Any]]:
        """加载用户抽卡状态"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT pity_5star, pity_4star, _5star_guaranteed, _4star_guaranteed, pull_count
                FROM gacha_states
                WHERE user_id = ?
            ''', (user_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return {
                'pity_5star': row[0],
                'pity_4star': row[1],
                '_5star_guaranteed': bool(row[2]),
                '_4star_guaranteed': bool(row[3]),
                'pull_count': row[4]
            }

    def save_pull_history(self, user_id: str, pull_data: Dict[str, Any]):
        """保存单次抽卡记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO pull_history 
                (user_id, item, rarity, pull_time)
                VALUES (?, ?, ?, ?)
            ''', (
                user_id,
                pull_data['item'],
                '未知',  # 暂时使用默认值，后续可以从物品详情获取
                pull_data['pull_time']
            ))
            conn.commit()

    def save_pull_history_batch(self, user_id: str, pull_history_list: List[Dict[str, Any]]):
        """批量保存抽卡记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT INTO pull_history 
                (user_id, item, rarity, pull_time)
                VALUES (?, ?, ?, ?)
            ''', [
                (user_id, record['item'], 
                 '未知',  # 暂时使用默认值，后续可以从物品详情获取
                 record['pull_time']) for record in pull_history_list
            ])
            conn.commit()

    def load_pull_history(self, user_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """加载用户抽卡历史"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = 'SELECT item, pull_time FROM pull_history WHERE user_id = ? ORDER BY id'
            params = [user_id]
            
            if limit:
                query += ' LIMIT ?'
                params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [{
                'item': row[0],
                'pull_time': row[1]
            } for row in rows]

    def get_user_statistics(self, user_id: str) -> Dict[str, int]:
        """获取用户统计数据"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) as total_pulls
                FROM pull_history
                WHERE user_id = ?
            ''', (user_id,))
            
            stats = cursor.fetchone()
            return {
                'total_pulls': stats[0] if stats[0] else 0
            }