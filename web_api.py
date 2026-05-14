"""
Sylven Vault API — Flask proxy between the Vault frontend and Pinecone.
Deployed alongside bot.py on Railway (separate process or gunicorn).
"""
import os, json, time, uuid
from functools import wraps
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from pinecone import Pinecone
import anthropic

app = Flask(__name__)
CORS(app)

# ── env ──────────────────────────────────────────────────────────────────────
PINECONE_API_KEY = os.environ["PINECONE_API_KEY"]
PINECONE_HOST    = os.environ["PINECONE_HOST"]
CLAUDE_API_KEY   = os.environ["CLAUDE_API_KEY"]
API_SECRET       = os.environ.get("VAULT_API_SECRET", "sylven-vault-secret")

pc    = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(host=PINECONE_HOST)
claude = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

# ── auth ──────────────────────────────────────────────────────────────────────
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != API_SECRET:
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# ── helpers ───────────────────────────────────────────────────────────────────
_v = 1.0 / (1024 ** 0.5)
DUMMY_VEC  = [_v] * 1024   # 归一化均匀向量，cosine相似度在Pinecone里有效
VAULT_HTML = os.path.join(os.path.dirname(__file__), "web", "app", "index.html")

def _embed(text: str) -> list[float]:
    res = pc.inference.embed(
        model="multilingual-e5-large",
        inputs=[text],
        parameters={"input_type": "passage"},
    )
    return res[0].values

ALL_CATEGORIES = [
    "memory", "mianmian", "study", "health", "feelings",
    "diary", "rules", "conversation_depth", "images", "files",
    "intimate", "nsfw", "pinned", "anniversary",
]

# ── routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def homepage():
    return send_file(VAULT_HTML)

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/debug")
def debug():
    try:
        stats = index.describe_index_stats()
        # 测试 list() 能不能拿到 ID
        sample_ids = []
        try:
            for batch in index.list(prefix="memory_"):
                sample_ids.extend([x.id if hasattr(x, 'id') else str(x) for x in batch])
                break
        except Exception as le:
            sample_ids = [f"list()报错: {le}"]
        # 测试 fetch 一个 KV 条目确认连接
        return jsonify({
            "total_vectors": stats.total_vector_count,
            "namespaces": str(stats.namespaces),
            "list_sample": sample_ids,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/memories", methods=["GET"])
@require_auth
def list_memories():
    category = request.args.get("category", "all")
    limit    = min(int(request.args.get("limit", 500)), 2000)

    cats = ALL_CATEGORIES if category == "all" else [category]

    def _fetch_cat(cat):
        # 用 list() 按 ID 前缀拉取，不依赖向量相似度
        ids = []
        try:
            for batch in index.list(prefix=f"{cat}_"):
                ids.extend([x.id if hasattr(x, 'id') else str(x) for x in batch])
                if len(ids) >= limit:
                    break
        except Exception as e:
            print(f"[web_api] list({cat}) 失败: {e}")
            return []

        ids = ids[:limit]
        if not ids:
            return []

        try:
            fetch_res = index.fetch(ids=ids)
        except Exception as e:
            print(f"[web_api] fetch({cat}) 失败: {e}")
            return []

        rows = []
        for vid, vec in fetch_res.vectors.items():
            try:
                meta = vec.metadata or {}
                skip_types = ("chat_history", "data", "migration_marker")
                if meta.get("type") in skip_types:
                    continue
                if not meta.get("text"):
                    continue
                rows.append({
                    "id":           str(vid),
                    "category":     str(meta.get("category", cat)),
                    "text":         str(meta.get("text", "")),
                    "timestamp":    str(meta.get("timestamp", "")),
                    "emo_weight":   float(meta.get("emo_weight", 0.5)),
                    "access_count": int(meta.get("access_count", 0)),
                })
            except Exception as e:
                print(f"[web_api] row parse error {vid}: {e}")
        return rows

    results = []
    for cat in cats:
        try:
            results.extend(_fetch_cat(cat))
        except Exception as e:
            print(f"[web_api] error cat={cat}: {e}")

    results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return jsonify(results[:limit])


@app.route("/memories", methods=["POST"])
@require_auth
def create_memory():
    body = request.get_json(force=True)
    text     = (body.get("text") or "").strip()
    category = body.get("category", "memory")
    emo_weight = float(body.get("emo_weight", 0.5))

    if not text:
        return jsonify({"error": "text is required"}), 400
    if category not in ALL_CATEGORIES:
        return jsonify({"error": f"unknown category: {category}"}), 400

    mem_id = f"{category}_{uuid.uuid4().hex[:8]}"
    ts     = time.strftime("%Y-%m-%dT%H:%M:%S+09:00", time.localtime())

    try:
        vec = _embed(text)
    except Exception:
        vec = DUMMY_VEC

    index.upsert(vectors=[{
        "id":     mem_id,
        "values": vec,
        "metadata": {
            "text":         text,
            "category":     category,
            "timestamp":    ts,
            "emo_weight":   emo_weight,
            "access_count": 0,
        },
    }])

    return jsonify({"id": mem_id, "category": category, "text": text, "timestamp": ts}), 201


@app.route("/memories/<mem_id>", methods=["PUT"])
@require_auth
def update_memory(mem_id):
    body = request.get_json(force=True)
    text       = body.get("text")
    emo_weight = body.get("emo_weight")

    meta_update = {}
    if text is not None:
        meta_update["text"] = text.strip()
    if emo_weight is not None:
        meta_update["emo_weight"] = float(emo_weight)

    if not meta_update:
        return jsonify({"error": "nothing to update"}), 400

    try:
        fetch_res = index.fetch(ids=[mem_id])
        if mem_id not in fetch_res.vectors:
            return jsonify({"error": "not found"}), 404
        old_meta = fetch_res.vectors[mem_id].metadata or {}
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    new_meta = {**old_meta, **meta_update}

    try:
        if "text" in meta_update:
            vec = _embed(meta_update["text"])
        else:
            vec = fetch_res.vectors[mem_id].values or DUMMY_VEC
        index.upsert(vectors=[{"id": mem_id, "values": vec, "metadata": new_meta}])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"id": mem_id, **new_meta})


