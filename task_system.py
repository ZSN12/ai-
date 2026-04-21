import time
import uuid
import threading
import json
from queue import Queue
from typing import Dict, Any, Optional, Tuple, List
import pandas as pd
from core import run_batch_analysis
from config import Settings, settings as default_settings
from database import db


class Task:
    """任务类"""
    def __init__(self, task_id: str, session_df: pd.DataFrame, policy_retriever: Any, config: Settings, merchant_id: Optional[str] = None, merchant_rules: Optional[Dict] = None, llm_service: Optional[Any] = None):
        self.task_id = task_id
        self.session_df = session_df
        self.policy_retriever = policy_retriever
        self.config = config
        self.merchant_id = merchant_id
        self.merchant_rules = merchant_rules
        self.llm_service = llm_service
        self.status = "pending"  # pending, running, completed, failed, cancelled
        self.result = None
        self.error = None
        self.progress = 0.0
        self.start_time = None
        self.end_time = None
        self.cancelled = False  # 标记任务是否被取消


class TaskSystem:
    """任务系统"""
    def __init__(self, max_workers: int = 4):
        self.tasks: Dict[str, Task] = {}
        self.task_queue = Queue()
        self.max_workers = max_workers
        self.workers = []
        self.running = False
        self.stop_event = threading.Event()
        # 加载数据库中的任务
        self._load_tasks_from_db()
    
    def _load_tasks_from_db(self):
        """从数据库加载任务"""
        # 这里可以添加从数据库加载任务的逻辑
        # 由于数据库表结构的限制，我们暂时只加载任务状态，不加载完整的任务数据
        pass
    
    def start(self):
        """启动任务系统"""
        if not self.running:
            self.running = True
            self.stop_event.clear()
            for i in range(self.max_workers):
                worker = threading.Thread(target=self._worker, daemon=True)
                worker.start()
                self.workers.append(worker)
    
    def stop(self):
        """停止任务系统"""
        self.running = False
        self.stop_event.set()
        # 向队列中添加None以唤醒所有工作线程
        for _ in range(self.max_workers):
            self.task_queue.put(None)
        # 等待所有工作线程结束
        for worker in self.workers:
            worker.join(timeout=5)
        self.workers.clear()
    
    def _worker(self):
        """工作线程"""
        while self.running:
            try:
                task = self.task_queue.get(timeout=1)
                if task is None:
                    break
                
                # 检查是否需要停止
                if self.stop_event.is_set():
                    task.status = "cancelled"
                    task.error = "Task cancelled due to system shutdown"
                    try:
                        db.save_task(task.task_id, "cancelled", task.progress, error_message="Task cancelled due to system shutdown")
                    except:
                        pass
                    self.task_queue.task_done()
                    break
                
                # 检查任务是否被取消
                if task.cancelled:
                    task.status = "cancelled"
                    task.error = "Task cancelled by user"
                    try:
                        db.save_task(task.task_id, "cancelled", task.progress, error_message="Task cancelled by user")
                    except:
                        pass
                    self.task_queue.task_done()
                    continue
                
                # 执行任务
                task.status = "running"
                task.start_time = time.time()
                
                # 更新数据库中的任务状态
                try:
                    db.save_task(task.task_id, "running", 0.0)
                except:
                    pass
                
                try:
                    def progress_callback(progress):
                        # 检查是否需要停止
                        if self.stop_event.is_set() or task.cancelled:
                            raise Exception("Task cancelled")
                        task.progress = progress
                        # 更新数据库中的任务进度
                        try:
                            db.save_task(task.task_id, "running", progress)
                        except:
                            pass
                    
                    def log_callback(message):
                        pass  # 可以添加日志处理
                    
                    # 再次检查任务是否被取消
                    if task.cancelled:
                        raise Exception("Task cancelled by user")
                    
                    # 注意：这里调用 run_batch_analysis，其内部会创建 ThreadPoolExecutor 进行并行处理
                    # 外层 TaskSystem 的 worker 数量控制并发任务数，内层线程池控制每个任务内的会话并行数
                    # 这种设计是为了：1) 任务粒度保持为整个文件，方便管理和追踪
                    # 2) 内层并行处理大量会话，提高处理速度
                    # 缺点是实际并发数 = 外层worker数 * 内层线程数，可能会超过预期
                    results, category_df = run_batch_analysis(
                            session_df=task.session_df,
                            policy_retriever=task.policy_retriever,
                            config=task.config,
                            progress_callback=progress_callback,
                            log_callback=log_callback,
                            merchant_rules=task.merchant_rules,
                            llm_service=task.llm_service
                        )
                    
                    # 检查任务是否被取消
                    if task.cancelled:
                        task.status = "cancelled"
                        task.error = "Task cancelled by user"
                        try:
                            db.save_task(task.task_id, "cancelled", task.progress, error_message="Task cancelled by user")
                        except:
                            pass
                    else:
                        task.result = (results, category_df)
                        task.status = "completed"
                        # 更新数据库中的任务状态
                        try:
                            db.save_task(task.task_id, "completed", 1.0, json.dumps({"results_count": len(results)}))
                        except:
                            pass
                except Exception as e:
                    error_msg = str(e)
                    error_code = "UNKNOWN_ERROR"
                    # 尝试提取错误代码
                    if "API error" in error_msg:
                        error_code = "API_ERROR"
                    elif "timeout" in error_msg.lower():
                        error_code = "TIMEOUT_ERROR"
                    elif "database" in error_msg.lower():
                        error_code = "DATABASE_ERROR"
                    elif "Task cancelled" in error_msg:
                        error_code = "CANCELLED"
                        task.status = "cancelled"
                    else:
                        task.status = "failed"
                    
                    task.error = {
                        "code": error_code,
                        "message": error_msg
                    }
                    # 更新数据库中的任务状态
                    try:
                        db.save_task(task.task_id, task.status, task.progress, error_message=json.dumps(task.error))
                    except:
                        pass
                
                task.end_time = time.time()
                # 从内存中移除完成的任务，避免内存泄漏
                if task.task_id in self.tasks:
                    del self.tasks[task.task_id]
                self.task_queue.task_done()
            except Exception as e:
                # 检查是否是队列为空的异常
                if "Empty" in str(type(e).__name__):
                    # 队列为空，继续循环
                    continue
                # 记录其他错误
                import traceback
                try:
                    print(f"Worker error: {str(e)}")
                    print(traceback.format_exc())
                except:
                    pass
    
    def create_task(self, session_df: pd.DataFrame, policy_retriever: Any, config: Optional[Settings] = None, merchant_id: Optional[str] = None, merchant_rules: Optional[Dict] = None, llm_service: Optional[Any] = None) -> str:
        """创建任务"""
        task_id = str(uuid.uuid4())
        config = config or default_settings
        task = Task(task_id, session_df, policy_retriever, config, merchant_id, merchant_rules, llm_service)
        self.tasks[task_id] = task
        self.task_queue.put(task)
        
        # 保存任务到数据库
        db.save_task(task_id, "pending", 0.0)
        
        return task_id
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        if task_id not in self.tasks:
            # 尝试从数据库中获取任务状态
            db_task = db.get_task_status(task_id)
            if db_task:
                return {
                    "task_id": task_id,
                    "status": db_task.get("status"),
                    "progress": db_task.get("progress", 0.0),
                    "start_time": db_task.get("created_at"),
                    "end_time": db_task.get("updated_at"),
                    "error": db_task.get("error_message")
                }
            return {"error": "Task not found"}
        
        task = self.tasks[task_id]
        return {
            "task_id": task.task_id,
            "status": task.status,
            "progress": task.progress,
            "start_time": task.start_time,
            "end_time": task.end_time,
            "error": task.error
        }
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        if task.status in ["completed", "failed", "cancelled"]:
            return False
        
        # 标记任务为已取消
        task.cancelled = True
        task.status = "cancelled"
        task.error = "Task cancelled by user"
        
        # 更新数据库中的任务状态
        try:
            db.save_task(task_id, "cancelled", task.progress, error_message="Task cancelled by user")
        except:
            pass
        
        return True
    
    def get_task_result(self, task_id: str) -> Optional[Tuple[List[Dict], pd.DataFrame]]:
        """获取任务结果"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            if task.status == "completed":
                return task.result
        
        # 任务可能已从内存中移除，但结果应该已经保存到数据库
        # 这里返回一个空的结果集，避免解包错误
        return [], pd.DataFrame(columns=['转人工类别', '数量', '占比'])
    
    def list_tasks(self) -> List[Dict[str, Any]]:
        """列出所有任务"""
        return [self.get_task_status(task_id) for task_id in self.tasks]


# 全局任务系统实例
task_system = TaskSystem()

# 启动任务系统
task_system.start()
