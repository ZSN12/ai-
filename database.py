import sqlite3
import json
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging
from db_connection_pool import ConnectionPool

logger = logging.getLogger(__name__)


class Database:
    """数据库管理类"""
    
    def __init__(self, db_path: str = "data/qa_database.db"):
        self.db_path = db_path
        # 确保data目录存在
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        # 创建连接池
        self.pool = ConnectionPool(db_path, max_connections=5)
        self._init_database()
    
    def _init_database(self):
        """初始化数据库"""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        # 创建会话表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建会话消息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS session_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                message_id TEXT,
                message TEXT,
                type INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
            )
        ''')
        
        # 创建质检结果表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS qa_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                category TEXT NOT NULL,
                remark TEXT,
                confidence REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
            )
        ''')
        
        # 创建类别统计表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS category_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(category, date)
            )
        ''')
        
        # 创建任务表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL,
                progress REAL DEFAULT 0.0,
                result_data TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建商家表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS merchants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 检查并添加updated_at列（如果不存在）
        try:
            cursor.execute('ALTER TABLE merchants ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        except:
            pass
        
        # 创建商家规则表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS merchant_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant_id TEXT NOT NULL,
                category TEXT NOT NULL,
                lang TEXT NOT NULL,
                keyword TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (merchant_id) REFERENCES merchants (merchant_id),
                UNIQUE(merchant_id, category, lang, keyword)
            )
        ''')
        
        # 修改sessions表，添加merchant_id字段
        try:
            cursor.execute('ALTER TABLE sessions ADD COLUMN merchant_id TEXT')
        except:
            pass
        
        # 修改qa_results表，添加merchant_id字段
        try:
            cursor.execute('ALTER TABLE qa_results ADD COLUMN merchant_id TEXT')
        except:
            pass
        
        # 修改category_stats表，添加merchant_id字段
        try:
            cursor.execute('ALTER TABLE category_stats ADD COLUMN merchant_id TEXT')
        except:
            pass
        
        # 修改tasks表，添加merchant_id字段
        try:
            cursor.execute('ALTER TABLE tasks ADD COLUMN merchant_id TEXT')
        except:
            pass
        
        # 修改logs表，添加merchant_id字段
        try:
            cursor.execute('ALTER TABLE logs ADD COLUMN merchant_id TEXT')
        except:
            pass
        
        conn.commit()
        self.pool.return_connection(conn)
    
    def _get_connection(self):
        """获取数据库连接"""
        return self.pool.get_connection()
    
    def _return_connection(self, conn):
        """归还数据库连接"""
        self.pool.return_connection(conn)
    
    def save_session_data(self, session_id: str, session_data: pd.DataFrame, merchant_id: str = None) -> bool:
        """保存会话数据"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 插入或更新会话记录
            cursor.execute('''
                INSERT INTO sessions (session_id, merchant_id, updated_at, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                merchant_id = excluded.merchant_id,
                updated_at = excluded.updated_at
            ''', (session_id, merchant_id or '', datetime.now().isoformat(), datetime.now().isoformat()))
            
            # 先删除旧的消息记录
            cursor.execute('DELETE FROM session_messages WHERE session_id = ?', (session_id,))
            
            # 插入新的消息记录
            for idx, row in session_data.iterrows():
                try:
                    message_id = row.get('会话ID', str(idx))
                    message = row.get('Message', '')
                    # 确保message是字符串
                    if not isinstance(message, str):
                        message = str(message)
                    # 限制message长度，避免超过数据库限制
                    if len(message) > 10000:
                        message = message[:10000]
                    message_type = row.get('Type', 0)
                    # 确保message_type是整数
                    if not isinstance(message_type, int):
                        try:
                            message_type = int(message_type)
                        except:
                            message_type = 0
                    
                    cursor.execute('''
                        INSERT INTO session_messages (session_id, message_id, message, type)
                        VALUES (?, ?, ?, ?)
                    ''', (session_id, message_id, message, message_type))
                except Exception as e:
                    logger.error(f"保存会话消息失败 (行 {idx}): {str(e)}")
                    # 跳过有问题的行，继续处理其他行
                    continue
            
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"保存会话数据失败: {str(e)}")
            # 尝试回滚
            try:
                if conn:
                    conn.rollback()
            except:
                pass
            return False
        finally:
            # 归还连接
            if conn:
                self._return_connection(conn)
    
    def save_qa_results(self, session_id: str, results: List[Dict[str, Any]]) -> bool:
        """保存质检结果"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 删除旧的质检结果
            cursor.execute('DELETE FROM qa_results WHERE session_id = ?', (session_id,))
            
            # 插入新的质检结果
            for result in results:
                cursor.execute('''
                    INSERT INTO qa_results (session_id, category, remark, confidence)
                    VALUES (?, ?, ?, ?)
                ''', (
                    session_id,
                    result.get('category', '未知'),
                    result.get('remark', ''),
                    result.get('confidence', 0.0)
                ))
            
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"保存质检结果失败: {str(e)}")
            # 尝试回滚
            try:
                if conn:
                    conn.rollback()
            except:
                pass
            return False
        finally:
            # 归还连接
            if conn:
                self._return_connection(conn)
    
    def save_category_stats(self, category_df: pd.DataFrame, date: str = None) -> bool:
        """保存类别统计"""
        conn = None
        try:
            if date is None:
                date = datetime.now().strftime('%Y-%m-%d')
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            for _, row in category_df.iterrows():
                category = row.get('转人工类别', row.get('category', '未知'))
                count = row.get('数量', row.get('count', 0))
                
                cursor.execute('''
                    INSERT OR REPLACE INTO category_stats (category, count, date)
                    VALUES (?, ?, ?)
                ''', (category, int(count), date))
            
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"保存类别统计失败: {str(e)}")
            # 尝试回滚
            try:
                if conn:
                    conn.rollback()
            except:
                pass
            return False
        finally:
            # 归还连接
            if conn:
                self._return_connection(conn)
    
    def save_task(self, task_id: str, status: str, progress: float = 0.0, 
                  result_data: str = None, error_message: str = None) -> bool:
        """保存任务状态"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO tasks (task_id, status, progress, result_data, error_message, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (task_id, status, progress, result_data, error_message, datetime.now().isoformat()))
            
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"保存任务状态失败: {str(e)}")
            # 尝试回滚
            try:
                if conn:
                    conn.rollback()
            except:
                pass
            return False
        finally:
            # 归还连接
            if conn:
                self._return_connection(conn)
    
    def log_message(self, level: str, message: str, source: str = None) -> bool:
        """记录日志"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO logs (level, message, source)
                VALUES (?, ?, ?)
            ''', (level, message, source))
            
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"记录日志失败: {str(e)}")
            # 尝试回滚
            try:
                if conn:
                    conn.rollback()
            except:
                pass
            return False
        finally:
            # 归还连接
            if conn:
                self._return_connection(conn)
    
    def get_session_data(self, session_id: str) -> Optional[pd.DataFrame]:
        """获取会话数据"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT message_id, message, type
                FROM session_messages
                WHERE session_id = ?
                ORDER BY id
            ''', (session_id,))
            
            rows = cursor.fetchall()
            
            if rows:
                # 构建DataFrame
                data = {
                    '会话ID': [row[0] for row in rows],
                    'Message': [row[1] for row in rows],
                    'Type': [row[2] for row in rows]
                }
                return pd.DataFrame(data)
            return None
        except Exception as e:
            logger.error(f"获取会话数据失败: {str(e)}")
            return None
        finally:
            # 归还连接
            if conn:
                self._return_connection(conn)
    
    def get_qa_results(self, session_id: str) -> List[Dict[str, Any]]:
        """获取质检结果"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT category, remark, confidence, created_at 
                FROM qa_results 
                WHERE session_id = ? 
                ORDER BY created_at DESC
            ''', (session_id,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'category': row[0],
                    'remark': row[1],
                    'confidence': row[2],
                    'created_at': row[3]
                })
            
            return results
        except Exception as e:
            logger.error(f"获取质检结果失败: {str(e)}")
            return []
        finally:
            # 归还连接
            if conn:
                self._return_connection(conn)
    
    def get_category_stats(self, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """获取类别统计"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            query = 'SELECT category, SUM(count) as total_count FROM category_stats'
            params = []
            
            if start_date and end_date:
                query += ' WHERE date BETWEEN ? AND ?'
                params.extend([start_date, end_date])
            elif start_date:
                query += ' WHERE date >= ?'
                params.append(start_date)
            elif end_date:
                query += ' WHERE date <= ?'
                params.append(end_date)
            
            query += ' GROUP BY category ORDER BY total_count DESC'
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            if rows:
                return pd.DataFrame(rows, columns=['category', 'count'])
            return pd.DataFrame(columns=['category', 'count'])
        except Exception as e:
            logger.error(f"获取类别统计失败: {str(e)}")
            return pd.DataFrame(columns=['category', 'count'])
        finally:
            # 归还连接
            if conn:
                self._return_connection(conn)
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT status, progress, result_data, error_message, created_at, updated_at
                FROM tasks WHERE task_id = ?
            ''', (task_id,))
            
            row = cursor.fetchone()
            
            if row:
                return {
                    'status': row[0],
                    'progress': row[1],
                    'result_data': row[2],
                    'error_message': row[3],
                    'created_at': row[4],
                    'updated_at': row[5]
                }
            return None
        except Exception as e:
            logger.error(f"获取任务状态失败: {str(e)}")
            return None
        finally:
            # 归还连接
            if conn:
                self._return_connection(conn)
    
    def save_merchant(self, merchant_id: str, name: str) -> bool:
        """保存商家信息"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO merchants (merchant_id, name, updated_at)
                VALUES (?, ?, ?)
            ''', (merchant_id, name, datetime.now().isoformat()))
            
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"保存商家信息失败: {str(e)}")
            # 尝试回滚
            try:
                if conn:
                    conn.rollback()
            except:
                pass
            return False
        finally:
            # 归还连接
            if conn:
                self._return_connection(conn)
    
    def get_merchant(self, merchant_id: str) -> Optional[Dict[str, Any]]:
        """获取商家信息"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT merchant_id, name, created_at, updated_at
                FROM merchants WHERE merchant_id = ?
            ''', (merchant_id,))
            
            row = cursor.fetchone()
            
            if row:
                return {
                    'merchant_id': row[0],
                    'name': row[1],
                    'created_at': row[2],
                    'updated_at': row[3]
                }
            return None
        except Exception as e:
            logger.error(f"获取商家信息失败: {str(e)}")
            return None
        finally:
            # 归还连接
            if conn:
                self._return_connection(conn)
    
    def get_all_merchants(self) -> List[Dict[str, Any]]:
        """获取所有商家信息"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT merchant_id, name, created_at, updated_at
                FROM merchants
                ORDER BY created_at DESC
            ''')
            
            rows = cursor.fetchall()
            
            merchants = []
            for row in rows:
                merchants.append({
                    'merchant_id': row[0],
                    'name': row[1],
                    'created_at': row[2],
                    'updated_at': row[3]
                })
            return merchants
        except Exception as e:
            logger.error(f"获取所有商家信息失败: {str(e)}")
            return []
        finally:
            # 归还连接
            if conn:
                self._return_connection(conn)
    
    def save_merchant_rules(self, merchant_id: str, rules: Dict[str, Dict[str, List[str]]]) -> bool:
        """保存商家规则"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 先删除该商家的所有规则
            cursor.execute('DELETE FROM merchant_rules WHERE merchant_id = ?', (merchant_id,))
            
            # 插入新的规则
            for category, lang_keywords in rules.items():
                for lang, keywords in lang_keywords.items():
                    for keyword in keywords:
                        cursor.execute('''
                            INSERT INTO merchant_rules (merchant_id, category, lang, keyword)
                            VALUES (?, ?, ?, ?)
                        ''', (merchant_id, category, lang, keyword))
            
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"保存商家规则失败: {str(e)}")
            # 尝试回滚
            try:
                if conn:
                    conn.rollback()
            except:
                pass
            return False
        finally:
            # 归还连接
            if conn:
                self._return_connection(conn)
    
    def get_merchant_rules(self, merchant_id: str) -> Dict[str, Dict[str, List[str]]]:
        """获取商家规则"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT category, lang, keyword
                FROM merchant_rules
                WHERE merchant_id = ?
                ORDER BY category, lang
            ''', (merchant_id,))
            
            rows = cursor.fetchall()
            
            rules = {}
            for row in rows:
                category, lang, keyword = row
                if category not in rules:
                    rules[category] = {}
                if lang not in rules[category]:
                    rules[category][lang] = []
                rules[category][lang].append(keyword)
            
            return rules
        except Exception as e:
            logger.error(f"获取商家规则失败: {str(e)}")
            return {}
        finally:
            # 归还连接
            if conn:
                self._return_connection(conn)
    
    def delete_merchant_rule(self, merchant_id: str, category: str, lang: str, keyword: str) -> bool:
        """删除商家规则"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM merchant_rules
                WHERE merchant_id = ? AND category = ? AND lang = ? AND keyword = ?
            ''', (merchant_id, category, lang, keyword))
            
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"删除商家规则失败: {str(e)}")
            # 尝试回滚
            try:
                if conn:
                    conn.rollback()
            except:
                pass
            return False
        finally:
            # 归还连接
            if conn:
                self._return_connection(conn)


# 全局数据库实例
db = Database()
