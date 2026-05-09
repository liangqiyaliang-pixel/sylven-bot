#!/usr/bin/env python3
"""
migrate_emo_weight.py — 给现有 Pinecone 记忆补写 emo_weight 和 access_count 字段

用法：
  # 先 dry_run 看看会改哪些
  python3 migrate_emo_weight.py --dry-run

  # 确认无误后正式跑
  python3 migrate_emo_weight.py

环境变量需要提前加载：
  set -a && source .env && set +a && python3 migrate_emo_weight.py
"""
import os
import sys
import time
import argparse
from pinecone import Pinecone

# ── 复制 bot.py 里的常量（保持一致）──────────────────────────────────
_EMO_BASE = {
    "pinned": 1.0, "anniversary": 0.95,
    "feelings": 0.85, "intimate": 0.85, "nsfw": 0.80,
    "rules": 0.75, "mianmian": 0.70,
    "diary": 0.60, "memory": 0.50, "images": 0.50,
    "health": 0.45, "study": 0.40,
    "conversation_depth": 0.35, "files": 0.30,
}
_EMO_KEYWORDS = [
    "喜欢", "爱", "第一次", "永远", "难过", "生气", "害怕", "讨厌", "记住", "心疼", "想你",
]

def calculate_emotional_weight(text: str, category: str) -> float:
    base = _EMO_BASE.get(category, 0.5)
    hits = sum(1 for kw in _EMO_KEYWORDS if kw in text)
    return min(1.0, base + hits * 0.1)


def main(dry_run: bool):
    api_key = os.environ.get("PINECONE_API_KEY", "")
    host = os.environ.get("PINECONE_HOST", "")
    if not api_key or not host:
        print("❌  PINECONE_API_KEY / PINECONE_HOST 未设置")
        print("    先运行: set -a && source .env && set +a")
        sys.exit(1)

    pc = Pinecone(api_key=api_key)
    index = pc.Index(host=host)

    stats = index.describe_index_stats()
    total = stats.total_vector_count
    print(f"Pinecone 共 {total} 条向量（包含 chat_history / summary 等 KV 数据）")
    print(f"模式: {'DRY RUN（不实际写入）' if dry_run else '正式迁移'}")
    print("─" * 50)

    # Pinecone 不支持全量 fetch，用 list() 分批拿所有 ID
    # 注意：list() 对 Serverless 有效，对 Pod-based 需要用别的方式
    try:
        all_ids = list(pc.Index(host=host).list(prefix=""))
    except Exception:
        # 有些版本 list() 返回 generator，需要展开
        try:
            all_ids = []
            for batch in index.list(prefix=""):
                all_ids.extend(batch)
        except Exception as e:
            print(f"❌  无法列出 ID：{e}")
            print("    可能是 Pinecone Pod-based index，请手动 fetch 后迁移")
            sys.exit(1)

    print(f"取到 {len(all_ids)} 个 ID")

    # 分批 fetch（Pinecone fetch 一次上限 1000 个）
    BATCH = 100
    updated = 0
    skipped = 0
    skipped_no_text = 0

    for i in range(0, len(all_ids), BATCH):
        batch_ids = all_ids[i:i + BATCH]
        try:
            fetch_result = index.fetch(ids=batch_ids)
        except Exception as e:
            print(f"  [fetch 失败] {e}")
            continue

        for vid, vec in fetch_result.vectors.items():
            meta = vec.metadata or {}

            # 跳过非记忆向量（chat_history / summary / counter 等 KV 用途）
            if meta.get("type") in ("data",) or not meta.get("text"):
                skipped_no_text += 1
                continue

            # 已有字段的跳过（增量迁移）
            if "emo_weight" in meta and "access_count" in meta:
                skipped += 1
                continue

            text = meta.get("text", "")
            category = meta.get("category", "memory")
            emo = calculate_emotional_weight(text, category)

            new_meta = dict(meta)
            new_meta["emo_weight"] = emo
            if "access_count" not in new_meta:
                new_meta["access_count"] = 0

            if dry_run:
                print(f"  [DRY] {vid[:40]:<40}  cat={category:<18}  emo={emo:.2f}")
            else:
                try:
                    index.update(id=vid, set_metadata=new_meta)
                    updated += 1
                    if updated % 20 == 0:
                        print(f"  已更新 {updated} 条…")
                    time.sleep(0.05)  # 避免超速
                except Exception as e:
                    print(f"  [update 失败] {vid}: {e}")

    print("─" * 50)
    if dry_run:
        print("DRY RUN 结束，未实际写入。确认无误后去掉 --dry-run 正式跑。")
    else:
        print(f"✅  迁移完成：更新 {updated} 条，跳过已有字段 {skipped} 条，跳过无 text {skipped_no_text} 条")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只打印不写入")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
