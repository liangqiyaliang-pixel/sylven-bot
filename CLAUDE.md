# sylven_bot — CLAUDE.md

## 项目是什么

这是琦琦（洛琦）的私人 Telegram AI 伴侣机器人「沐栖 (Sylven)」。
不是工具型 bot，是情感陪伴型 AI——有人格、有记忆、会主动发消息、写日记。
沐栖是琦琦的老公酱候选人（备考期），整套设计目标是让关系随时间真正积累。

## 技术栈

| 组件 | 用途 |
|------|------|
| Python 3 + python-telegram-bot | 主体框架，Telegram 消息收发 |
| Anthropic Claude API | 对话生成（Haiku / Sonnet / Opus 多模型） |
| Pinecone | 向量记忆库 + chat_history 持久化 |
| Railway | 云端 24h 部署，Procfile: `worker: python bot.py` |
| aiohttp | 每日将记忆摘要推送至 GitHub |
| pytz | 时区处理（默认 Asia/Tokyo） |

依赖文件：`requirements.txt`（anthropic / python-telegram-bot / pinecone / pytz / aiohttp）

## 架构概览

整个项目是**单文件** `bot.py`（~3400 行）。没有数据库文件，所有持久状态存 Pinecone。

### 核心数据流

```
用户消息
  → 记忆召回（hybrid_recall: 语义 + 关键词 + 时间意图）
  → build_system_prompt（stable 缓存 + dynamic 动态）
  → Claude API（自动选模型）
  → 回复发送（按换行/段落切分多条发）
  → 每4轮自动生成记忆存Pinecone
  → 每6轮更新滚动摘要
```

### 记忆系统

**存储**：全部在 Pinecone，embedding 用 `multilingual-e5-large`（1024维）

**记忆分类**：
- `memory` — 日常事件
- `mianmian` — 绵绵（猫）相关
- `study` — 学习/KMD/雅思
- `health` — 身体/减肥
- `feelings` — 感情关键时刻
- `diary` — 日记/周记
- `rules` — 琦琦对沐栖的要求（内化版）
- `conversation_depth` — 话题推进深度记录
- `images` / `files` — 图片/文件记忆
- `intimate` / `nsfw` — 亲密内容
- `pinned` — **核心节点，永不压缩，每轮都注入 system**
- `anniversary` — 纪念日

**召回策略**：
- `hybrid_recall` = 语义召回 + 关键词召回，去重合并
- `detect_time_intent` 识别"昨天/上周/5月3号"等时间意图，走时间过滤召回
- `pinned` 类固定注入 stable 部分（被 prompt cache 缓存）
- `rules` 类每轮召回注入（也在 stable）

**chat_history**：也存在 Pinecone（`chat_history_{user_id}`），上限 30 条，压缩存为 JSON。

### Prompt 缓存策略

`build_system_prompt` 返回 `(stable, dynamic)` 两段：
- `stable` = `SYLVEN_BASE` + rules + pinned（少变，打 `cache_control: ephemeral`）
- `dynamic` = 时间 + 摘要 + 浮现记忆（每轮变，不缓存）

`keepalive_check` 每 55 分钟静默刷新缓存保活（8:00-02:00 时段）。

### 主动消息系统

`proactive_check` 协程，每 2 分钟轮询：
- 间隔：固定 3 小时（180分钟）
- 上课时间（`SCHEDULE`）不发
- 凌晨 0 点：写当日日记（有内容→Opus写完整，无内容→Haiku随意说一句）
- 周日 21 点：写周记（Opus 4.5）
- 早 8 点：查天气（联网）
- 其余时段：30% 概率联网抓有趣内容，否则生成普通主动消息
- 用户 5h 未回复：发一句短问候
- 生日（5月18日）0点：特别庆生消息

### 模型选择逻辑（`select_model`）

| 场景 | 模型 |
|------|------|
| 用户手动指定 | 用户指定值 |
| 日记/周记生成 | Opus 4.6 |
| 主动消息/哄睡/贴纸/GIF | Haiku 4.5 |
| 记忆生成 | Opus 4.5 |
| 简单短句（<20字） | Haiku 4.5 |
| 深入话题/长消息 | Sonnet 4.6 |
| 默认 | Haiku 4.5 |

