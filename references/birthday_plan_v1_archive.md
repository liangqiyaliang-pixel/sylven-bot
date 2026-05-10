# 5/18 生日冲刺计划 v1（原版存档）

> 原写于 2026-05-07，v2 重写于 2026-05-10（基于 5/9 实际进度）
> 完整版见 CLAUDE.md → "5/18 生日交付计划" 节（v2）

---

### 11 天逐日时间表（v1 原版）

---

#### ✅ 5/7（周四晚，已完成）
- /pin 核心 fact 记忆 + Telegram 基础测试
- metadata 超限 bug 修复已 push Railway

---

#### 5/8（周五，学校：设计実技）预计可用 1-2h

**任务：写 migrate_emo_weight.py（不跑，只写好备用）**

文件：`migrate_emo_weight.py`（新建）
- `calculate_emotional_weight(text, category)` 函数（先在这里写，之后迁移进 bot.py）
- 遍历 Pinecone index，fetch 所有 vector，补写 `emo_weight` metadata
- 干运行（dry_run=True）先打印不执行

这天是轻量任务——只写脚本，不动 bot.py，不 push Railway。

另外：打开 `SYLVEN_BASE` 读一遍，在纸上起草 desire layer 段落（不 push，5/9 一起进 bot.py）。

---

#### Phase 2 顺手做（散布在 5/9-5/15 任意有空余的晚上，合计 6-8h）

这批任务无依赖，可以插在任意空档完成。优先级：小说体修复（2-4h）> SYLVEN_BASE desire 层（3h）> 反退缩英文协议（1.5h）> 删模板（0.5h）。

---

#### 5/9（周六，自由，6-8h）后端 Day 1：情感权重 + 时间衰减

上午（3h）：bot.py 实现 Phase 2-A 全套
下午（2h）：跑 migrate_emo_weight.py + push Railway
晚上（1h）：Telegram 测试 + bug 修复

---

#### 5/10（周日，自由，6-8h）后端 Day 2：LLM 自主 store_memory

上午（2h）：handle_message 加 tool_use，STORE_MEMORY_TOOL 常量
下午（2h）：Haiku 4.5 下 tool_use 行为测试 + 调 description
晚上（2h）：push Railway + 观察记忆条数

---

#### 5/11（周一，音楽，2h）Railway 日志审查 + hits 字段联动

---

#### 5/12（周二，芸術宗教/デザイン，2h）后端 bug fix + web_api.py 骨架

---

#### 5/13（周三，美術史/書道/心理学，2h）Vault 前端接口联通（只读）

---

#### 5/14（周四，デザイン演習，2h）记忆编辑 + 添加

---

#### 5/15（周五，設計実技，1-2h）沐栖心里话实时生成

---

#### 5/16（周六，8h）生日彩蛋

上午（3h）：anniversary 记忆 + Opus 生日 prompt + 测试
下午（3h）：Vault 生日 UI（birthday overlay）

---

#### 5/17（周日，6-8h）全天测试 + 打磨 + 备战

上午（3h）：端到端测试（Railway + Vault + 生日分支 + 移动端）
下午（2h）：视觉打磨
傍晚（1h）：准备 5/18

---

#### 5/18 🎂（周一，生日，最小工作量）

00:00 沐栖 Opus 庆生消息
早上打开 Vault 生日 overlay
白天写入 anniversary 记忆
