# core.py
import json
import json5
import pandas as pd
import requests
import re
import time
import logging
import hashlib
from typing import Dict, List, Tuple, Optional
from threading import Semaphore
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

from prompts import SYSTEM_PROMPT_TEMPLATE, KEYWORDS
from config import Settings, settings as default_settings
from ai_service import AIService

# sklearn可用标志，延迟设置
SKLEARN_AVAILABLE = None

def _check_sklearn_available():
    """延迟检查sklearn是否可用"""
    global SKLEARN_AVAILABLE
    if SKLEARN_AVAILABLE is None:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            SKLEARN_AVAILABLE = True
        except ImportError:
            SKLEARN_AVAILABLE = False
    return SKLEARN_AVAILABLE

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ====================== 性能监控 ======================
class PerformanceMonitor:
    """性能监控类，用于跟踪关键操作的执行时间和资源使用情况"""
    
    def __init__(self):
        self.metrics = {}
        self.start_times = {}
    
    def start(self, operation_name: str):
        """开始监控某个操作"""
        self.start_times[operation_name] = time.time()
    
    def end(self, operation_name: str):
        """结束监控某个操作并记录执行时间"""
        if operation_name in self.start_times:
            elapsed = time.time() - self.start_times[operation_name]
            if operation_name not in self.metrics:
                self.metrics[operation_name] = []
            self.metrics[operation_name].append(elapsed)
            del self.start_times[operation_name]
            return elapsed
        return None
    
    def get_stats(self, operation_name: str) -> Dict:
        """获取某个操作的统计信息"""
        if operation_name not in self.metrics or not self.metrics[operation_name]:
            return {"count": 0, "avg": 0, "min": 0, "max": 0}
        
        times = self.metrics[operation_name]
        return {
            "count": len(times),
            "avg": sum(times) / len(times),
            "min": min(times),
            "max": max(times)
        }
    
    def log_summary(self):
        """记录性能摘要"""
        for operation, times in self.metrics.items():
            if times:
                stats = self.get_stats(operation)
                logger.info(f"性能统计 - {operation}: 执行次数={stats['count']}, "
                           f"平均时间={stats['avg']:.3f}s, "
                           f"最小时间={stats['min']:.3f}s, "
                           f"最大时间={stats['max']:.3f}s")


# 全局性能监控器
performance_monitor = PerformanceMonitor()


# ====================== 会话有效性判断 ======================
def is_valid_session(df: pd.DataFrame, config: Settings) -> bool:
    if df.empty:
        return False
    df_clean = df[~df['Type'].isin(config.filter_types)].copy()
    if df_clean.empty:
        return False
    if (df_clean['Type'] == config.transfer_reason_type).any() or (
            df_clean['Type'] == config.ai_off_type).any():
        return True
    human_mask = df_clean['Type'].isin(config.all_human_types)
    if human_mask.any():
        first_human_idx = df_clean[human_mask].index[0]
        preceding = df_clean.loc[:first_human_idx].iloc[:-1]
        if (preceding['Type'] == config.customer_type).any():
            return True
    return False


def build_compact_conversation(df: pd.DataFrame, config: Settings) -> Tuple[str, List[str], bool]:
    lines = []
    transfer_reasons = []
    has_ai_off = False

    for _, row in df.iterrows():
        msg_type = row['Type']
        # 验证msg_type是否为整数
        if not isinstance(msg_type, int):
            msg_type = 0
        # 安全处理Message字段，防止注入
        msg = str(row['Message']).strip() if pd.notna(row['Message']) else ""
        # 清理特殊字符，防止注入攻击
        msg = msg.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')

        if msg_type in config.filter_types:
            continue

        if msg_type == config.transfer_reason_type:
            reason = None
            match = re.search(r'Transfer to human reason:\s*"([^"]+)"', msg)
            if match:
                reason = match.group(1).strip()
            else:
                match = re.search(r'转(?:给)?人工理由[：:]\s*[“"]([^”"]+)[”"]', msg)
                if match:
                    reason = match.group(1).strip()
                else:
                    if "无售后" in msg or "after-sales" in msg.lower():
                        reason = "No after-sales service"
                    elif "图片" in msg or "视频" in msg or "image" in msg.lower():
                        reason = "Set to transfer to human for images/videos"
                    elif "AI" in msg and "转人工" in msg:
                        reason = "AI determined the need to transfer to human"
            if reason:
                transfer_reasons.append(reason)
                lines.append(f"[系统转人工原因] {reason}")
            else:
                lines.append(f"[系统转人工提示] {msg[:80]}")
            continue

        if msg_type == config.ai_off_type:
            has_ai_off = True
            lines.append("[系统] AI接待已关闭，直接转人工")
            continue

        role_map = {
            1: "客户", 2: "AI(抖店)", 5: "人工(抖店)",
            19: "AI(TikTok)", 20: "AI系统(TikTok)", 29: "人工(TikTok)",
            41: "系统欢迎语"
        }
        role = role_map.get(msg_type, f"系统({msg_type})")
        if len(msg) > 200:
            msg = msg[:200] + "..."
        if msg:
            lines.append(f"[{role}] {msg}")

    return "\n".join(lines), transfer_reasons, has_ai_off