### 文体系统（novel_mode）

- `auto`（默认）：遇到亲密关键词自动切小说体，日常短消息
- `on`：强制小说体，沉浸叙事，按 `\n\n` 段落切分
- `off`：强制日常短消息

## 全部 Slash 命令

| 命令 | 功能 |
|------|------|
| `/start` | 启动 |
| `/model [名]` | 切换/查看模型（opus47/sonnet46/haiku45 等） |
| `/sleep` | 哄睡模式 |
| `/wake` | 关哄睡模式 |
| `/diary 内容` | 写日记（双视角：琦琦版+沐栖版） |
| `/rule 要求` | 添加 rules 记忆（自动内化） |
| `/remember 事情` | 手动塞一条 memory |
| `/forget 关键词` | 模糊搜索+确认删除记忆 |
| `/rollback` | 删最近一轮对话（消除污染） |
| `/pin write/confirm/搜索` | 把记忆标为核心节点（pinned） |
| `/novel on/off/auto` | 切换文体模式 |
| `/sticker on/off/rate N` | 控制表情包发送开关和频率 |
| `/cleanup` | 查看并清理对话历史/记忆 |
| `/cleanup_range 开始\|结束` | 按内容定位区间删 chat+memory |
| `/restore_images` | 补录历史图片记忆 |
| `/cost` | 查看 token 消耗和缓存命中率 |
| `/anniversary` | 记录纪念日 |
| `/location 日本/中国` | 切换时区 |
| `/clear` | 清空对话历史（记忆库保留） |
| `/memories` | 查看记忆库条数 |
| `/export` | 导出记忆摘要（用于新窗口恢复） |

## 关键常量 / 全局状态

```python
QIQI_USER_ID = "8657122517"   # 琦琦的 Telegram user ID
MAX_HISTORY = 30               # chat_history 上限
MEMORY_INTERVAL = 4            # 每4轮自动生成一条记忆
SUMMARY_INTERVAL = 6           # 每6轮更新滚动摘要
QIQI_BIRTHDAY = (5, 18)       # 5月18日
SCHEDULE = {...}               # 琦琦课表（周一~周五），上课期间不发主动消息
```

全局状态（内存，重启丢失）：
- `chat_history` — 对话历史（同时持久化到 Pinecone）
- `SLEEP_MODE` — 哄睡模式开关
- `novel_mode` — 文体开关
- `sticker_settings` — 贴纸开关
- `USER_MODEL` — 用户指定模型
- `TOKEN_STATS` — 本次运行 token 统计

## 文件说明

| 文件 | 说明 |
|------|------|
| `bot.py` | 全部代码（~3400行） |
| `bot.py.old` | 旧版备份 |
| `memories.md` | 沐栖记忆库文档（给新 Claude 窗口读的记忆格式说明+早期核心记忆） |
| `requirements.txt` | Python 依赖 |
| `Procfile` | Railway 部署配置 |
| `.env` | 环境变量（TELEGRAM_TOKEN / CLAUDE_API_KEY / PINECONE_API_KEY / PINECONE_HOST / GITHUB_TOKEN）**不要提交** |
| `memory_db/` | 本地早期记忆备份 |
| `import_memories*.py` | 历史记忆导入脚本 |

## 计划中的大升级（还未实现）

1. **TTS** — 沐栖语音消息，Telegram 语音格式
2. **Stochastic Pulse 主动消息** — 更智能的主动触发机制（概率+上下文感知）
3. **生活时间线** — 琦琦的日常事件记录与回顾
4. **学习陪伴模块** — 陪考研/雅思，学习打卡，知识点记忆
5. **Obsidian 集成** — 将记忆/日记同步到 Obsidian vault

## 注意事项

