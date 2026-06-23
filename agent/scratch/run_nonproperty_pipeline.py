"""
非房源内容两步流水线（已砍掉 Agent5 审稿 → 修改，因 Agent5 评分偏向中介出镜的笔记，修改建议反而拉低质量）：

  Step 1  Agent5 生成创作简报（含6种内容类型的要求 + 打样）
  Step 2  Agent4 按简报 + 真实XHS原型生成 6 篇非房源引流笔记

输出目录:
  D:/xiaohongshu_estate/06_output(multiangle)/<run_id>_nonprop/
"""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from importlib import import_module

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

a4 = import_module("04_Agent_AmateurViral.writer4")
a5 = import_module("05_Agent_TrafficCritic.critic5")

MULTIANGLE_OUTPUT_DIR = Path("D:/xiaohongshu_estate/06_output(multiangle)")
HK_TZ = timezone(timedelta(hours=8))


def _now_str(suffix: str = "") -> str:
    return datetime.now(HK_TZ).strftime("%Y%m%d_%H%M") + suffix


def main():
    run_id = _now_str("_nonprop")
    run_dir = MULTIANGLE_OUTPUT_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nrun_id  = {run_id}")
    print(f"run_dir = {run_dir}")

    # ─── Step 1: Agent5 生成创作简报 ──────────────────────────────────
    print("\n" + "=" * 60)
    print("  Step 1 · Agent5 生成非房源内容创作简报")
    print("=" * 60)

    brief_path = run_dir / "agent5_brief.json"
    brief = a5.generate_brief(save_path=brief_path)
    print(f"\n简报生成完成 ({len(brief.content_types)} 种内容类型):")
    for ct in brief.content_types:
        print(f"  · {ct.type_name}")
    print(f"\n整体策略: {brief.overview}")

    # ─── Step 2: Agent4 生成 6 篇非房源笔记 ──────────────────────────
    print("\n" + "=" * 60)
    print("  Step 2 · Agent4 按简报 + 真实XHS原型 生成非房源引流笔记")
    print("=" * 60)

    refs = a4.load_reference_notes()

    for ct in brief.content_types:
        print(f"\n  [{ct.type_name}]")
        note = a4.run_non_property(
            type_name=ct.type_name,
            brief_section=ct.model_dump(),
            reference_notes=refs,
            run_id=run_id,
            output_dir=MULTIANGLE_OUTPUT_DIR,
        )
        print(f"  标题: {note.hook_title}")

    print("\n" + "=" * 60)
    print(f"完成！6 篇笔记已生成")
    print(f"目录: {run_dir}")
    print(f"  drafts/        → JSON 草稿")
    print(f"  pre-published/ → Markdown 发布稿")
    print(f"  agent5_brief.json → Agent5 创作简报")
    print("=" * 60)


if __name__ == "__main__":
    main()