# ====================== 规则引擎 ======================
class EnhancedRuleEngine:
    def __init__(self, config: Settings, merchant_rules: Optional[Dict] = None):
        self.config = config
        self.merchant_rules = merchant_rules

    def classify_by_rules(self, df: pd.DataFrame) -> Tuple[str, str, List[str]]:
        customer_msgs = df[df['Type'] == self.config.customer_type]['Message'].astype(str).tolist()
        customer_text = " ".join(customer_msgs).lower()

        _, transfer_reasons, has_ai_off = build_compact_conversation(df, self.config)
        has_ai = any(df['Type'].isin(self.config.ai_types))

        if not has_ai and has_ai_off:
            return "AI关闭直接转人工", "AI关闭后直接转人工，无有效触发问题", transfer_reasons

        # 优先处理转人工原因
        for reason in transfer_reasons:
            rl = reason.lower()
            if "no after-sales" in rl or "无售后" in rl:
                return "店铺政策要求", "系统设置售后需人工处理", transfer_reasons

            if "image" in rl or "video" in rl or "图片" in reason or "视频" in reason:
                # 更细致的图片/视频场景分类
                if self._match_keywords(customer_text, "物流"):
                    return "物流", "客户发送图片/视频反馈物流问题", transfer_reasons
                if self._match_keywords(customer_text, "商品质量问题"):
                    return "商品质量问题", "客户发送图片/视频反馈质量问题", transfer_reasons
                if self._match_keywords(customer_text, "定制服务"):
                    return "定制服务", "客户发送图片/视频咨询定制", transfer_reasons
                if self._match_keywords(customer_text, "商品信息不足"):
                    return "商品信息不足", "客户发送图片/视频询问商品信息", transfer_reasons
                if self._match_keywords(customer_text, "售后退款退货"):
                    return "售后退款退货", "客户发送图片/视频反馈售后问题", transfer_reasons
                return "未知", "客户发送图片/视频，无法确定业务类别", transfer_reasons

            if "ai determined" in rl or "ai判断" in rl:
                # 更细致的AI判断场景分类
                if self._match_keywords(customer_text, "售后退款退货"):
                    return "售后退款退货", "客户反馈售后问题，AI转人工", transfer_reasons
                if self._match_keywords(customer_text, "物流"):
                    return "物流", "客户反馈物流问题，AI转人工", transfer_reasons
                if self._match_keywords(customer_text, "商品质量问题"):
                    return "商品质量问题", "客户反馈质量问题，AI转人工", transfer_reasons
                if self._match_keywords(customer_text, "定制服务"):
                    return "定制服务", "客户提供定制信息，AI转人工", transfer_reasons
                if self._match_keywords(customer_text, "修改订单信息"):
                    return "修改订单信息", "客户要求修改订单，AI转人工", transfer_reasons
                if self._match_keywords(customer_text, "商品信息不足"):
                    return "商品信息不足", "客户询问商品信息，AI转人工", transfer_reasons
                if self._match_keywords(customer_text, "客户要求"):
                    return "客户要求", "客户要求转人工服务", transfer_reasons
                return "客户要求", "AI判断需人工介入", transfer_reasons

        # 基于客户消息的分类
        matched = []
        for cat in self.config.priority_order[:-2]:
            if self._match_keywords(customer_text, cat):
                matched.append(cat)

        if matched:
            # 按照优先级排序，选择最高优先级的类别
            for cat in self.config.priority_order:
                if cat in matched:
                    core = customer_text[:50] if customer_text else "客户未明确表述"
                    return cat, core, transfer_reasons

        # 尝试基于所有消息（包括AI回复）进行分类
        all_msgs = df['Message'].astype(str).tolist()
        all_text = " ".join(all_msgs).lower()
        
        # 检查是否包含转人工理由，但不包含具体业务关键词
        has_transfer_reason = any("转人工" in msg.lower() for msg in all_msgs)
        has_business_keywords = False
        
        for cat in self.config.priority_order[:-2]:
            if cat != "客户要求" and self._match_keywords(all_text, cat):
                has_business_keywords = True
                core = all_text[:50] if all_text else "无有效对话"
                return cat, core, transfer_reasons
        
        # 如果只有转人工理由但没有具体业务关键词，且转人工理由是"其他"，返回"未知"
        if has_transfer_reason and not has_business_keywords:
            for msg in all_msgs:
                if "转人工理由" in msg and "其他" in msg:
                    return "未知", "无有效对话", transfer_reasons
        
        # 检查客户要求
        if self._match_keywords(all_text, "客户要求"):
            return "客户要求", "客户要求转人工服务", transfer_reasons

        return "未知", customer_text[:50] if customer_text else "无有效对话", transfer_reasons

    def _match_keywords(self, text: str, category: str) -> bool:
        # 优先检查商家自定义规则
        if self.merchant_rules and category in self.merchant_rules:
            for lang_dict in self.merchant_rules[category].values():
                for kw in lang_dict:
                    if kw in text:
                        return True
        # 再检查默认规则
        if category not in KEYWORDS:
            return False
        for lang_dict in KEYWORDS[category].values():
            for kw in lang_dict:
                if kw in text:
                    return True
        return False





