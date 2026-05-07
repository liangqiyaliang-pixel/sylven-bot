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
