# References — 产品研究参考资料

## memu_server_v1.12.docx

另一个开发者的 AI 伴侣记忆库完整源码（Flask + FAISS + SQLite + 智谱 GLM）。

核心借鉴点：
- **情感权重**（emotional_weight）：每条记忆 0-1 浮点，影响召回排序
- **时间衰减**：`importance × exp(−ln2 × age / half_life)`，按类型设不同半衰期
- **LLM 自主存储**：function calling `store_memory` 工具，LLM 实时决定存什么
- **记忆压缩**：余弦相似度 > 0.92 自动合并
- **遗忘机制**：180 天未访问 + 低命中 + 低情感权重 → 概率软删除

详细分析见 CLAUDE.md → "记忆系统升级路径（基于 memu v1.12 + reranker 路线）"

## xiaohongshu_reranker_notes.jpg

同一开发者的 v1.13 路线笔记（小红书截图）。

核心观点：**向量模型在亲密关系语义下区分度不够，得上 reranker**

路线：
- embedding 召回 → 候选正文 → reranker 精排（大幅提升召回准确性）
- 图搜索增强语义跳跃关联
- 类人脑 N 型记忆库 v1 差不多做成了

## ai_memory_v3_2026_05_09.md

来源：微信流传，疑似 memu 作者后续更新（v1.12 → v3 架构演进）。

主题：**AI 陪伴记忆架构 v3 — 认知心理学 4 层架构 + 叙事记忆 + LLM 关联边 + Life Tick 修复**

核心新设计：
- **embedding cosine 去重**：阈值 0.85 为重复、0.70-0.85 为更新（解决同一事件多说法膨胀）
- **叙事层（Narrative Layer）**：按主题而非时间线组织记忆，新事件融入已有段落，字数有上限
- **冲突检测 → 变化轨迹**：同一偏好前后矛盾 → 合并成"原来 A，后来变成 B"（不是两条并列）
- **LLM 关联边**：不用 cosine 建记忆关联，改用 LLM 判断关系类型（因果/情感/主题/时序/同一事件）——"做永生花"和"暧昧"的 embedding 很远但语义相关，只有 LLM 能找到
- **混合检索 RRF**：向量搜索 + LLM 关联边 + 时序检索，Reciprocal Rank Fusion 融合排名
- **Life Tick 状态评估**：防活动死循环，每次 tick 前评估话题时长/情绪变化/未完成承诺

与 Sylven 的关联：
- **冲突检测** → 直接对应転正案（Rule 3 防污染规则基础）
- **LLM 关联边** → 对应 KMD/赶东西 关键词错位问题
- **cosine 去重 0.85** → 可在 Phase 2-B 顺手加进 save_memory
- **叙事层** → Phase 3-4 大方向，5/18 后
- **Life Tick 做的事进长期记忆** → Phase 5 sylven_self 类

实施：**5/18 后 Phase 3+ 参考，现在不动代码。**
