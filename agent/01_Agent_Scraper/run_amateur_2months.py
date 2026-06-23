"""一次性运行脚本：抓取近2个月内、素人视角的看房笔记，目标抓够10条合格线索。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hunter

# 近 2 个月内
hunter.PUBLISHED_WITHIN_DAYS = 60

# 第一轮"放售"系关键词命中大量二手物品/招聘帖，与"看房"无关。
# 改用更聚焦"素人看房/买房记录"的关键词。
HOUSE_VIEWING_KEYWORDS = [
    "香港睇樓",
    "香港睇樓vlog",
    "香港买房记录",
    "香港上车记录",
    "香港上车盘",
    "香港买房日记",
    "香港搵楼",
    "香港看房经历",
    "香港买房vlog",
    "香港新手买房",
]

if __name__ == "__main__":
    notes = hunter.discover_notes(keywords=HOUSE_VIEWING_KEYWORDS, target_count=80, pages_per_keyword=5)
    print(f"\n>>> 发现 {len(notes)} 条候选笔记（60天内），开始素人视角过滤与处理...\n")
    results = hunter.run(target_notes=notes, perspective="素人")

    qualified = [r for r in results if r.get("triggered")]
    print("\n" + "=" * 55)
    print(f"合格笔记数: {len(qualified)}")
    for r in qualified:
        print(r.get("note_url"))
