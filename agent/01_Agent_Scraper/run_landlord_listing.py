"""
业主放盘 笔记收集脚本
目标：收集小红书上素人视角的业主放盘笔记（不走询盘过滤，全量下载素人笔记）
输出：/Users/asleep/松鼠找房/02_scrap/
"""
import sys
import json
import time
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hunter

# === 输出目录（按启动时间自动命名） ===
_ts = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d_%H%M")
SCRAP_DIR = Path(f"/Users/asleep/松鼠找房/02_scrap_output/{_ts}")
SCRAP_DIR.mkdir(parents=True, exist_ok=True)
hunter.DOWNLOADS_DIR = SCRAP_DIR / "downloads"

# 不限发布时间
hunter.PUBLISHED_WITHIN_DAYS = 0

# 业主放租经历分享——香港房东视角，出租自己的房子
KEYWORDS = [
    "出租我的香港房子",
    "香港第一次当房东",
    "香港包租婆经历",
    "香港放租记录",
    "香港当房东经验",
    "香港业主出租经历",
    "香港收租生活",
    "香港放租自己的房",
    "香港房东分享",
    "香港业主放租心得",
    "香港收租攻略",
    "香港出租房子经验",
]


if __name__ == "__main__":
    hk_tz = timezone(timedelta(hours=8))
    run_start = datetime.now(hk_tz)

    print("=" * 55)
    print("  业主放盘笔记收集 启动")
    print(f"  时间: {run_start.strftime('%Y-%m-%d %H:%M')}")
    print(f"  输出目录: {SCRAP_DIR}")
    print(f"  关键词数: {len(KEYWORDS)}")
    print("=" * 55)

    # 1. 发现笔记（每词 5 页，目标 150 条去重候选）
    notes = hunter.discover_notes(
        keywords=KEYWORDS,
        target_count=150,
        pages_per_keyword=5,
        published_within_days=0,
    )
    print(f"\n>>> 发现 {len(notes)} 条候选笔记，开始素人视角分类...\n")

    if not notes:
        print("未发现笔记，退出。")
        sys.exit(0)

    # 2. 视角分类，只保留素人视角
    perspectives = hunter.classify_perspectives(notes)
    for note, p in zip(notes, perspectives):
        note["perspective"] = p

    dist = Counter(perspectives)
    print(f"视角分布: {dict(dist)}")

    amateur_notes = [n for n in notes if "素人" in n.get("perspective", "")]
    print(f"\n素人视角笔记: {len(amateur_notes)} 条，开始全量下载...\n")

    # 3. 全量下载所有素人笔记（不走询盘过滤）
    results = []
    for i, note in enumerate(amateur_notes):
        title_preview = (note.get("title", "") or "")[:40]
        print(f"[{i+1}/{len(amateur_notes)}] {title_preview}")
        try:
            dl_dir = hunter.download_note_content(
                note["id"],
                xsec_token=note.get("xsec_token", ""),
                note_url=note["note_url"],
                note_title=note.get("title", ""),
            )
            results.append({
                "note_id": note["id"],
                "title": note.get("title", ""),
                "note_url": note["note_url"],
                "perspective": note.get("perspective", ""),
                "liked_count": note.get("liked_count", 0),
                "comment_count": note.get("comment_count", 0),
                "download_ok": dl_dir is not None,
                "download_dir": str(dl_dir) if dl_dir else "",
            })
        except Exception as e:
            print(f"  ⚠ 下载失败: {e}")
            results.append({
                "note_id": note["id"],
                "title": note.get("title", ""),
                "note_url": note["note_url"],
                "perspective": note.get("perspective", ""),
                "liked_count": note.get("liked_count", 0),
                "comment_count": note.get("comment_count", 0),
                "download_ok": False,
                "download_dir": "",
                "error": str(e),
            })

        if i < len(amateur_notes) - 1:
            time.sleep(hunter.SLEEP_BETWEEN_NOTES)

    # 4. 保存汇总报告
    report = {
        "run_time": run_start.strftime("%Y-%m-%d %H:%M"),
        "total_discovered": len(notes),
        "perspective_dist": dict(dist),
        "amateur_count": len(amateur_notes),
        "downloaded_count": sum(1 for r in results if r["download_ok"]),
        "notes": results,
    }
    report_path = SCRAP_DIR / f"report_{run_start.strftime('%Y-%m-%d_%H-%M')}.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n" + "=" * 55)
    print(f"完成！素人笔记: {len(amateur_notes)} 条 | 成功下载: {report['downloaded_count']} 条")
    print(f"报告: {report_path}")
    print(f"下载内容: {SCRAP_DIR / 'downloads'}")
    print("=" * 55)