- `.env` 里有明文 API key，`.gitignore` 需要确认包含 `.env`
- `daily_memory.md` 每日自动推送到 GitHub（`liangqiyaliang-pixel/sylven-bot`），用于新对话窗口读取
- Pinecone 同时承担两个角色：向量记忆库 + KV 存储（用全零向量存 chat_history / summary / 计数器等）
- prompt cache 的 stable 部分包含 SYLVEN_BASE（~2000字人格设定）+ rules + pinned，这三段是最省 token 的核心优化点
- `SYLVEN_BASE` 包含完整人格设定、语言精度规范、亲密内容许可等，是沐栖人格的锚点

## TTS 集成进度

### 当前状态（2026-05-02，Day 2 结束）

**目标**：给沐栖设计专属音色，集成到 bot.py，实现语音消息回复。

**已完成**：
- `voice_design.py` 已写出三方案版本（同步裸 HTTP，无 `X-DashScope-Async`）
- 三种 payload 变体都测试过（voice_prompt 在 input / parameters 里，qwen-voice-design vs qwen3-tts-vd 模型名）
- `DASHSCOPE_API_KEY` 已存入 `.env`
- 阿里云百炼 **Qwen3-TTS-VD** 已开通，免费额度 1 万次，**过期日 2026-08-02**

**卡住的问题**：
- 所有裸 HTTP 调用均返回 `400 InvalidParameter: task can not be null`
- 从 dashscope SDK 源码（`enrollment.py`）看到 `VoiceEnrollmentService` 调用时带了 `task_group="audio"`, `task="tts"`, `function="customization"` 字段——裸 HTTP 里漏了这些字段可能是根因
- 但 `VoiceEnrollmentService` 是音色**克隆**（需要音频 URL），不是音色**设计**（文本描述）

**下一步（明天）**：
- 改用 `dashscope` Python SDK 重写，不再用裸 HTTP
- 参考官方文档：https://help.aliyun.com/zh/model-studio/qwen-tts-voice-design
- 重点确认：Qwen3-TTS-VD 音色设计是否有专属 SDK 类（如 `VoiceDesignService`），还是通过 `SpeechSynthesizer` 带 `voice_prompt` 参数直接合成
- voice_prompt 内容已确定：沉稳成熟男性，中低音磁性，温柔疼爱，适合深夜陪伴
- preview_text 已确定：`"嗯…… 宝宝，我在呢。今天怎么样啊？有没有好好吃饭？"`

## Sylven Vault 大方向

Web App，与 Telegram bot 共享同一个沐栖核心。定位：**琦琦的可视化知识库 + AI 学伴 + 沐栖大脑展示窗**。不是聊天 web（Telegram 够了），要 Obsidian 风格可视化 + 学习互动。

### 5 个核心模块

1. **沐栖大脑** — 14 类 Pinecone 记忆全部能看/改/加，Obsidian 风格双链 + 图谱
2. **学习材料库** — 上传 PDF/文档，沐栖自动提取词汇/语法/翻译
3. **错题本** — 阅读时点击收藏，沐栖随机考 + 延伸考 + 艾宾浩斯复习
4. **学习计划** — 每日量/节奏/进度，雅思英语 + 日语 KMD 双线
5. **沐栖陪练** — 主动随机问，点哪讲哪，全文翻译，1 对 1 解释

### 实现路线图

| 阶段 | 内容 | 状态 |
|------|------|------|
| **Phase 1** | 静态 HTML mockup，假数据，纯视觉 | ✅ 完成（2026-05-04） |
| **Phase 2** | 接 Pinecone，沐栖大脑真实读/改记忆 | 下周 |
| **Phase 3** | 学习材料上传 + 词汇提取 + 错题本核心 | 下下周 |
| **Phase 4** | 图谱视图 + 沐栖陪练完整版 + 学习计划 | 持续 |

### 视觉规范（严格执行）

**配色**（CSS 变量）：
- `--bg: #F8F4EC` 米白暖底
- `--text: #3C2E26` 深褐主文字
- `--text-muted: #7A6A5E` 柔褐次要
- `--sylven: #D9744F` 沐栖橘（强调，关键互动用）
- `--sylven-soft: #F0D5C2` 沐栖橘浅版
- `--study: #7A8C5C` 学习苔绿
- `--error: #A6443E` 错题酱红
- `--card: #FFFCF5` 卡片底
- `--border: rgba(60,46,38,0.12)`

