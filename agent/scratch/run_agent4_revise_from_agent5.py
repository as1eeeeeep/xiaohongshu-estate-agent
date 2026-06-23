"""根据 Agent5 的审稿意见，让 Agent4 对一批笔记做修改稿 (v2)。

输入: <run_dir>/agent5_review/review_<run_id>.json (Agent5 审稿结果)
      <run_dir>/drafts/*.json (Agent4 原始草稿)
输出: 新的 run_id 目录下的 drafts/ + pre-published/ (v2 修改稿)
"""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from importlib import import_module

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

a4 = import_module("04_Agent_AmateurViral.writer4")

MULTIANGLE_OUTPUT_DIR = Path("D:/xiaohongshu_estate/06_output(multiangle)")

ANGLE_KEYS = list(a4.PROPERTY_ANGLES.keys())


def extract_property_prefix(pre_published_stem: str) -> tuple[str, str]:
    """从 pre-published 文件名(去掉 'agent4_' 前缀和扩展名)中解析出 (safe_name, angle_key)。"""
    for angle in ANGLE_KEYS:
        marker = f"_{angle}_"
        if marker in pre_published_stem:
            safe_name, _rest = pre_published_stem.split(marker, 1)
            return safe_name, angle
    raise ValueError(f"无法从文件名解析角度: {pre_published_stem}")


def load_drafts_by_hook_title(run_dir: Path) -> dict[str, dict]:
    """加载 drafts/*.json，按 hook_title 索引。"""
    drafts: dict[str, dict] = {}
    for f in (run_dir / "drafts").glob("*.json"):
        data = json.loads(f.read_text(encoding="utf-8"))
        drafts[data["hook_title"]] = data
    return drafts


def main(run_dir: Path, output_dir: Path = MULTIANGLE_OUTPUT_DIR):
    review_path = run_dir / "agent5_review" / f"review_{run_dir.name}.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))

    drafts = load_drafts_by_hook_title(run_dir)
    overall_suggestions = review["overall_suggestions_for_agent4"]

    system_prompt = a4.load_system_prompt()

    hk_tz = timezone(timedelta(hours=8))
    run_id = datetime.now(hk_tz).strftime("%Y%m%d_%H%M") + "_v2"
    print(f"run_id = {run_id}")

    for nr in review["note_reviews"]:
        file_name = nr["file_name"]
        stem = file_name[len("agent4_"):-len(".md")]
        safe_name, angle_key = extract_property_prefix(stem)

        # 通过该角度的标题模式匹配原始草稿 (drafts 中 persona_note = 角度标签)
        angle_label = a4.PROPERTY_ANGLES[angle_key]
        match = next(
            (d for d in drafts.values() if d.get("_category") == angle_key and d.get("persona_note") == angle_label),
            None,
        )
        if match is None:
            # 兜底：按 _category 单独匹配（同一房源同角度只应有一篇）
            candidates = [d for d in drafts.values() if d.get("_category") == angle_key]
            match = candidates[0] if candidates else None
        if match is None:
            print(f"[WARN] 找不到原始草稿: {file_name}")
            continue

        original = a4.NoteContent.model_validate({k: v for k, v in match.items() if k != "_category"})

        print("-" * 50)
        print(f"修改: {safe_name} | {angle_label}")
        print(f"原标题: {original.hook_title} (评分 {nr['traffic_score']}/10)")

        revised = a4.revise_note(
            original=original,
            angle_key=angle_key,
            note_suggestions=nr["suggestions"],
            overall_suggestions=overall_suggestions,
            system_prompt=system_prompt,
        )

        prefix = f"agent4_{safe_name}_{angle_key}"
        a4.save_draft(revised, category=angle_key, run_id=run_id, output_dir=output_dir, file_prefix=f"draft_{prefix}")
        md_path = a4.save_pre_published(revised, category=angle_key, run_id=run_id, output_dir=output_dir, file_prefix=prefix)

        print(f"新标题: {revised.hook_title}")
        print(f"MD: {md_path}")

        # 移除已用掉的草稿，避免同角度下次被重复匹配
        if match["hook_title"] in drafts:
            del drafts[match["hook_title"]]

    print("=" * 50)
    print(f"修改稿已全部生成，run_id = {run_id}")
    print(f"目录: {output_dir / run_id}")


if __name__ == "__main__":
    src_run = Path("D:/xiaohongshu_estate/06_output(multiangle)/20260615_1842")
    main(src_run)
