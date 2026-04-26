# config.py
import multiprocessing
from typing import List, Dict, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_prefix=""               # 环境变量无前缀
    )

    # ---------- API 配置 ----------
    deepseek_api_key: str = Field(default="", validation_alias="DEEPSEEK_API_KEY")
    deepseek_api_url: str = Field(
        default="https://api.deepseek.com/v1/chat/completions",
        validation_alias="DEEPSEEK_API_URL"
    )
    
    # ---------- 并发控制 ----------
    cpu_count: int = Field(default_factory=multiprocessing.cpu_count)
    default_workers_max: int = 10
    llm_max_concurrent: int = Field(default=5, validation_alias="LLM_MAX_CONCURRENT")
    max_workers: int = 32  # 最大工作线程数限制

    # ---------- 文件处理 ----------
    max_row_warning: int = 50000
    max_row_limit: int = 200000
    chunk_size: int = 10000
    max_file_size_mb: int = 50  # 最大文件大小限制（MB）

    # ---------- 质检参数 ----------
    prompt_version: str = "V4.6.0(2026-04-12) - Pydantic V2 配置版"
    retry_times: int = 2
    llm_timeout: int = 15
    enable_llm_cache: bool = True  # 是否启用LLM缓存
    max_cache_size: int = 1000  # 最大缓存条目数
    enable_llm_verification: bool = True  # 是否启用LLM验证
    
    # ---------- 日志配置 ----------
    log_level: str = "INFO"  # 日志级别
    log_max_bytes: int = 10 * 1024 * 1024  # 日志文件最大大小（10MB）
    log_backup_count: int = 5  # 日志备份文件数量
    enable_console_log: bool = True  # 是否启用控制台日志
    
    # ---------- 数据验证 ----------
    enable_data_validation: bool = True  # 是否启用数据验证
    enable_data_integrity_check: bool = True  # 是否启用数据完整性检查
    
    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'日志级别必须是以下之一: {", ".join(valid_levels)}')
        return v.upper()
    
    @field_validator('llm_max_concurrent', 'max_workers', 'retry_times', 'chunk_size', 'max_cache_size')
    @classmethod
    def validate_positive_int(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('该值必须为正整数')
        return v
    
    @field_validator('max_file_size_mb', 'max_row_limit', 'max_row_warning')
    @classmethod
    def validate_positive_int_or_zero(cls, v: int) -> int:
        if v < 0:
            raise ValueError('该值必须为非负整数')
        return v

    # ---------- 分类配置 ----------
    category_map: Dict[int, str] = {
        1: "商品信息不足", 2: "修改订单信息", 3: "店铺政策要求", 4: "客户要求",
        5: "售后退款退货", 6: "物流", 7: "定制服务", 8: "商品质量问题",
        9: "未知", 10: "AI关闭直接转人工"
    }
    priority_order: List[str] = [
        "售后退款退货", "物流", "商品质量问题", "修改订单信息",
        "定制服务", "商品信息不足", "客户要求", "店铺政策要求",
        "AI关闭直接转人工", "未知"
    ]

    # ---------- Type 常量 ----------
    customer_type: int = 1
    ai_types: List[int] = [2, 19, 20]
    all_human_types: List[int] = [5, 29]
    transfer_reason_type: int = 42
    ai_off_type: int = 44
    filter_types: List[int] = [6, 7, 11, 22, 23, 24, 27, 30, 36, 40, 43]

    # ---------- 输出路径 ----------
    default_report_path: str = "电商转人工质检报告.xlsx"

# 全局单例
settings = Settings()