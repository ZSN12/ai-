import streamlit as st
import pandas as pd
import numpy as np
import time
import datetime
import json
import re
import logging
from typing import Optional, List, Dict, Any
import traceback

from core import run_batch_analysis, PolicyRetriever, SessionPreprocessor, EnhancedRuleEngine
from prompts import SYSTEM_PROMPT_TEMPLATE, KEYWORDS
from config import Settings, settings as default_settings
from utils import (sanitize_filename, clean_text)
from logger_config import get_file_logger
from database import db
from session_manager import session_manager

# 导入UI模块
from ui.file_upload import handle_file_upload, handle_api_integration, start_analysis
from ui.monitoring import show_real_time_monitoring, show_operational_control
from ui.analysis_results import show_analysis_results
from ui.prediction import show_prediction_analysis, show_smart_suggestions
from ui.rule_management import show_rule_management
from ui.system_settings import show_system_settings

# ====================== 多语言支持 ======================
# 语言字典
LANGS = {
    "zh": {
        "title": "电商转人工质检机器人",
        "tabs": ["文件上传", "实时监控", "操作控制", "分析结果", "规则管理", "预测分析", "智能建议", "系统设置"],
        "data_source": "数据来源",
        "file_upload": "文件上传",
        "api_integration": "API集成",
        "policy_file": "店铺政策文件",
        "session_file": "会话记录文件",
        "upload_file": "上传文件",
        "start_analysis": "开始质检",
        "clear_results": "清空结果",
        "clear_cache": "清除缓存",
        "analysis_results": "分析结果",
        "rule_management": "规则管理",
        "team_collaboration": "团队协作",
        "prediction_analysis": "预测分析",
        "smart_suggestions": "智能建议",
        "system_settings": "系统设置",
        "transfer_rate": "转人工率",
        "category_distribution": "类别分布",
        "daily_trend": "日趋势",
        "real_time_monitoring": "实时监控",
        "operational_control": "操作控制",
        "active_sessions": "活跃会话",
        "avg_response_time": "平均响应时间",
        "queue_length": "队列长度",
        "stop_monitoring": "停止监控",
        "start_monitoring": "开始监控",
        "export_results": "导出结果",
        "download_csv": "下载CSV",
        "download_excel": "下载Excel",
        "download_json": "下载JSON",
        "config_saved": "配置已保存",
        "test_connection": "测试连接",
        "connection_success": "连接成功",
        "connection_failed": "连接失败",
        "api_key": "API密钥",
        "api_url": "API URL",
        "model_name": "模型名称",
        "max_workers": "最大工作线程",
        "timeout": "超时时间",
        "retry_times": "重试次数",
        "save_config": "保存配置",
        "apply_config": "应用配置",
        "current_config": "当前配置",
        "update_frequency": "更新频率",
        "alert_threshold": "告警阈值",
        "enable_email_alerts": "启用邮件告警",
        "email_recipients": "邮件接收人",
        "enable_sms_alerts": "启用短信告警",
        "sms_recipients": "短信接收人",
        "success": "成功",
        "error": "错误",
        "warning": "警告",
        "info": "信息",
        "confirm": "确认",
        "cancel": "取消",
        "close": "关闭",
        "edit": "编辑",
        "delete": "删除",
        "add": "添加",
        "save": "保存",
        "load": "加载",
        "import": "导入",
        "export": "导出",
        "search": "搜索",
        "filter": "筛选",
        "sort": "排序",
        "refresh": "刷新",
        "reset": "重置",
        "help": "帮助",
        "about": "关于",
        "version": "版本",
        "settings": "设置",
        "dashboard": "仪表盘",
        "reports": "报告",
        "analytics": "分析",
        "users": "用户",
        "tasks": "任务",
        "notifications": "通知",
        "logs": "日志",
        "profile": "个人资料",
        "logout": "退出"
    },
    "en": {
        "title": "E-commerce Transfer to Human Inspection Robot",
        "tabs": ["File Upload", "Real-time Monitoring", "Operational Control", "Analysis Results", "Rule Management", "Prediction Analysis", "Smart Suggestions", "System Settings"],
        "data_source": "Data Source",
        "file_upload": "File Upload",
        "api_integration": "API Integration",
        "policy_file": "Store Policy File",
        "session_file": "Session Record File",
        "upload_file": "Upload File",
        "start_analysis": "Start Analysis",
        "clear_results": "Clear Results",
        "clear_cache": "Clear Cache",
        "analysis_results": "Analysis Results",
        "rule_management": "Rule Management",
        "team_collaboration": "Team Collaboration",
        "prediction_analysis": "Prediction Analysis",
        "smart_suggestions": "Smart Suggestions",
        "system_settings": "System Settings",
        "transfer_rate": "Transfer Rate",
        "category_distribution": "Category Distribution",
        "daily_trend": "Daily Trend",
        "real_time_monitoring": "Real-time Monitoring",
        "operational_control": "Operational Control",
        "active_sessions": "Active Sessions",
        "avg_response_time": "Average Response Time",
        "queue_length": "Queue Length",
        "stop_monitoring": "Stop Monitoring",
        "start_monitoring": "Start Monitoring",
        "export_results": "Export Results",
        "download_csv": "Download CSV",
        "download_excel": "Download Excel",
        "download_json": "Download JSON",
        "config_saved": "Config Saved",
        "test_connection": "Test Connection",
        "connection_success": "Connection Success",
        "connection_failed": "Connection Failed",
        "api_key": "API Key",
        "api_url": "API URL",
        "model_name": "Model Name",
        "max_workers": "Max Workers",
        "timeout": "Timeout",
        "retry_times": "Retry Times",
        "save_config": "Save Config",
        "apply_config": "Apply Config",
        "current_config": "Current Config",
        "update_frequency": "Update Frequency",
        "alert_threshold": "Alert Threshold",
        "enable_email_alerts": "Enable Email Alerts",
        "email_recipients": "Email Recipients",
        "enable_sms_alerts": "Enable SMS Alerts",
        "sms_recipients": "SMS Recipients",
        "success": "Success",
        "error": "Error",
        "warning": "Warning",
        "info": "Info",
        "confirm": "Confirm",
        "cancel": "Cancel",
        "close": "Close",
        "edit": "Edit",
        "delete": "Delete",
        "add": "Add",
        "save": "Save",
        "load": "Load",
        "import": "Import",
        "export": "Export",
        "search": "Search",
        "filter": "Filter",
        "sort": "Sort",
        "refresh": "Refresh",
        "reset": "Reset",
        "help": "Help",
        "about": "About",
        "version": "Version",
        "settings": "Settings",
        "dashboard": "Dashboard",
        "reports": "Reports",
        "analytics": "Analytics",
        "users": "Users",
        "tasks": "Tasks",
        "notifications": "Notifications",
        "logs": "Logs",
        "profile": "Profile",
        "logout": "Logout"
    },
    "tl": {
        "title": "E-commerce Transfer sa Human Inspection Robot",
        "tabs": ["Mag-upload ng File", "Real-time Monitoring", "Operational Control", "Mga Resulta ng Pagsusuri", "Pamamahala ng Panuntunan", "Prediction Analysis", "Smart Suggestions", "Mga Setting ng System"],
        "data_source": "Pinagmulan ng Data",
        "file_upload": "Mag-upload ng File",
        "api_integration": "API Integration",
        "policy_file": "File ng Patakaran ng Store",
        "session_file": "File ng Tala ng Session",
        "upload_file": "Mag-upload ng File",
        "start_analysis": "Simulan ang Pagsusuri",
        "clear_results": "Linisin ang Mga Resulta",
        "clear_cache": "Linisin ang Cache",
        "analysis_results": "Mga Resulta ng Pagsusuri",
        "rule_management": "Pamamahala ng Panuntunan",
        "team_collaboration": "Pakikipagtulungan ng Team",
        "prediction_analysis": "Prediction Analysis",
        "smart_suggestions": "Mga Matalinong Mungkahi",
        "system_settings": "Mga Setting ng System",
        "transfer_rate": "Rate ng Paglilipat",
        "category_distribution": "Distribusyon ng Kategorya",
        "daily_trend": "Araw-araw na Trend",
        "real_time_monitoring": "Real-time Monitoring",
        "operational_control": "Operational Control",
        "active_sessions": "Aktibong Mga Session",
        "avg_response_time": "Average na Oras ng Pagsagot",
        "queue_length": "Haba ng Pila",
        "stop_monitoring": "Itigil ang Pagsubaybay",
        "start_monitoring": "Simulan ang Pagsubaybay",
        "export_results": "I-export ang Mga Resulta",
        "download_csv": "I-download ang CSV",
        "download_excel": "I-download ang Excel",
        "download_json": "I-download ang JSON",
        "config_saved": "Nai-save ang Config",
        "test_connection": "Subukan ang Koneksyon",
        "connection_success": "Matagumpay na Koneksyon",
        "connection_failed": "Nabigo ang Koneksyon",
        "api_key": "API Key",
        "api_url": "API URL",
        "model_name": "Pangalan ng Modelo",
        "max_workers": "Max na Mga Worker",
        "timeout": "Timeout",
        "retry_times": "Mga Beses ng Pag-subok Muli",
        "save_config": "I-save ang Config",
        "apply_config": "I-apply ang Config",
        "current_config": "Kasalukuyang Config",
        "update_frequency": "Dalas ng Update",
        "alert_threshold": "Threshold ng Alert",
        "enable_email_alerts": "I-enable ang Mga Alert sa Email",
        "email_recipients": "Mga Tatanggap ng Email",
        "enable_sms_alerts": "I-enable ang Mga Alert sa SMS",
        "sms_recipients": "Mga Tatanggap ng SMS",
        "success": "Matagumpay",
        "error": "Error",
        "warning": "Babala",
        "info": "Impormasyon",
        "confirm": "Konfirmahin",
        "cancel": "I-kansela",
        "close": "Isara",
        "edit": "I-edit",
        "delete": "I-delete",
        "add": "Magdagdag",
        "save": "I-save",
        "load": "I-load",
        "import": "I-import",
        "export": "I-export",
        "search": "Maghanap",
        "filter": "Mag-filter",
        "sort": "Mag-sort",
        "refresh": "I-refresh",
        "reset": "I-reset",
        "help": "Tulong",
        "about": "Tungkol sa",
        "version": " Bersyon",
        "settings": "Mga Setting",
        "dashboard": "Dashboard",
        "reports": "Mga Report",
        "analytics": "Analytics",
        "users": "Mga User",
        "tasks": "Mga Gawain",
        "notifications": "Mga Abiso",
        "logs": "Mga Log",
        "profile": "Profile",
        "logout": "Mag-logout"
    }
}

