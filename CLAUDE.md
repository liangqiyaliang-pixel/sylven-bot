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