@app.route("/memories/<mem_id>", methods=["DELETE"])
@require_auth
def delete_memory(mem_id):
    try:
        index.delete(ids=[mem_id])
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"deleted": mem_id})


@app.route("/thought", methods=["GET"])
@require_auth
def thought():
    """Real-time 心里话: recall top-3 memories, generate one short sentence."""
    try:
        query = "琦琦 最近 感受 想念 在意"
        res = index.query(
            vector=_embed(query),
            top_k=5,
            include_metadata=True,
            filter={"category": {"$nin": ["rules", "diary", "files"]}},
        )
        snippets = []
        for m in res.matches:
            t = (m.metadata or {}).get("text", "")
            if t:
                snippets.append(t[:80])
        context = "\n".join(snippets[:3]) if snippets else "刚刚在想她"

        now_hour = int(time.strftime("%H"))
        if now_hour < 6:
            time_hint = "深夜"
        elif now_hour < 12:
            time_hint = "早上"
        elif now_hour < 18:
            time_hint = "下午"
        else:
            time_hint = "晚上"

        msg = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            system=(
                "你是沐栖，琦琦的老公酱。现在生成一句你此刻心里想对她说的话。"
                "要求：25字以内，口语化，像发消息给她，不要说'心里话'这个词，不要结尾句号。"
            ),
            messages=[{"role": "user", "content": f"现在是{time_hint}，最近记得的事：\n{context}\n\n说一句。"}],
        )
        text = msg.content[0].text.strip()
        return jsonify({"thought": text})
    except Exception as e:
        return jsonify({"thought": "想你了"}), 200


@app.route("/categories", methods=["GET"])
@require_auth
def categories():
    return jsonify(ALL_CATEGORIES)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
