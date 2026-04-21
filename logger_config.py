# logger_config.py
import logging
import os
import re
from logging.handlers import RotatingFileHandler
from datetime import datetime


class SensitiveInfoFilter(logging.Filter):
    """敏感信息过滤器，防止API密钥等敏感信息泄露到日志中"""
    
    def filter(self, record):
        if hasattr(record, 'msg'):
            msg = str(record.msg)
            # 过滤API密钥 - 使用 \S+ 匹配包含特殊字符的Key
            msg = re.sub(r'Bearer\s+\S+', 'Bearer [REDACTED]', msg)
            msg = re.sub(r'deepseek_api_key["\']?\s*[:=]\s*\S+', 'deepseek_api_key=[REDACTED]', msg)
            msg = re.sub(r'api_key["\']?\s*[:=]\s*\S+', 'api_key=[REDACTED]', msg)
            # 过滤个人信息
            msg = re.sub(r'\b\d{11}\b', '[PHONE_REDACTED]', msg)  # 手机号
            msg = re.sub(r'\b[\w\.-]+@[\w\.-]+\.\w+\b', '[EMAIL_REDACTED]', msg)  # 邮箱
            msg = re.sub(r'\b\d{15,19}\b', '[CARD_REDACTED]', msg)  # 银行卡号
            record.msg = msg
        return True


def setup_file_logger(log_dir: str = "logs", max_bytes: int = 10 * 1024 * 1024, backup_count: int = 5, 
                   console_level: int = logging.WARNING):
    """设置文件日志和控制台日志"""
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    log_filename = os.path.join(log_dir, f"质检日志_{datetime.now().strftime('%Y-%m-%d')}.log")

    file_logger = logging.getLogger("quality_inspection_file")
    file_logger.setLevel(logging.INFO)
    
    # 防止重复添加handler
    if not file_logger.handlers:
        # 文件日志处理器
        file_handler = RotatingFileHandler(
            log_filename,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(SensitiveInfoFilter())
        file_logger.addHandler(file_handler)
        
        # 控制台日志处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        console_handler.addFilter(SensitiveInfoFilter())
        file_logger.addHandler(console_handler)

    return file_logger


def get_file_logger():
    """获取文件日志记录器"""
    logger = logging.getLogger("quality_inspection_file")
    if not logger.handlers:
        return setup_file_logger()
    return logger