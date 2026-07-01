"""
抓取「素人视角 + 给房产中介号导流」类笔记。
聚焦：房地产买房/卖房/看房/楼市，香港 + 内地均可，排除留学/移民/求职中介。
输出目录：/Users/asleep/松鼠找房/02_scrap_output/
不限发布时间，每关键词 8 页，目标候选量 600 条。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hunter

# ── 输出重定向到 02_scrap_output ──
OUTPUT_ROOT = Path(__file__).resolve().parent.parent.parent / "02_scrap_output"
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

hunter.QUALIFIED_LEADS_PATH = OUTPUT_ROOT / "qualified_leads.json"
hunter.DOWNLOADS_DIR        = OUTPUT_ROOT / "downloads"
hunter.VIRAL_DIR            = OUTPUT_ROOT / "viral_examples"
hunter.STAGE1_DIR           = OUTPUT_ROOT / "stage1_raw"

# ── 不限时间 ──
hunter.PUBLISHED_WITHIN_DAYS = 0

# ── 关键词：专聚焦房地产，香港 + 内地 ──
TRAFFIC_KEYWORDS = [
    # ── 香港：买房日记/心得 ──
    "香港买房日记",
    "香港上车日记",
    "香港买楼日记",
    "香港买房手记",
    "香港买房经历",
    "香港置业日记",
    "香港买房入伙",
    "香港收楼",

    # ── 香港：攻略/科普 ──
    "香港买房攻略",
    "香港置业攻略",
    "香港首次置业",
    "香港买房流程",
    "香港买房注意事项",
    "香港按揭攻略",
    "香港买房避坑",
    "香港楼盘避坑",

    # ── 香港：看房/踩坑 ──
    "香港看房记录",
    "香港看房踩坑",
    "香港看楼日记",
    "香港看房笔记",
    "香港睇楼日记",

    # ── 香港：区域/楼盘测评 ──
    "香港哪个区买房",
    "香港上车盘推荐",
    "香港荃湾买房",
    "香港元朗买房",
    "香港将军澳买房",
    "香港沙田买房",
    "香港西营盘买房",
    "香港北角买房",
    "香港细价楼上车",
    "香港上车心得",

    # ── 香港：租转买 / 楼市行情 ──
    "香港租转买",
    "香港楼市行情",
    "香港楼价走势",
    "香港二手楼",

    # ── 内地：买房日记/心得 ──
    "深圳买房日记",
    "广州买房经历",
    "上海买房心得",
    "北京买房踩坑",
    "买房看房日记",
    "首套房购买经历",
    "置业分享",

    # ── 内地：攻略/科普 ──
    "买房避坑指南",
    "二手房避坑",
    "新房选购攻略",
    "首套房攻略",
    "房贷攻略",
    "买房流程分享",

    # ── 内地：看房/踩坑 ──
    "看房日记",
    "看房踩坑",
    "新房交付踩坑",
    "买房后悔了",
    "卖房经历",

    # ── 内地：楼市行情 ──
    "楼市分析2025",
    "现在适合买房吗",
    "房价走势",
]

if __name__ == "__main__":
    print(f"输出目录: {OUTPUT_ROOT}")
    print(f"关键词数: {len(TRAFFIC_KEYWORDS)}")
    print("开始发现笔记（目标候选量 600，每关键词 8 页，不限时间）...\n")

    notes = hunter.discover_notes(
        keywords=TRAFFIC_KEYWORDS,
        pages_per_keyword=8,
        target_count=600,
        published_within_days=0,
    )
    print(f"\n>>> 发现 {len(notes)} 条候选笔记，开始素人视角过滤与询盘筛选...\n")

    results = hunter.run(target_notes=notes, perspective="素人")

    qualified = [r for r in results if r.get("triggered")]
    print("\n" + "=" * 55)
    print(f"合格笔记数: {len(qualified)}")
    print(f"输出目录: {OUTPUT_ROOT}")
    for r in qualified:
        print(r.get("note_url"))