def _(key):
    """获取翻译"""
    current_lang = get_current_language()
    return LANGS.get(current_lang, LANGS["zh"]).get(key, key)

def get_current_language():
    """获取当前语言"""
    if 'lang' not in st.session_state:
        st.session_state.lang = 'zh'
    return st.session_state.lang

# ====================== 初始化状态 ======================
if 'session_id' not in st.session_state:
    st.session_state.session_id = session_manager.get_or_create_session()

if 'qa_results' not in st.session_state:
    st.session_state.qa_results = None

if 'category_df' not in st.session_state:
    st.session_state.category_df = None

if 'session_df' not in st.session_state:
    st.session_state.session_df = None

if 'policy_retriever' not in st.session_state:
    st.session_state.policy_retriever = None

if 'monitoring_status' not in st.session_state:
    st.session_state.monitoring_status = "stopped"

if 'transfer_rate_history' not in st.session_state:
    st.session_state.transfer_rate_history = []

if 'current_transfer_rate' not in st.session_state:
    st.session_state.current_transfer_rate = 0.0

if 'users' not in st.session_state:
    st.session_state.users = [
        {"id": 1, "name": "管理员", "role": "admin", "status": "在线"},
        {"id": 2, "name": "质检员1", "role": "inspector", "status": "在线"},
        {"id": 3, "name": "质检员2", "role": "inspector", "status": "离线"}
    ]

