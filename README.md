# 电商智能客服：转人工归因自动化系统 (AI Attribution & ROI Optimizer)

> [cite_start]“不仅仅是分类，更是对 AI 运营成本的极致压榨。” 本项目专注于解决大模型落地中的“幻觉问题”与“成本焦虑” [cite: 55, 56]。

---

## 📈 核心业务战果
  **成本治理**：引入语义去重算法，API 消耗支出直降 **70%** 。
  **精度跃迁**：通过专家仲裁机制，意图识别准确率从 **78% 提升至 92%** 。
  **能效提升**：实现 **20万行级** 大数据流式处理，彻底取代人工归因复盘 。

## 🧠 核心策略模块 (Strategy Modules)

1. 专家投票仲裁系统 (Expert Voting System) [cite: 62]
**仲裁逻辑**：针对 70% 高频确定场景采用关键词规则引擎，30% 长尾场景调用 LLM 。

**解决痛点**：通过 `WeightedEnsembleClassifier` 对规则与 AI 结果进行动态权重分配，有效规避 LLM 的“幻觉”问题 。

### [cite_start]2. 语义聚类去重引擎 (Semantic Deduplication) [cite: 66]
- [cite_start]**算法方案**：利用 **TF-IDF + 余弦相似度** 对会话进行预处理 [cite: 67]。
- [cite_start]**商业价值**：识别相似度 > 0.85 的重复咨询，实现“一次推理，万次复用”，将单位质检成本控制在极低水平 。

## ⚙️ 技术决策 (Technical Decisions)
- [cite_start]**性能与稳定性**：采用 **SQLite WAL 模式** 与连接池技术，解决多线程并发下的读写冲突 [cite: 70]。
- [cite_start]**背压控制**：设计 **Semaphore（信号量）机制**，平衡 AI 消费速度与数据读取速度，确保高负载下的系统稳健性 [cite: 71]。

## 🛠 技术栈
- [cite_start]**AI**: DeepSeek API, Few-shot Learning, Semantic Clustering [cite: 73]
- [cite_start]**Backend**: Python 3.9+, SQLite (Connection Pool), Pandas [cite: 74]
- [cite_start]**UI**: Streamlit (Data Dashboard) 

---
[cite_start]*本项目代码由作者通过 **Vibe Coding** 模式主导设计并驱动 AI 协作完成 [cite: 76]。*