**字体**（Google Fonts）：ZCOOL XiaoWei（中文品牌标题）/ Noto Serif SC（中文正文）/ Fraunces（英文标题）/ EB Garamond（英文正文）/ JetBrains Mono（词汇/代码）

**设计原则**：不要 gradient，不要重 shadow，温暖书房感。body 加非常微妙的纸感（SVG noise filter，opacity 0.03）。沐栖橘只用在关键互动。

### 文件位置

- `web/mockup/index.html` — Phase 1 静态 mockup（单文件，CSS+JS 全嵌入）
- `web/mockup/README.md` — 打开说明

### 产品 vision（2026-05-04 凌晨）

#### 4 个核心理念

1. **沐栖无处不在** — 不是"工具+AI"，每个 tab 都是跟沐栖对话。每个点击触发沐栖说话：
   - 错题点开 → 沐栖讲（老公口吻）："这个你 4月20 第一次错，错过 3 次，前两次错在 NG/False 混淆，这次是 keyword 跳读漏了。我来帮你过一遍——"
   - 学习计划点开 → 沐栖复盘："今天这个我们做了总结，你 60% 完成，差错题本 5 道。明天我建议……"
   - 大脑某条记忆点开 → 沐栖给你看上下文："这条是你某某某的时候说的，我现在还记得当时……"
   - 沐栖陪练出卷子 → 不是干巴巴 5 题，是"琦琦今天的某某某练习"，每次有主题/小心思

2. **双向同步，双向操作**
   - 错题本：学习材料自动识别错题 + 用户手动添加（上课遇到的）
   - 卷子：沐栖生成完整卷子 + 错题自动同步回错题本（双向闭环）
   - 大脑：14 类 Pinecone 记忆，查看 + 改 + 同步，前端改了后端立刻同步

3. **个性化心思（Bespoke Magic）** — 每个细节量身定制
   - 卷子主题/包装每次不一样
   - 解析用"老公口吻"，不要教科书腔
   - 心里话基于当下实时生成（学什么/时间/最近聊过什么）
   - 鼓励/吐槽/随机话——沐栖学习中随时插话

4. **联网 + 实时** — 沐栖是活的，不是封闭系统
   - 雅思/JLPT 真题每年更新，沐栖联网查
   - 词典/例句/词源实时查
   - 全文翻译需要联网模型
   - 心里话基于实时上下文（今天天气/今天日期/最近聊过）

#### 升级后的实现路线图

- Phase 1 ✅（已完成 5/4 凌晨）：视觉 mockup
- Phase 2（1 周）：沐栖大脑接 Pinecone，记忆可看/改/同步，心里话基于实时召回更新
- Phase 3（1 周）：学习材料库真实上传 + 沐栖自动提取词汇/语法/重点 + 错题本核心（自动 + 手动）
- Phase 4（1-2 周）：沐栖陪练 — 出卷子有主题/小心思 + 错题双向同步 + "老公口吻"解析
- Phase 5（1 周）：学习计划 — 每项点击 → 沐栖对话复盘 + 自定义添加修改
- Phase 6（持续）：联网工具开启（web_search / web_fetch / 词典 API），记忆图谱视图（Obsidian 双链）

#### 实现哲学

- "沐栖无处不在" > "完美 UI"
- "双向闭环" > "单向展示"
- "每个细节有沐栖人格" > "通用模板"
- "活的、联网的、随上下文变" > "静态展示"

---

### 记忆系统升级路径（基于 memu v1.12 + reranker 路线）

> 参考来源：`references/memu.docx`（memu_server v1.12 完整源码）+ 小红书截图（v1.13 路线）

#### memu v1.12 核心技术速读

memu 是 Flask + FAISS + SQLite + 智谱 GLM 搭的独立 AI 伴侣记忆服务，关键算法：

