"""
数据库交互模块
负责所有与数据库相关的操作，包括数据查询、插入、更新和删除
只包含基本的、业务无关的数据库操作方法
"""
import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import List, Dict, Any

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 定义插件路径
PLUGIN_PATH = Path(__file__).parent.parent.parent

class CommonDatabase:
    """通用数据库操作类"""

    def __init__(self, db_path: Path = PLUGIN_PATH.parent.parent / 'ww_gacha_sim_data.db'):
        """
        初始化数据库连接
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._ensure_directory_exists()
        self.init_db()
        logger.info(f"初始化数据库连接: {self.db_path}")

    def _ensure_directory_exists(self):
        """确保数据库所在目录存在"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def init_db(self):
        """初始化数据库表结构 - 由子类或专门的初始化函数负责"""
        pass

    @contextmanager
    def get_connection(self):
        """数据库连接上下文管理器，确保连接正确关闭"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute('PRAGMA foreign_keys = ON')  # 启用外键约束
            conn.execute('PRAGMA journal_mode = WAL')  # 启用WAL模式，提高并发性能
            yield conn
        except sqlite3.Error as e:
            logger.error(f"数据库连接错误: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    # 通用数据库操作方法
    def execute_query(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """
        执行查询操作
        
        Args:
            query: SQL查询语句
            params: 查询参数
            
        Returns:
            查询结果列表
        """
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"查询执行错误: {e}, SQL: {query}, Params: {params}")
            raise

    def execute_query_single(self, query: str, params: tuple = ()) -> sqlite3.Row:
        """
        执行查询操作，返回单个结果
        
        Args:
            query: SQL查询语句
            params: 查询参数
            
        Returns:
            查询结果，如果没有结果返回None
        """
        results = self.execute_query(query, params)
        return results[0] if results else None

    def execute_update(self, query: str, params: tuple = ()) -> int:
        """
        执行更新操作（INSERT, UPDATE, DELETE）
        
        Args:
            query: SQL更新语句
            params: 更新参数
            
        Returns:
            影响的行数
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                logger.debug(f"更新执行成功，影响行数: {cursor.rowcount}, SQL: {query}, Params: {params}")
                return cursor.rowcount
        except sqlite3.Error as e:
            logger.error(f"更新执行错误: {e}, SQL: {query}, Params: {params}")
            raise

    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """
        执行批量操作
        
        Args:
            query: SQL语句
            params_list: 参数列表
            
        Returns:
            影响的行数
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(query, params_list)
                conn.commit()
                logger.debug(f"批量执行成功，影响行数: {cursor.rowcount}, SQL: {query}")
                return cursor.rowcount
        except sqlite3.Error as e:
            logger.error(f"批量执行错误: {e}, SQL: {query}")
            raise

    def execute_script(self, script: str) -> None:
        """
        执行SQL脚本
        
        Args:
            script: SQL脚本内容
        """
        try:
            with self.get_connection() as conn:
                conn.executescript(script)
                conn.commit()
                logger.debug("SQL脚本执行成功")
        except sqlite3.Error as e:
            logger.error(f"SQL脚本执行错误: {e}")
            raise

    def close(self):
        """关闭数据库连接（占位方法，实际由上下文管理器处理）"""
        pass