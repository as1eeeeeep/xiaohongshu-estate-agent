# -*- coding: utf-8 -*-
"""压缩超过500字的笔记文案"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "D:/xiaohongshu_estate/agent")

from pathlib import Path
from openai import OpenAI
from shared.config import API_KEY, BASE_URL, HEAVY_MODEL

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
BASE = Path(r"D:\xiaohongshu_estate\06_output(multiangle)\20260615_1904_v2\assembled")

targets = ["C04", "P03", "P09", "P01", "P10"]

for prefix in targets:
    for folder in sorted(BASE.iterdir()):
        if not folder.is_dir() or not folder.name.startswith(prefix):
            continue
        note = folder / "note.txt"
        if not note.exists():
            continue
        text = note.read_text(encoding="utf-8")
        chars = len(text)
        if chars <= 490:
            print(f"{prefix}: {chars}字 OK")
            continue

        print(f"{prefix}: {chars}字 → 压缩中...")
        resp = client.chat.completions.create(
            model=HEAVY_MODEL,
            messages=[{
                "role": "user",
                "content": (
                    f"以下是小红书笔记文案，当前{chars}字，请压缩到500字以内。\n"
                    "只删冗余、合并重复表达，不改结构、不删关键信息、不改变风格。\n"
                    "保持：小姐姐 @阿琪的香港看房日记 规则、口语化素人语气。\n\n"
                    f"{text}"
                ),
            }],
            temperature=0.3,
            max_tokens=4096,
            timeout=60,
        )
        new_text = resp.choices[0].message.content.strip()
        # 清理代码块
        for mark in ("```txt", "```"):
            if new_text.startswith(mark):
                new_text = new_text[len(mark):].strip()
        if new_text.endswith("```"):
            new_text = new_text[:-3].strip()

        new_chars = len(new_text)
        if 50 < new_chars <= 520:
            note.write_text(new_text, encoding="utf-8")
            print(f"  ✓ → {new_chars}字")
        else:
            # 手动截断
            print(f"  LLM返回{new_chars}字异常，手动截断...")
            # 找标签行
            idx = text.rfind("\n标签")
            if idx > 0:
                body = text[:idx]
                tags = text[idx:]
                # 每段删一些
                lines = body.split("\n")
                trimmed = []
                for line in lines:
                    if len(line) > 60:
                        line = line[:55] + "…"
                    trimmed.append(line)
                new_text = "\n".join(trimmed) + tags
                new_chars = len(new_text)
                if new_chars <= 510:
                    note.write_text(new_text, encoding="utf-8")
                    print(f"  ✓ 手动截断 → {new_chars}字")
                else:
                    # 更激进截断
                    new_text = text[:480] + text[text.rfind("\n标签"):]
                    note.write_text(new_text, encoding="utf-8")
                    print(f"  ✓ 硬截断 → {len(new_text)}字")
        break

print("\n最终字数：")
for folder in sorted(BASE.iterdir()):
    if not folder.is_dir():
        continue
    note = folder / "note.txt"
    if note.exists():
        chars = len(note.read_text(encoding="utf-8"))
        flag = " ⚠" if chars > 500 else ""
        print(f"  {chars:4d}字 | {folder.name[:35]}{flag}")