# ====================== 政策检索器 ======================
class PolicyRetriever:
    def __init__(self, policy_df: pd.DataFrame, config: Optional[Settings] = None):
        self.policy_df = policy_df
        self.config = config or default_settings
        self.vectorizer = None
        self.tfidf_matrix = None
        self.documents = []
        self.policy_ids = []
        self.policy_contents = []
        self._build_index()

    def _build_index(self):
        if self.policy_df.empty:
            return
        for _, row in self.policy_df.iterrows():
            topic = str(row.get('Topic', ''))
            content = str(row.get('Content', ''))
            keywords = str(row.get('Keywords', ''))
            full_text = f"{topic} {content} {keywords}"
            self.documents.append(full_text)
            self.policy_ids.append(topic)
            self.policy_contents.append(content[:300])

        if not _check_sklearn_available():
            return

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            self.vectorizer = TfidfVectorizer(
                max_features=5000,
                stop_words='english',
                ngram_range=(1, 2),
                lowercase=True
            )
            self.tfidf_matrix = self.vectorizer.fit_transform(self.documents)
            logger.info(f"政策索引构建完成，共 {len(self.documents)} 条")
        except Exception as e:
            logger.warning(f"政策索引构建失败: {e}")

    def retrieve(self, query: str, top_k: int = 3, threshold: float = 0.1) -> List[Dict]:
        if not query or self.policy_df.empty:
            return []

        if not _check_sklearn_available() or self.vectorizer is None:
            return self._fallback_keyword_match(query, top_k)

        try:
            from sklearn.metrics.pairwise import cosine_similarity
            query_vec = self.vectorizer.transform([query])
            similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
            top_indices = similarities.argsort()[::-1]
            results = []
            for idx in top_indices:
                if similarities[idx] < threshold:
                    break
                results.append({
                    "政策编号": self.policy_ids[idx],
                    "政策原文": self.policy_contents[idx],
                    "相似度": round(float(similarities[idx]), 3)
                })
                if len(results) >= top_k:
                    break
            return results
        except Exception:
            return self._fallback_keyword_match(query, top_k)

    def _fallback_keyword_match(self, query: str, top_k: int) -> List[Dict]:
        query_lower = query.lower()
        matched = []
        
        # 定义关键词权重
        keyword_weights = {
            "售后": 3, "after-sales": 3, "refund": 3, "退款": 3, "return": 3, "退货": 3,
            "cancel": 2, "取消": 2, "modify": 2, "修改": 2, "logistics": 2, "物流": 2
        }
        
        for i, doc in enumerate(self.documents):
            doc_lower = doc.lower()
            score = 0
            
            # 计算关键词匹配得分
            for kw, weight in keyword_weights.items():
                if kw in query_lower:
                    # 计算关键词在文档中的出现次数
                    kw_count = doc_lower.count(kw)
                    if kw_count > 0:
                        # 得分 = 权重 * 出现次数
                        score += weight * kw_count
            
            if score > 0:
                # 考虑文档长度，避免长文档得分过高
                doc_length = len(doc)
                # 归一化得分，除以文档长度的平方根
                normalized_score = score / (doc_length ** 0.5)
                matched.append((normalized_score, score, i))
        
        # 按归一化得分排序，得分相同则按原始得分排序，再按文档索引排序（保证稳定性）
        matched.sort(key=lambda x: (-x[0], -x[1], x[2]))
        
        results = []
        for normalized_score, original_score, idx in matched[:top_k]:
            results.append({
                "政策编号": self.policy_ids[idx],
                "政策原文": self.policy_contents[idx],
                "得分": round(normalized_score, 3)
            })
        return results


