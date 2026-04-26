# 📈 电商智能客服：转人工归因自动化系统 (AI Attribution & ROI Optimizer)

> **“不仅仅是分类，更是对 AI 运营成本的极致压榨。”**
> 本项目专注于解决大模型落地中的“幻觉问题”与“成本焦虑”。

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.9+-green)
![Framework](https://img.shields.io/badge/framework-Streamlit-FF4B4B)
![AI-Engine](https://img.shields.io/badge/AI-DeepSeek-lightgrid)

本项目是一款基于 **“规则引擎 + 大模型 (LLM)”** 集成架构的转人工归因分析系统。专为电商业务场景设计，通过多线程异步调度与语义聚类技术，实现海量客服对话数据的高效分类质检，彻底取代人工归因复盘。

---

## 🌟 核心业务战果 (Business Impact)

* **💰 成本治理**：引入语义去重算法，实现“一次推理，万次复用”，API 消耗支出直降 **70%**。
* **🎯 精度跃迁**：通过专家仲裁机制动态分配权重，意图识别准确率从 **78% 跃升至 92%**。
* **⚡ 能效提升**：实现 **20万行级** 大数据流式处理，极大地释放了运营人力成本。

---

## 🎥 演示视频与架构图 (Demo & Architecture)

### 视频演示


https://github.com/user-attachments/assets/d64f0fb2-e519-4666-becc-94210ed391b4



### 系统流转架构
<img width="700" height="825" alt="Welcome to FigJam (1)" src="https://github.com/user-attachments/assets/7193f7bd-c82c-4c72-a4c5-f05e0a659e7e" />


---

## 🧠 核心策略模块 (Strategy Modules)

### 1. ⚖️ 专家投票仲裁系统 (Expert Voting System)
* **仲裁逻辑**：针对 70% 高频确定场景采用关键词规则引擎，30% 长尾场景调用 LLM 语义推理。
* **技术实现**：构建 `WeightedEnsembleClassifier` 对规则命中得分与 AI 置信度进行动态博弈与权重分配。
* **解决痛点**：完美规避 LLM 在特定电商业务语境下产生的“一本正经胡说八道”（幻觉问题）。

### 2. 🧩 语义聚类去重引擎 (Semantic Deduplication)
* **算法方案**：利用 **TF-IDF + 余弦相似度 (Cosine Similarity)** 对海量会话进行特征提取与预处理。
* **商业价值**：精准识别相似度 > 0.85 的重复咨询（如爆款商品的相同催发货话术），同簇会话仅调用一次 LLM，将单位质检成本压榨至极限。

### 3. ⚙️ 工业级并发与背压控制 (High Concurrency & Backpressure)
* **并发安全**：采用 **SQLite WAL 模式** 与自定义连接池（Connection Pool）技术，彻底解决多线程并发下的数据库读写冲突。
* **流量削峰**：设计 **Semaphore (信号量) 背压机制**，确保 AI 消费速度与本地大文件读取速度保持平衡，系统在满载高压下依然稳如磐石，拒绝 OOM 内存溢出。

---

## 🛠️ 技术底座 (Tech Stack)

* **产品前端**：Streamlit (交互式数据面板展示)
* **AI 引擎**：DeepSeek API (Few-shot Learning / Prompt Engineering)
* **后端架构**：Python 3.9+, 并发线程池调度
* **数据存储**：SQLite (高并发 WAL 模式)
* **数据处理**：Pandas, scikit-learn (特征向量化与清洗)

---

## 🔐 履约声明与交流邀请 (Compliance & Let's Talk)

> ⚠️ **合规声明 (Disclaimer)**
> 本项目为实习期间深度参与的商业化落地项目。基于职业素养与保密协议（NDA），本仓库**仅作产品架构、策略逻辑与脱敏界面的展示，暂不开源核心业务代码、Prompt 指令集及真实生产数据**。演示视频中的分析内容均为随机生成的 Mock Data。

> 💡 **开发模式声明 (Vibe Coding)**
> 本项目代码由作者通过 **Vibe Coding** 模式主导架构设计，并驱动 AI 协作完成。旨在探索“人机协同”在复杂工程落地中的效率极限。

* **Let's Talk**: 欢迎通过 [15990070647@163.com](mailto:15990070647@163.com) 与我交流大模型商业化落地、成本优化策略及 Vibe Coding 实践经验。
