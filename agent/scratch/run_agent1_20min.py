"""Agent 1 — 限时 20 分钟抓取素人视角买房/看房笔记，尽量多收集合格笔记。"""
import sys
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import importlib
hunter = importlib.import_module("01_Agent_Scraper.hunter")

TIME_BUDGET_SEC = 20 * 60

# 不限发布时间，聚焦素人买房/看房晒图主题
hunter.PUBLISHED_WITHIN_DAYS = 0

KEYWORDS = [
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
    "香港看房日记",
    "香港上车盘",
    "香港租房分享",
]


def main():
    start = time.monotonic()
    run_start = datetime.now(timezone(timedelta(hours=8)))

    hunter.logger.info("=" * 55)
    hunter.logger.info("  Agent 1 — 限时 20 分钟素人笔记抓取 启动")
    hunter.logger.info("=" * 55)

    notes = hunter.discover_notes(keywords=KEYWORDS, target_count=200, pages_per_keyword=5)
    hunter.logger.info(">>> 发现 %d 条候选笔记，开始素人视角过滤与处理...", len(notes))

    # 视角过滤
    hunter.logger.info("正在分类 %d 条笔记的写作视角...", len(notes))
    perspectives = hunter.classify_perspectives(notes)
    for note, p in zip(notes, perspectives):
        note["perspective"] = p
    target_notes = [n for n in notes if "素人" in n.get("perspective", "")]
    hunter.logger.info("视角过滤: %d 条中 %d 条为素人视角", len(notes), len(target_notes))

    results = []
    qualified = 0
    captcha_count = 0

    for i, note in enumerate(target_notes):
        elapsed = time.monotonic() - start
        if elapsed >= TIME_BUDGET_SEC:
            hunter.logger.info("已达 20 分钟时间预算，停止抓取。")
            break
        hunter.logger.info("\n[%d/%d] (已用时 %.0fs) %s", i + 1, len(target_notes), elapsed,
                            note["id"][:24] if note.get("id") else "?")
        try:
            result, captcha_count = hunter.process_note(note, captcha_count=captcha_count)
            if result:
                results.append(result)
                if result.get("triggered"):
                    qualified += 1
        except KeyboardInterrupt:
            hunter.logger.info("用户中断")
            break
        except RuntimeError as e:
            if "验证码" in str(e):
                hunter.logger.error("%s", e)
                break
            hunter.logger.error("未处理的异常，跳过此笔记: %s", e, exc_info=True)
        except Exception as e:
            hunter.logger.error("未处理的异常，跳过此笔记: %s", e, exc_info=True)

        if i < len(target_notes) - 1:
            time.sleep(hunter.SLEEP_BETWEEN_NOTES)

    total = len(results)
    hunter.logger.info("\n" + "=" * 55)
    hunter.logger.info("扫描完成: %d/%d 条合格 | 共处理 %d 条笔记 | 用时 %.0fs",
                        qualified, total, len(results), time.monotonic() - start)

    hunter.save_crawl_results(results, run_start)

    qualified_urls = [r["note_url"] for r in results if r.get("triggered")]
    if qualified_urls:
        urls_text = "\n".join(qualified_urls)
        hunter.STAGE1_DIR.mkdir(parents=True, exist_ok=True)
        run_start_str = run_start.strftime("%Y-%m-%d_%H-%M")
        archive_path = hunter.STAGE1_DIR / f"qualified_urls_{run_start_str}.txt"
        archive_path.write_text(urls_text, encoding="utf-8")
        hunter.logger.info("合格链接归档已保存至: %s", archive_path)

    print("\n" + "=" * 55)
    print(f"合格笔记数: {qualified}")
    for r in results:
        if r.get("triggered"):
            print(r.get("note_url"), "|", r.get("download_dir"))


if __name__ == "__main__":
    main()
