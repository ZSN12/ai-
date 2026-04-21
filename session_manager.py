import time
import uuid
from typing import Dict, Optional, Any
from threading import Lock
from ai_service import AIService
from task_system import TaskSystem
from config import Settings, settings as default_settings


class SessionManager:
    """会话管理器，为每个用户会话提供独立的服务实例"""
    
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.lock = Lock()
        self.cleanup_interval = 3600  # 清理间隔（秒）
        self.session_timeout = 7200  # 会话超时时间（秒）
        
    def get_or_create_session(self, session_id: Optional[str] = None) -> str:
        """获取或创建会话ID"""
        if not session_id:
            session_id = str(uuid.uuid4())
        
        with self.lock:
            if session_id not in self.sessions:
                # 为新会话创建独立的服务实例
                self.sessions[session_id] = {
                    'created_at': time.time(),
                    'last_accessed': time.time(),
                    'ai_service': AIService(default_settings),
                    'task_system': TaskSystem(max_workers=4)
                }
                # 启动任务系统
                self.sessions[session_id]['task_system'].start()
            else:
                # 更新最后访问时间
                self.sessions[session_id]['last_accessed'] = time.time()
        
        # 定期清理过期会话
        self._cleanup_expired_sessions()
        
        return session_id
    
    def get_ai_service(self, session_id: str) -> AIService:
        """获取会话的AI服务实例"""
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id]['last_accessed'] = time.time()
                return self.sessions[session_id]['ai_service']
            else:
                # 如果会话不存在，创建一个新的
                return self.get_or_create_session(session_id)['ai_service']
    
    def get_task_system(self, session_id: str) -> TaskSystem:
        """获取会话的任务系统实例"""
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id]['last_accessed'] = time.time()
                return self.sessions[session_id]['task_system']
            else:
                # 如果会话不存在，创建一个新的
                return self.get_or_create_session(session_id)['task_system']
    
    def clear_session(self, session_id: str):
        """清除会话"""
        with self.lock:
            if session_id in self.sessions:
                # 停止任务系统
                self.sessions[session_id]['task_system'].stop()
                # 清除会话
                del self.sessions[session_id]
    
    def _cleanup_expired_sessions(self):
        """清理过期会话"""
        current_time = time.time()
        expired_sessions = []
        
        with self.lock:
            for session_id, session_data in self.sessions.items():
                if current_time - session_data['last_accessed'] > self.session_timeout:
                    expired_sessions.append(session_id)
        
        # 清理过期会话
        for session_id in expired_sessions:
            self.clear_session(session_id)
    
    def get_session_count(self) -> int:
        """获取当前会话数量"""
        with self.lock:
            return len(self.sessions)


# 全局会话管理器实例
session_manager = SessionManager()