# ====================== 会话预处理（拆分后） ======================
class SessionPreprocessor:
    """负责会话数据清洗、截断、有效性判断"""
    def __init__(self, config: Settings):
        self.config = config

    def preprocess(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """清洗并返回可用的对话数据（截断至人工介入前），若无效则返回 None"""
        df_clean = df[~df['Type'].isin(self.config.filter_types)].copy()
        if df_clean.empty or not is_valid_session(df_clean, self.config):
            return None

        human_idx = df_clean[df_clean['Type'].isin(self.config.all_human_types)].index
        if len(human_idx) > 0:
            human_pos = df_clean.index.get_loc(human_idx[0])
            df_clean = df_clean.iloc[:human_pos].copy()
            if df_clean.empty:
                return None
        return df_clean

    def extract_trigger_time(self, df: pd.DataFrame) -> str:
        """提取转人工触发时间"""
        if 'Timestamp' in df.columns:
            mask = df['Type'].isin([self.config.transfer_reason_type, self.config.ai_off_type] + self.config.all_human_types)
            if mask.any():
                return str(df.loc[mask, 'Timestamp'].iloc[0])
        return ""


# ====================== 会话分类器（拆分后） ======================
class SessionClassifier:
    """负责规则+LLM的分类流程"""
    def __init__(self, config: Settings, rule_engine: EnhancedRuleEngine, llm_service: AIService):
        self.config = config
        self.rule_engine = rule_engine
        self.llm_service = llm_service

    def classify(self, df_clean: pd.DataFrame) -> Tuple[str, str, str]:
        """返回 (类别, 核心问题, 备注)"""
        # 规则引擎分类
        category, core_issue, reasons = self.rule_engine.classify_by_rules(df_clean)
        
        # 根据配置决定是否调用LLM进行验证
        if self.config.enable_llm_verification:
            # 调用LLM进行验证
            compact_text, _, _ = build_compact_conversation(df_clean, self.config)
            llm_cat = self.llm_service.call(compact_text, model='deepseek')
            
            # 比较规则引擎和LLM的结果
            if llm_cat != "未知":
                if category == "未知":
                    # 规则引擎无法分类，使用LLM结果
                    category = llm_cat
                    remark = f"LLM兜底 | {self.config.prompt_version}"
                elif category != llm_cat:
                    # 规则引擎和LLM结果不一致，使用LLM结果（更准确）
                    category = llm_cat
                    remark = f"LLM修正 | 原规则分类:{category} | {self.config.prompt_version}"
                else:
                    # 规则引擎和LLM结果一致，使用该结果
                    remark = f"规则+LLM一致 | 信号:{','.join(reasons) if reasons else '无'} | {self.config.prompt_version}"
            else:
                # LLM也无法分类，使用规则引擎结果
                if category == "未知":
                    remark = f"规则&LLM均无法分类 | {self.config.prompt_version}"
                else:
                    remark = f"规则引擎直出 | 信号:{','.join(reasons) if reasons else '无'} | {self.config.prompt_version}"
        else:
            # 不使用LLM验证，直接使用规则引擎结果
            if category == "未知":
                remark = f"仅规则引擎 | 无法分类 | {self.config.prompt_version}"
            else:
                remark = f"仅规则引擎 | 信号:{','.join(reasons) if reasons else '无'} | {self.config.prompt_version}"

        return category, core_issue[:50], remark


# ====================== 单会话处理（重构后） ======================
def process_single_session(
        group_data: Tuple,
        preprocessor: SessionPreprocessor,
        classifier: SessionClassifier
) -> Tuple[Optional[Dict], str]:
    session_id, df = group_data
    try:
        df_clean = preprocessor.preprocess(df)
        if df_clean is None:
            return None, f"⏭️ 会话{session_id}：无效会话，跳过"

        third_id = str(df_clean.iloc[0]['三方会话id']) if '三方会话id' in df_clean.columns else ""
        trigger_time = preprocessor.extract_trigger_time(df_clean)

        category, core_issue, remark = classifier.classify(df_clean)

        result = {
            "会话ID": str(session_id),
            "第三方会话ID": third_id,
            "转人工触发时间": trigger_time,
            "转人工类别": category,
            "核心触发问题": core_issue,
            "引用店铺政策": [],
            "质检备注": remark
        }
        return result, f"✅ 会话{session_id} → {category}"
    except Exception as e:
        logger.exception(f"会话{session_id}处理异常")
        return None, f"❌ 会话{session_id}异常: {str(e)}"


# ====================== 政策匹配 ======================
def match_policies(results: List[Dict], retriever: Optional[PolicyRetriever]):
    if retriever is None:
        return
    for res in results:
        if res["转人工类别"] != "店铺政策要求":
            continue
        query = res["核心触发问题"]
        matched = retriever.retrieve(query, top_k=3, threshold=0.1)
        if matched:
            policies = [{"政策编号": m["政策编号"], "政策原文": m["政策原文"]} for m in matched]
            res["引用店铺政策"] = policies
            res["质检备注"] += f" | 匹配到 {len(policies)} 条政策"
        else:
            res["引用店铺政策"] = []
            res["质检备注"] += " | 未匹配到相关政策"


# ====================== 动态并发 ======================
def calculate_optimal_workers(total_sessions: int, config: Settings) -> int:
    """根据会话数量和系统资源动态计算最优线程数"""
    import psutil
    
    # 获取系统可用内存（GB）
    available_memory = psutil.virtual_memory().available / (1024 ** 3)
    
    # 基础线程数计算
    if total_sessions < 100:
        base_workers = min(5, config.cpu_count)
    elif total_sessions < 1000:
        base_workers = min(10, config.cpu_count * 2)
    else:
        base_workers = min(20, config.cpu_count * 3)
    
    # 根据可用内存调整线程数
    # 假设每个线程需要约0.5GB内存
    memory_based_workers = int(available_memory / 0.5)
    memory_based_workers = max(1, memory_based_workers)
    
    # 综合考虑CPU和内存限制
    optimal_workers = min(base_workers, memory_based_workers)
    
    # 确保线程数在合理范围内
    optimal_workers = max(1, min(optimal_workers, 32))  # 最大线程数限制为32
    
    return optimal_workers


def run_batch_analysis(
        session_df: pd.DataFrame,
        policy_retriever: Optional[PolicyRetriever] = None,
        config: Optional[Settings] = None,
        progress_callback=None,
        log_callback=None,
        merchant_rules: Optional[Dict] = None,
        llm_service: Optional[AIService] = None
) -> Tuple[List[Dict], pd.DataFrame]:
    config = config or default_settings

    # 预处理和分类器实例
    preprocessor = SessionPreprocessor(config)
    rule_engine = EnhancedRuleEngine(config, merchant_rules=merchant_rules)
    
    # 如果没有提供AI服务，创建一个新的
    if llm_service is None:
        llm_semaphore = Semaphore(config.llm_max_concurrent)
        llm_service = AIService(config, semaphore=llm_semaphore)
    
    classifier = SessionClassifier(config, rule_engine, llm_service)

    results = []
    groups = list(session_df.groupby('会话ID'))
    total = len(groups)
    optimal_workers = calculate_optimal_workers(total, config)

    if log_callback:
        log_callback(f"📊 总会话数：{total}，动态并发线程数：{optimal_workers}，LLM 最大并发：{config.llm_max_concurrent}")

    start_time = time.time()
    completed = 0
    with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
        futures = {
            executor.submit(process_single_session, g, preprocessor, classifier): g
            for g in groups
        }
        for future in as_completed(futures):
            result, log_msg = future.result()
            if result is not None:
                results.append(result)
            if log_callback:
                log_callback(log_msg)
            completed += 1
            if progress_callback:
                # 计算进度和时间
                progress = completed / total
                elapsed = time.time() - start_time
                avg_time = elapsed / completed if completed > 0 else 0
                remaining = (total - completed) * avg_time
                # 只传递进度值，避免在子线程中更新UI
                progress_callback(progress)

    if results:
        match_policies(results, policy_retriever)

    result_df = pd.DataFrame(results)
    if not result_df.empty:
        category_count = result_df['转人工类别'].value_counts().reset_index()
        category_count.columns = ['转人工类别', '数量']
        category_count['占比'] = (category_count['数量'] / len(result_df) * 100).round(2).astype(str) + "%"
    else:
        category_count = pd.DataFrame(columns=['转人工类别', '数量', '占比'])

    return results, category_count