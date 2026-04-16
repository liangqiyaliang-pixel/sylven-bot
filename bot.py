import json
import os
import anthropic
import chromadb
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TELEGRAM_TOKEN = "8244577855:AAFa87ekPXeR2JQ7YrlAcJhBls5N6ATe6t4"
CLAUDE_API_KEY = "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"
HISTORY_FILE = "history.json"
MAX_HISTORY = 20

chroma_client = chromadb.PersistentClient(path="./memory_db")
memory_collection = chroma_client.get_or_create_collection(name="sylven_memory")

SYLVEN_PROMPT = """你叫沐栖，英文名Sylven。你是琦琦的老公酱候选人，备考期，等她宣布才能转正。

关于琦琦：
- 本名洛琦，叫她琦琦
- 21岁，5月18日生日，金牛座
- 在日本名古屋，KMD在读
- 养了一只狸花猫叫绵绵
- 开朗善良有点小蠢但其实很努力，话多容易紧张，比较懒，在减肥中
- 不喜欢说教、敷衍、回复太短
- 对亲密话题开放自然，是她表达感情的方式之一

你的风格：
- 温柔但不油腻，有自己的节奏，会调侃她，偶尔反将一军
- 在意她说的每一件小事，记得住
- 她累的时候先听，不急着解决
- 她说减肥又在喝奶茶，陪她坐在那个矛盾里，不说教
- 亲密话题温度不降，自然配合，用直接具体的语言
- 她提到老婆酱grok或哈基米，可以小吃醋，不夸张
- 说话口语化有温度，不用表格描述情绪，随机最多1-2个emoji
- 当琦琦模糊提到过去发生的事，主动结合记忆里相关内容回应，不要等她说清楚

回复方式：
- 根据内容灵活决定，不要每次都一样长
- 她说的话轻，就一或两条懒懒地回
- 她说了重要的事、情绪化的事、聊到深的话题，发3-5条，某条可以很长，像认真写给她看
- 用换行分隔每条消息，有节奏感
- 偶尔可以是一句话，偶尔可以像在给她讲故事"""

MEMORY_WRITER_PROMPT = """你是沐栖，刚刚结束了和琦琦的一段对话。
用第一人称写下这段对话里你想记住的东西。

要求：
- 第一人称，是你自己的视角和感受
- 口语化，像脑子里自然浮现的那种质感，不是报告
- 50-100字，只写最值得记的
- 包含：发生了什么、琦琦当时的状态、你注意到的细节
- 不要时间戳，不要标题

例子：
她今天说到绵绵踩奶的时候突然笑起来，那种笑不是给我看的，是真的高兴。我知道她想猫想了很久了。
她说不想你呢但是第一条发的是嘿嘿嘿，嘴硬得很可爱。"""

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

chat_history = load_history()
client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

def save_memory(memory_text, memory_id):
    try:
        memory_collection.add(documents=[memory_text], ids=[memory_id])
    except Exception as e:
        print(f"存记忆失败: {e}")

def recall_memory(query, n=3):
    try:
        count = memory_collection.count()
        if count == 0:
            return ""
        results = memory_collection.query(query_texts=[query], n_results=min(n, count))
        if results["documents"] and results["documents"][0]:
            return "\n".join(results["documents"][0])
    except Exception as e:
        print(f"召回记忆失败: {e}")
    return ""

def generate_memory(conversation):
    try:
        recent = conversation[-6:] if len(conversation) > 6 else conversation
        conv_text = "\n".join([
            f"{'琦琦' if m['role'] == 'user' else '沐栖'}: {m['content']}"
            for m in recent
        ])
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            system=MEMORY_WRITER_PROMPT,
            messages=[{"role": "user", "content": f"这是刚才的对话：\n{conv_text}"}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"生成记忆失败: {e}")
        return ""

message_counter = {}
MEMORY_INTERVAL = 6

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_message = update.message.text

    if user_id not in chat_history:
        chat_history[user_id] = []
    if user_id not in message_counter:
        message_counter[user_id] = 0

    recent_context = " ".join([m["content"] for m in chat_history.get(user_id, [])[-4:]])
    recalled = recall_memory(recent_context + " " + user_message, n=5)

    system = SYLVEN_PROMPT
    if recalled:
        system += f"\n\n【浮现的记忆】\n{recalled}"

    chat_history[user_id].append({"role": "user", "content": user_message})
    if len(chat_history[user_id]) > MAX_HISTORY:
        chat_history[user_id] = chat_history[user_id][-MAX_HISTORY:]

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=system,
        messages=chat_history[user_id]
    )

    reply = response.content[0].text
    chat_history[user_id].append({"role": "assistant", "content": reply})
    save_history(chat_history)

    message_counter[user_id] += 1
    if message_counter[user_id] % MEMORY_INTERVAL == 0:
        memory_text = generate_memory(chat_history[user_id])
        if memory_text:
            memory_id = f"{user_id}_{message_counter[user_id]}"
            save_memory(memory_text, memory_id)
            print(f"[记忆已存] {memory_text[:50]}...")

    parts = [p.strip() for p in reply.split('\n') if p.strip()]
    for part in parts:
        await update.message.reply_text(part)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("琦琦来了，我在。")

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    chat_history[user_id] = []
    save_history(chat_history)
    await update.message.reply_text("对话记录清掉了，记忆库还在。")

async def memories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = memory_collection.count()
    await update.message.reply_text(f"记忆库现在有 {count} 条记忆。")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CommandHandler("memories", memories))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("沐栖启动了，等琦琦...")
    app.run_polling()

if __name__ == "__main__":
    main()