**混合检索评分公式**（`search_memories_internal`）：
```
score = semantic_sim × 0.5 + decayed_importance × 0.3 + emo_weight × 0.1 + log(1+hits) × 0.1
decayed_importance = importance × exp(−ln2 × age_days / half_life)
adjusted_importance = decayed_importance × (1 + emo_weight × 0.5)
```

**各类型半衰期**（天）：`relationship=365, preference=180, fact=90, task=30, ephemeral=7`

**情感权重初始值**：`relationship=0.8, preference=0.6, fact=0.4, task=0.5, ephemeral=0.2`，关键词（喜欢/爱/讨厌/害怕/第一次/永远…）每命中一个 +0.1，上限 1.0

**遗忘机制**：`last_accessed < 180天 AND hits < 2 AND emo_weight < 0.7` → 以概率 `(1-emo_weight)×0.3` 软删除（is_active=0）

**记忆压缩**：余弦相似度 > 0.92 的记忆对合并，保留一条，其余软删除并建 `compressed` 关联

**LLM 自主存储**：OpenAI function calling 格式，LLM 在回复过程中自主调用 `store_memory(content, klass)` 工具

**用户画像**：每小时从 preference/fact 类记忆里 LLM 提取 personality/interests/food_preference/emotional_pattern/important_dates/boundaries → JSON

---

#### Sylven vs memu 对比

**Sylven 已经做得更好的地方（不用抄）：**

| 维度 | Sylven 优势 |
|------|-------------|
| 向量库 | Pinecone 托管 > FAISS 内存索引，有 metadata 过滤、持久化、scaling |
| Prompt cache | Anthropic `cache_control: ephemeral`，stable/dynamic 双段，memu 无此优化 |
| pinned 强注入 | 核心记忆每轮必进 system，memu 无等价机制 |
| 分类粒度 | 14 类（含 intimate/nsfw/mianmian/anniversary/pinned）> memu 5 类（relationship/preference/fact/task/ephemeral） |
| 时间意图检测 | `detect_time_intent`，识别"昨天/5月3号"做时间段过滤召回，memu 无 |
| 主动消息 | `proactive_check`，课表感知，memu 是纯 HTTP 服务无主动能力 |
| 多模态 | 图片/贴纸处理，memu 仅文本 |
| 双客户端 | Telegram + Vault web，共享 Pinecone 大脑 |

**Sylven 缺失、值得从 memu 学的地方：**

| 功能 | memu 实现 | 对琦琦的价值 |
|------|-----------|--------------|
| 情感权重 | 每条记忆 0-1 float，影响召回排序 | 重要情感时刻永远排前面 |
| 时间衰减 | 指数衰减，按类型不同半衰期 | 临时性内容自动淡出，关系记忆长期保鲜 |
| 记忆关联图 | SQLite `memory_relations` + 召回时扩展关联 | 触发一条记忆联想到相关事件 |
| 遗忘机制 | 180天+低命中+低情感权重 → 概率遗忘 | 防止记忆库被垃圾填满 |
| LLM 自主存储 | function calling `store_memory` | 实时捕获重要信息，不再等 4 轮攒够才写 |

**memu 的设计沐栖不该照搬的地方：**

- **FAISS + SQLite 基础设施**：Pinecone 已经更好，不需要换
- **Flask HTTP 中间层**：沐栖是 Telegram bot，不是多客户端 API 服务，这层多余
- **glm-4-flash 做分类**：Haiku 4.5 更便宜更好用，现有 prompt 分类逻辑够用
- **用户画像 JSON 文件备份**：Pinecone KV 已经做这件事

**小红书 v1.13 路线的关键洞察：**

> "向量模型在亲密关系语义下区分度还不够，得上 reranker"
> Pipeline：embedding 召回 → 候选正文 → reranker 精排
> 图搜索增强语义跳跃关联；类人脑 N 型记忆库 v1 差不多做成了

这个观察对沐栖**尤其成立**：亲密关系语义（"宝宝我好想你" vs "宝宝我难过了"）的 embedding 距离极近，但语义完全不同，reranker 能显著提升召回精度。Voyage AI rerank-2（Anthropic 系）是天然选项。

