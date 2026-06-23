"""一次性运行脚本：抓取素人视角、买房相关、带房源实景图的看房/买房笔记，不限发布时间。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hunter

# 不限发布时间
hunter.PUBLISHED_WITHIN_DAYS = 0

# 聚焦"买房+晒房源实景"主题，避免命中租房/留学吐槽/市场讨论类笔记
BUY_HOUSE_KEYWORDS = [
    "香港买房晒图",
    "香港新家分享",
    "香港业主自述",
    "香港买房入伙",
    "香港买房实拍",
    "香港置业分享",
    "香港我的新房子",
    "香港买楼装修",
    "香港买房看房vlog",
    "香港楼盘实地考察",
]

if __name__ == "__main__":
    notes = hunter.discover_notes(keywords=BUY_HOUSE_KEYWORDS, target_count=100, pages_per_keyword=5)
    print(f"\n>>> 发现 {len(notes)} 条候选笔记（不限时间），开始素人视角过滤与处理...\n")
    results = hunter.run(target_notes=notes, perspective="素人")

    qualified = [r for r in results if r.get("triggered")]
    print("\n" + "=" * 55)
    print(f"合格笔记数: {len(qualified)}")
    for r in qualified:
        print(r.get("note_url"))
