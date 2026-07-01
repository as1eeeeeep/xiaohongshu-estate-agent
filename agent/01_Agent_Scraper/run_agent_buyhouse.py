"""一次性运行脚本：抓取近1个月内、中介视角的香港买房爆款笔记。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hunter

hunter.PUBLISHED_WITHIN_DAYS = 30

AGENT_KEYWORDS = [
    "香港放盘推荐",
    "香港笋盘",
    "香港楼盘推荐",
    "香港置业顾问",
    "香港地产代理",
    "香港房源推介",
    "香港细价楼推介",
    "港岛楼盘放售",
    "九龙楼盘推介",
    "香港二手房源",
]

if __name__ == "__main__":
    notes = hunter.discover_notes(keywords=AGENT_KEYWORDS, target_count=80, pages_per_keyword=5)
    print(f"
>>> 发现 {len(notes)} 条候选笔记（30天内），开始中介视角过滤与处理...
")
    results = hunter.run(target_notes=notes, perspective="中介")

    qualified = [r for r in results if r.get("triggered")]
    print("
" + "=" * 55)
    print(f"合格笔记数: {len(qualified)}")
    for r in qualified:
        print(r.get("note_url"))