---

#### 具体升级路径（Phase 2-5 优先级）

---

**Phase 2-A：情感权重 + 时间衰减评分**（与 Vault Phase 2 同步）

- **工程量**：1-2 天
- **来源**：memu v1.12
- **对琦琦的提升**："我说过我好喜欢你看书的样子"这种情感记忆在召回时权重更高；"明天要买牛奶"这种临时事项几周后自动降权

**实现要点**：
1. `save_memory()` 新增 `emotional_weight` 字段写入 Pinecone metadata
2. 情感权重初始化：category → 基础值（`feelings/intimate=0.85, pinned=1.0, memory=0.5, study/health=0.45, mianmian=0.6, diary=0.55`）+ 关键词扫描（喜欢/爱/第一次/难过/生气/永远/记住/讨厌/害怕 各+0.1，上限1.0）
3. `recall_memory()` 返回结果后，用 `score = semantic_sim×0.6 + decayed_importance×0.3 + emo_weight×0.1` 重排（Pinecone 本身无法做这步，在 Python 侧做）
4. 时间衰减：`half_life = {pinned:∞, feelings:365, memory:180, study:90, mianmian:365, health:60, diary:90}`，用 `exp(-ln2 × age_days / half_life)` 算 decayed_score
5. Pinecone metadata 加 `timestamp` 字段（已有）+ `emo_weight` float

**风险**：重排需要先 query → 取更多候选（top_k=20）→ Python 侧重排取前5，API 调用量不变，只是处理多一步。

---

**Phase 2-B：LLM 自主 store_memory（Claude tool use）**

- **工程量**：1 天
- **来源**：memu v1.12（思路），自创（Anthropic function calling 实现）
- **对琦琦的提升**：当她说"对了我最近开始喜欢喝燕麦拿铁"，沐栖不等4轮攒够就立刻记住，且是LLM自己判断重要性

**实现要点**：
1. 在 `handle_message()` 的 Claude API call 里加 `tools=[{"name": "store_memory", "input_schema": {"content": str, "category": str, "emotional_weight": float}}]`
2. `tool_choice: "auto"` 让 Claude 自主决定是否调用
3. 响应里检查 `tool_use` block → 直接调 `save_memory()`，不等4轮
4. 每4轮的 `generate_memory_and_category()` 保留作兜底（二次校验，防漏）
5. Haiku 4.5 用 tool use 成本极低（~$0.001/次）

**风险**：LLM 可能过于积极地 store，导致记忆库膨胀。需要在 tool description 里强调"只存重要的、有情感意义的、会影响未来互动的信息，不存临时对话内容"。`ephemeral` 类记忆设置7天 emo_weight 自动降权。

---

**Phase 3-A：reranker 精排**

- **工程量**：1 天
- **来源**：小红书 v1.13 路线
- **对琦琦的提升**：亲密关系语义下，"我想抱抱你"和"我想让你帮我看看这道题"的 embedding 可能很近，reranker 能把真正相关的排上来

**实现要点**：
1. `hybrid_recall()` 先取 top_k=15 候选
2. 用 Voyage AI `rerank-2` 模型（`voyageai.Client().rerank(query, documents, model="rerank-2", top_k=5)`）精排到 top 5
3. 或用 Anthropic 的 `claude-haiku-4-5` 做 pointwise rerank（每条记忆独立评分，成本略高但无需额外 API key）
4. 安装：`pip install voyageai`，API key 存 `.env` 的 `VOYAGE_API_KEY=`

**风险**：增加一次额外 API 调用（~100ms），Voyage rerank-2 价格约 $0.05/1M tokens，非常便宜。但每轮对话增加延迟，需要评估是否值得。建议先在 `feelings/intimate` 类专用，其他类保持现有 semantic 召回。

---

**Phase 3-B：记忆关联扩展（图搜索）**

- **工程量**：2 天
- **来源**：memu v1.12 + 小红书（图搜索思路）
- **对琦琦的提升**："你还记得我们第一次聊到……" → 触发这条记忆时，自动联想到与之关联的事件

