# -*- coding: utf-8 -*-
"""批量修文案：中介→小姐姐，去夸张词，加@阿琪"""
import re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

BASE = Path(r"D:\xiaohongshu_estate\06_output(multiangle)\20260615_1904_v2\assembled")

for folder in sorted(BASE.iterdir()):
    if not folder.is_dir():
        continue
    note = folder / "note.txt"
    if not note.exists():
        continue
    text = note.read_text(encoding="utf-8")
    original = text

    # ── 1. 中介/小哥/经纪 → 小姐姐 ──
    text = re.sub(r'中介小哥', '小姐姐', text)
    text = re.sub(r'带看的小哥', '带看的小姐姐', text)
    text = re.sub(r'带看小哥', '带看的小姐姐', text)
    text = re.sub(r'带了(个)?小哥', r'带了\1小姐姐', text)
    text = re.sub(r'(?<![小])小哥', '小姐姐', text)
    text = re.sub(r'中介', '小姐姐', text)
    text = re.sub(r'经纪', '小姐姐', text)

    # ── 2. 去夸张：拉了个表 / 当场用手机拉了个表 ──
    text = re.sub(r'他当场(用手机)?(给我)?拉了个表[，,]\s*算了下?[，,]?\s*', '她帮我大致算了下，', text)
    text = re.sub(r'当场(用手机)?(给我)?拉了个表[，,]\s*', '大概帮我算了下，', text)
    text = re.sub(r'拉了个表[，,]\s*算', '帮我算了', text)
    text = re.sub(r'拉了个表[，,]?\s*', '', text)
    text = re.sub(r'按他算的', '按她算的', text)

    # ── 3. 去夸张：掏出激光测距仪 / 测距仪 / 激光尺 ──
    text = re.sub(r'掏出(了)?(个)?激光测距仪[，,]?\s*', '', text)
    text = re.sub(r'掏出(了)?随身带的测距仪[，,]?\s*', '', text)
    text = re.sub(r'当场掏出(了)?(随身带的)?(激光)?测距仪[，,]?\s*', '', text)
    text = re.sub(r'拿激光尺[，,]?\s*', '', text)
    # 独立短句 "掏出个激光测距仪现场量了下尺寸" → 改自然
    text = re.sub(r'掏出个激光测距仪现场量了下尺寸[，,]?\s*', '', text)
    text = re.sub(r'掏出随身带的测距仪[，,]?\s*现场量了下[，,]\s*', '', text)
    # 去掉多余逗号
    text = re.sub(r'，\s*，', '，', text)

    # ── 4. 去夸张：测距仪相关叙述改写 ──
    text = re.sub(r'用具体数据一看确实挺局促的', '确实挺局促的', text)
    text = re.sub(r'中介当场掏出激光测距仪帮我量了下次卧[，,]?\s*', '', text)
    text = re.sub(r'直接提醒我', '提醒我', text)
    # "当场量了一下" / "现场量了下" 保留但去工具描述
    text = re.sub(r'掏出(了)?(个)?激光测距仪，?直接在纸上画了个草图[，,]?\s*', '', text)
    text = re.sub(r'告诉我怎么改两房走线最省钱[，,]?\s*这波操作确实有点超出预期。', '还比划了下怎么改两房走线最省钱，挺意外的。', text)
    # 去掉多余标点
    text = re.sub(r'，\s*，', '，', text)

    # ── 5. 去掉 "靠谱中介" 标签 ──
    text = re.sub(r'#靠谱中介\s*', '', text)

    # ── 6. 结尾添加 @阿琪的香港看房日记 ──
    # 在正文末尾（标签前）加一行
    if '@阿琪的香港看房日记' not in text:
        text = re.sub(r'(\n标签[：:])', r'\n@阿琪的香港看房日记\n\1', text)
        if '@阿琪的香港看房日记' not in text:
            text = re.sub(r'(\n#)', r'\n@阿琪的香港看房日记\n\1', text)
        if '@阿琪的香港看房日记' not in text:
            text = text.rstrip() + '\n\n@阿琪的香港看房日记\n'

    # ── 7. 修缮：把改了之后不通顺的句子修一下 ──
    # "试着" → 不自然
    # 双逗号清理
    text = re.sub(r'，\s*，', '，', text)
    text = re.sub(r'^，\s*', '', text, flags=re.MULTILINE)

    if original != text:
        note.write_text(text, encoding="utf-8")
        name = folder.name[:30]
        print(f"✓ {name}")
    else:
        print(f"  {folder.name[:30]} (无变化)")

print("\n完成！")
