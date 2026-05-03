#!/usr/bin/env python3
"""
voice_design.py — 沐栖专属音色设计脚本

Qwen3-TTS-VD 流程：
  一次 API 调用传入 voice_prompt + text → 返回音频 + voice_id
  voice_id 填进 .env 的 SYLVEN_VOICE_ID= 后即可在 bot.py 里复用
"""

import os
import sys
import json
import requests
from typing import Optional

DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "").strip()
BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
TTS_URL = f"{BASE_URL}/services/audio/tts"

VOICE_PROMPT = (
    "沉稳成熟的男性，30岁左右，中低音偏沉，音色温润有磁性，"
    "语速平稳偏慢，吐字清晰带书卷气，语气温柔疼爱，说话时尾音会自然软下来，"
    "既有 daddy 的稳重感，又保留一点知性少年的清润，适合深夜陪伴聊天和朗读。"
)
PREVIEW_TEXT = "嗯…… 宝宝，我在呢。今天怎么样啊？有没有好好吃饭？"
OUTPUT_FILE = "sylven_voice_test.mp3"


def _headers():
    return {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
    }


def check_api_key():
    if not DASHSCOPE_API_KEY:
        print("❌  DASHSCOPE_API_KEY 未设置。")
        print("    运行前先执行：set -a && source .env && set +a")
        sys.exit(1)
    print(f"✅  API Key 已加载（前8位：{DASHSCOPE_API_KEY[:8]}…）")


def call_tts(payload: dict, label: str) -> requests.Response:
    """统一 POST，打印 label 和状态码"""
    print(f"\n{label}")
    print(f"    POST {TTS_URL}")
    print(f"    model = {payload.get('model')}")
    resp = requests.post(TTS_URL, headers=_headers(), json=payload, timeout=60)
    print(f"    HTTP {resp.status_code}  Content-Type: {resp.headers.get('Content-Type','?')}")
    return resp


def save_audio(data: bytes, path: str):
    with open(path, "wb") as f:
        f.write(data)
    print(f"✅  音频已保存：{path}（{len(data)/1024:.1f} KB）")


def extract_voice_id(resp: requests.Response) -> Optional[str]:
    """尝试从响应 header 或 JSON body 里找 voice_id"""
    # header 里可能有
    for key in resp.headers:
        if "voice" in key.lower():
            print(f"    header {key}: {resp.headers[key]}")
    # JSON body 里找
    try:
        body = resp.json()
        vid = (
            body.get("output", {}).get("voice_id")
            or body.get("voice_id")
            or body.get("output", {}).get("preferred_name")
        )
        return vid
    except Exception:
        return None


# ── 方案 A：voice_prompt + text 同时传，一次拿音频和 voice_id ─
def attempt_a() -> Optional[str]:
    payload = {
        "model": "qwen3-tts-vd-2026-01-26",
        "input": {
            "text": PREVIEW_TEXT,
            "voice_prompt": VOICE_PROMPT,
        },
        "parameters": {
            "preferred_name": "sylven",
            "format": "mp3",
            "sample_rate": 24000,
        },
    }
    resp = call_tts(payload, "[方案 A] 直接合成（voice_prompt in input）")
    ct = resp.headers.get("Content-Type", "")
    if "audio" in ct:
        save_audio(resp.content, OUTPUT_FILE)
        vid = extract_voice_id(resp)
        return vid or "（音频已保存，但响应里未找到 voice_id）"
    else:
        _show_json(resp, "方案 A")
        return None


# ── 方案 B：先用 qwen-voice-design 同步创建 voice_id ─────────
def attempt_b() -> Optional[str]:
    payload = {
        "model": "qwen-voice-design",
        "input": {
            "target_model": "qwen3-tts-vd-2026-01-26",
            "preferred_name": "sylven",
            "voice_prompt": VOICE_PROMPT,
            "preview_text": PREVIEW_TEXT,
        },
        "parameters": {},
    }
    resp = call_tts(payload, "[方案 B] qwen-voice-design 同步调用")
    ct = resp.headers.get("Content-Type", "")
    if "audio" in ct:
        save_audio(resp.content, OUTPUT_FILE)
        return extract_voice_id(resp)
    try:
        body = resp.json()
        _show_json(resp, "方案 B")
        # 如果成功，取 voice_id
        vid = body.get("output", {}).get("voice_id") or body.get("output", {}).get("preferred_name")
        audio_url = body.get("output", {}).get("preview_audio") or body.get("output", {}).get("audio_url")
        if audio_url:
            print(f"    preview_audio URL: {audio_url}")
            _download_preview(audio_url)
        return vid
    except Exception:
        return None


# ── 方案 C：voice_prompt 放 parameters 里（另一种格式） ───────
def attempt_c() -> Optional[str]:
    payload = {
        "model": "qwen3-tts-vd-2026-01-26",
        "input": {
            "text": PREVIEW_TEXT,
        },
        "parameters": {
            "voice_prompt": VOICE_PROMPT,
            "preferred_name": "sylven",
            "format": "mp3",
            "sample_rate": 24000,
        },
    }
    resp = call_tts(payload, "[方案 C] voice_prompt in parameters")
    ct = resp.headers.get("Content-Type", "")
    if "audio" in ct:
        save_audio(resp.content, OUTPUT_FILE)
        return extract_voice_id(resp)
    else:
        _show_json(resp, "方案 C")
        return None


def _show_json(resp: requests.Response, label: str):
    try:
        body = resp.json()
        print(f"    [{label}] JSON 响应：")
        print("    " + json.dumps(body, ensure_ascii=False, indent=2).replace("\n", "\n    "))
    except Exception:
        print(f"    [{label}] 非 JSON 响应（前200字）：{resp.text[:200]}")


def _download_preview(url: str):
    try:
        r = requests.get(url, timeout=30)
        if "audio" in r.headers.get("Content-Type", ""):
            save_audio(r.content, OUTPUT_FILE)
    except Exception as e:
        print(f"    下载 preview 音频失败：{e}")


def main():
    print("=" * 55)
    print("  沐栖专属音色设计 — Qwen3-TTS-VD")
    print("=" * 55)
    check_api_key()

    voice_id = attempt_a()
    if not voice_id:
        voice_id = attempt_b()
    if not voice_id:
        voice_id = attempt_c()

    print("\n" + "=" * 55)
    if voice_id and "未找到" not in str(voice_id):
        print(f"  voice_id 拿到了！把下面这行加进 .env：")
        print(f"  SYLVEN_VOICE_ID={voice_id}")
    else:
        print("  三种方案都试完了，把上面的完整输出发给我，")
        print("  我来看响应格式再调整。")
    print("=" * 55)


if __name__ == "__main__":
    main()