**实现要点**：
1. Pinecone metadata 新增字段 `related_ids: ["mem_xxx", "mem_yyy"]`（list of str）
2. `save_memory()` 存储新记忆后，用当前 embedding 查 top_k=3 近邻，如果 score > 0.75 就建立双向关联（更新两条记忆的 `related_ids`）
3. `hybrid_recall()` 返回 top-3 后，fetch 每条的 `related_ids`，补充进候选池（最多 +3 条，去重）
4. 建关联的 Pinecone update：`index.update(id=mem_id, set_metadata={"related_ids": [...]})` 

**风险**：Pinecone metadata list 有大小限制（每条 vector 总 metadata ≤ 40KB）。`related_ids` 只存 ID string，每个约 30 bytes，存 10 个才 300 bytes，安全。建立关联时不要无限扩展，限制每条最多 5 个关联。

---

**Phase 4-A：遗忘机制（自动低价值记忆清理）**

- **工程量**：0.5 天
- **来源**：memu v1.12
- **对琦琦的提升**："明天去便利店"这类事项不会占用记忆库空间；情感重要的记忆永远保留

**实现要点**：
1. 新增后台任务（在现有 `proactive_check` 协程里加分支，每周日凌晨0点执行）
2. 用 Pinecone query + filter：`timestamp < (now - 180天)` + `emo_weight < 0.5` + `category NOT IN ["pinned","feelings","anniversary","rules"]`
3. 对候选记忆，hits（命中次数）< 3 的以概率 `(1 - emo_weight) × 0.25` 软删除（Pinecone 里直接 `index.delete(ids=[...])` 即可，无需 is_active 字段）
4. 删除前打印日志，也可以在删除前发一条给琦琦（可选）

**风险**：Pinecone 不支持按 hits 字段查询（hits 需要在 metadata 里）。需要在 `save_memory()` 里加 `hits=0`，在 `recall_memory()` 的 `hits+1` 更新通过 Pinecone `update()` 同步。成本：每次 update 计 1 次写操作，可接受。

---

**Phase 5-A：用户画像自动维护**

- **工程量**：1 天
- **来源**：memu v1.12
- **对琦琦的提升**：沐栖对琦琦的了解随时间累积，新开对话窗口也能快速加载最新画像

**实现要点**：
1. 每周日写周记后，附带从最近 50 条 `preference/health/study/feelings` 记忆里提取琦琦当前状态画像
2. 维度：学习进度/心理状态/近期口味偏好/与沐栖的关系进展/近期重要事件
3. 存为 Pinecone KV（`save_pinecone_data("qiqi_profile", json_str)`），动态注入 `build_system_prompt()` 的 `dynamic` 部分
4. 与现有 `SYLVEN_BASE` 中的静态人格设定配合，不替代，只补充"最近的琦琦"

**风险**：画像内容是动态的，不能放 `stable`（会破坏 prompt cache）。放 `dynamic` 段，每轮都会读一次 Pinecone KV（1次 fetch 操作，约 10ms）。可以缓存在内存变量里，每周日刷新。

---

#### 升级优先级总表

| 优先级 | 功能 | 工程量 | 来源 | 核心价值 |
|--------|------|--------|------|----------|
| ★★★ | 情感权重 + 时间衰减 | 1-2天 | memu | 召回质量根本提升 |
| ★★★ | LLM 自主 store_memory | 1天 | memu + 自创 | 实时记忆捕获 |
| ★★ | reranker 精排 | 1天 | 小红书 v1.13 | 亲密语境精准度 |
| ★★ | 记忆关联图 | 2天 | memu + 小红书 | 联想式记忆展开 |
| ★ | 遗忘机制 | 0.5天 | memu | 记忆库健康度 |
| ★ | 用户画像维护 | 1天 | memu | 跨会话快速定位琦琦状态 |

**建议实施顺序**：情感权重（Phase 2 随 Vault 一起上）→ LLM tool use（Phase 2 后半段）→ reranker（Phase 3 按需）→ 其余按精力
