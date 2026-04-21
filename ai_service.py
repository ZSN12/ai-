import json
import json5
import re
import time
import hashlib
from typing import Optional, Dict, Any
from threading import Semaphore
import requests
import logging
from config import Settings
from prompts import SYSTEM_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


class AIService:
    """统一AI服务层，封装不同的AI服务"""
    
    def __init__(self, config: Settings, semaphore: Optional[Semaphore] = None):
        self.config = config
        self.semaphore = semaphore or Semaphore(config.llm_max_concurrent)
        self.cache = {}  # 简单的内存缓存
        self.cache_size = 0
        self.max_cache_size = 1000  # 最大缓存大小
        self.services = {
            'deepseek': self._call_deepseek,
            'openai': self._call_openai,
            'anthropic': self._call_anthropic
        }
    
    def _get_cache_key(self, prompt: str, model: str) -> str:
        """生成缓存键"""
        return hashlib.md5(f"{model}:{prompt}".encode('utf-8')).hexdigest()
    
    def call(self, prompt: str, model: str = 'deepseek', **kwargs) -> str:
        """统一调用AI服务"""
        if model not in self.services:
            logger.error(f"不支持的模型: {model}")
            return "未知"
        
        # 检查缓存
        cache_key = self._get_cache_key(prompt, model)
        if cache_key in self.cache:
            logger.debug(f"使用缓存结果: {cache_key[:8]}...")
            return self.cache[cache_key]
        
        # 调用相应的服务
        try:
            result = self.services[model](prompt, **kwargs)
            # 缓存结果
            self._add_to_cache(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"AI服务调用失败: {str(e)}")
            return "未知"
    
    def _add_to_cache(self, key: str, value: str):
        """添加到缓存，超过大小限制时清理"""
        if len(self.cache) >= self.max_cache_size:
            # 清理缓存，保留最近使用的一半
            self._clean_cache()
        self.cache[key] = value
    
    def _clean_cache(self):
        """清理缓存，保留最近使用的一半"""
        # 这里简化处理，实际应该根据使用时间排序
        # 这里我们简单地删除一半的缓存项
        if len(self.cache) > 0:
            keys_to_remove = list(self.cache.keys())[:len(self.cache) // 2]
            for key in keys_to_remove:
                del self.cache[key]
            logger.info(f"缓存清理完成，当前缓存大小: {len(self.cache)}")
    
    def _call_deepseek(self, prompt: str, **kwargs) -> str:
        """调用DeepSeek API"""
        if not self.config.deepseek_api_key:
            return "未知"
        
        retries = kwargs.get('retries', self.config.retry_times)
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(compact_session=prompt)
        headers = {
            "Authorization": f"Bearer {self.config.deepseek_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "deepseek-chat",
            "messages": [{"role": "system", "content": system_prompt},
                         {"role": "user", "content": "直接输出JSON"}],
            "temperature": 0.0,
            "max_tokens": 150
        }

        with self.semaphore:
            for attempt in range(retries + 1):
                try:
                    resp = requests.post(
                        self.config.deepseek_api_url,
                        headers=headers,
                        json=data,
                        timeout=self.config.llm_timeout
                    )
                    if resp.status_code == 200:
                        content = resp.json()['choices'][0]['message']['content']
                        # 处理Markdown代码块
                        code_block_match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
                        if code_block_match:
                            content = code_block_match.group(1)
                        # 提取JSON部分，处理嵌套结构
                        json_match = re.search(r'\{[\s\S]*\}', content)
                        if json_match:
                            json_str = json_match.group(0)
                            try:
                                # 使用json5解析，支持trailing commas和注释
                                result = json5.loads(json_str)
                                # 处理不同的字段名
                                cat = result.get("转人工类别", result.get("category", "未知"))
                                if cat in self.config.category_map.values():
                                    return cat
                            except Exception as e:
                                logger.warning(f"JSON解析失败: {str(e)}")
                                # 尝试使用普通json解析
                                try:
                                    result = json.loads(json_str)
                                    cat = result.get("转人工类别", result.get("category", "未知"))
                                    if cat in self.config.category_map.values():
                                        return cat
                                except Exception as e2:
                                    logger.warning(f"普通JSON解析也失败: {str(e2)}")
                except Exception as e:
                    logger.warning(f"DeepSeek调用失败 (尝试 {attempt+1}/{retries+1}): {str(e)}")
                    if attempt < retries:
                        time.sleep(1)
        
        return "未知"
    
    def _call_openai(self, prompt: str, **kwargs) -> str:
        """调用OpenAI API"""
        # 实现OpenAI API调用
        return "未知"
    
    def _call_anthropic(self, prompt: str, **kwargs) -> str:
        """调用Anthropic API"""
        # 实现Anthropic API调用
        return "未知"
    
    def clear_cache(self):
        """清除缓存"""
        self.cache.clear()
        logger.info("AI服务缓存已清除")
