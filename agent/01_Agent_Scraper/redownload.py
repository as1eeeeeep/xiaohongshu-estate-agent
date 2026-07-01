"""
补下载脚本：读取报告 JSON，对所有未成功下载的笔记（或全部）重新下载，
并传 xsec_token 给 xhs read 修复 token 验证失败的问题。

用法：
  python 01_Agent_Scraper/redownload.py <report.json> [--all]

  --all  重新下载报告里的全部笔记（不只是失败的）
"""
import sys
import json
import time
import shutil
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hunter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", help="报告 JSON 路径")
    parser.add_argument("--all", action="store_true", help="重下全部，不只是失败的")
    args = parser.parse_args()

    report_path = Path(args.report)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    notes = report["notes"]

    # 输出目录 = 报告所在文件夹
    out_dir = report_path.parent
    hunter.DOWNLOADS_DIR = out_dir / "downloads"
    hunter.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    if args.all:
        targets = notes
    else:
        targets = [n for n in notes if not n.get("download_ok")]

    print(f"目标: {len(targets)} 条 ({'全部' if args.all else '仅失败'})")
    print(f"输出: {hunter.DOWNLOADS_DIR}")
    print("=" * 55)

    ok = 0
    for i, note in enumerate(targets):
        note_id = note["note_id"]
        xsec = note.get("xsec_token", "") or ""
        title = note.get("title", "")
        note_url = note.get("note_url", "")

        # 先清空旧的空目录（失败时留下的）
        import re
        safe_title = re.sub(r'[\\/:*?"<>|]', "_", title)[:40] if title else ""
        folder_name = f"{note_id}_{safe_title}" if safe_title else f"{note_id}_"
        old_dir = hunter.DOWNLOADS_DIR / folder_name
        if old_dir.exists():
            txt_files = list(old_dir.glob("*.txt"))
            if not txt_files:
                shutil.rmtree(old_dir)

        print(f"[{i+1}/{len(targets)}] {title[:45]}")
        try:
            dl = hunter.download_note_content(
                note_id, xsec_token=xsec,
                note_url=note_url, note_title=title,
            )
            if dl:
                ok += 1
                note["download_ok"] = True
                note["download_dir"] = str(dl)
            else:
                print("  ⚠ 返回 None")
        except Exception as e:
            print(f"  ✗ {e}")

        if i < len(targets) - 1:
            time.sleep(hunter.SLEEP_BETWEEN_NOTES)

    # 更新报告
    report["downloaded_count"] = sum(1 for n in notes if n.get("download_ok"))
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 55)
    print(f"完成：本次成功 {ok}/{len(targets)} 条，报告总下载数 {report['downloaded_count']}/{len(notes)}")


if __name__ == "__main__":
    main()
