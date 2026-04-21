import sqlite3
import threading
from typing import Optional


class ConnectionPool:
    """SQLite连接池管理"""
    
    def __init__(self, db_path: str, max_connections: int = 5):
        self.db_path = db_path
        self.max_connections = max_connections
        self.connections = []
        self.lock = threading.Lock()
        
    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        # 为每个线程创建独立的连接
        # SQLite不支持跨线程使用连接
        conn = sqlite3.connect(self.db_path)
        # 设置PRAGMA，提高并发性能
        cursor = conn.cursor()
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA synchronous=NORMAL')
        cursor.execute('PRAGMA busy_timeout=30000')  # 30秒超时
        conn.commit()
        return conn
    
    def return_connection(self, conn: sqlite3.Connection):
        """归还数据库连接"""
        try:
            # 关闭连接，因为SQLite不支持跨线程使用
            conn.close()
        except:
            pass
    
    def close_all(self):
        """关闭所有连接"""
        # 由于每个连接都是独立的，这里不需要做什么
        pass