if 'tasks' not in st.session_state:
    st.session_state.tasks = [
        {"id": 1, "title": "质检会话1", "assignee": "质检员1", "status": "已完成", "priority": "高"},
        {"id": 2, "title": "质检会话2", "assignee": "质检员2", "status": "进行中", "priority": "中"}
    ]

if 'prediction_data' not in st.session_state:
    st.session_state.prediction_data = pd.DataFrame({
        "日期": [],
        "预测转人工率": [],
        "实际转人工率": []
    })

if 'suggestions' not in st.session_state:
    st.session_state.suggestions = []

# ====================== 主函数 ======================
def main():
    """主函数"""
    # 设置页面配置
    st.set_page_config(
        page_title=_('title'),
        page_icon="🤖",
        layout="wide"
    )
    
    # 添加自定义CSS
    st.markdown("""
    <style>
        .card {
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .success {
            background-color: #d4edda;
            color: #155724;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 10px;
        }
        .error {
            background-color: #f8d7da;
            color: #721c24;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 10px;
        }
        .warning {
            background-color: #fff3cd;
            color: #856404;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 10px;
        }
        .info {
            background-color: #d1ecf1;
            color: #0c5460;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 10px;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # 侧边栏语言选择
    with st.sidebar:
        st.title(_('title'))
        st.markdown("---")
        
        # 语言选择
        st.subheader("🌐 语言 / Language")
        lang_options = {
            "zh": "中文",
            "en": "English",
            "tl": "Tagalog"
        }
        current_lang = get_current_language()
        lang = st.radio(
            "选择语言 / Select Language",
            options=list(lang_options.keys()),
            format_func=lambda x: lang_options[x],
            index=list(lang_options.keys()).index(current_lang)
        )
        
        if st.session_state.get('lang') != lang:
            st.session_state.lang = lang
            st.rerun()
        
        # 显示上次分析结果
        if st.session_state.qa_results:
            st.success(f"📋 已从缓存恢复上次质检结果（共 {len(st.session_state.qa_results)} 条）")
        
        st.markdown("---")
        st.markdown("© 2024 电商转人工质检机器人")
    
    # 主内容区
    tab_names = LANGS[get_current_language()]["tabs"]
    tabs = st.tabs(tab_names)
    
    # ===== 1. 文件上传 =====
    with tabs[0]:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader(f"📁 {_('file_upload')}")
        
        # 数据来源选择
        data_source = st.radio(
            _('data_source'),
            [_('file_upload'), _('api_integration')],
            horizontal=True
        )
        
        if data_source == _('file_upload'):
            handle_file_upload()
        else:  # API集成
            handle_api_integration()
        
        # 开始质检按钮
        if st.button(f"🚀 {_('start_analysis')}", key="start_analysis"):
            start_analysis()
        
        # 清空结果按钮
        if st.button(f"🗑️ {_('clear_results')}", key="clear_results"):
            st.session_state.qa_results = None
            st.session_state.category_df = None
            st.success("✅ 结果已清空")
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    # ===== 2. 实时监控 =====
    with tabs[1]:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader(f"📊 {_('real_time_monitoring')}")
        show_real_time_monitoring()
        st.markdown("</div>", unsafe_allow_html=True)
    
    # ===== 3. 操作控制 =====
    with tabs[2]:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader(f"🎮 {_('operational_control')}")
        show_operational_control()
        st.markdown("</div>", unsafe_allow_html=True)
    
    # ===== 4. 分析结果 =====
    with tabs[3]:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader(f"📈 {_('analysis_results')}")
        show_analysis_results()
        st.markdown("</div>", unsafe_allow_html=True)
    
    # ===== 5. 规则管理 =====
    with tabs[4]:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader(f"📝 {_('rule_management')}")
        show_rule_management()
        st.markdown("</div>", unsafe_allow_html=True)
    
    # ===== 6. 预测分析 =====
    with tabs[5]:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader(f"🔮 {_('prediction_analysis')}")
        show_prediction_analysis()
        st.markdown("</div>", unsafe_allow_html=True)
    
    # ===== 7. 智能建议 =====
    with tabs[6]:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader(f"💡 {_('smart_suggestions')}")
        show_smart_suggestions()
        st.markdown("</div>", unsafe_allow_html=True)
    
    # ===== 8. 系统设置 =====
    with tabs[7]:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader(f"⚙️ {_('system_settings')}")
        show_system_settings()
        st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"应用程序错误: {str(e)}")
        get_file_logger().error(f"应用程序错误: {str(e)}")
        get_file_logger().error(traceback.format_exc())
