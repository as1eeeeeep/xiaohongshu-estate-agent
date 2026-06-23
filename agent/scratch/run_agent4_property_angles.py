"""用升级后的 Agent4 为 3 个房源各写 4 个角度，共 12 篇笔记。"""
import sys
import json
import random
from pathlib import Path
from importlib import import_module

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

writer = import_module("03_Agent_Generator.writer")
a4 = import_module("04_Agent_AmateurViral.writer4")

TARGET_KEYWORDS = [
    "西營盤🇭🇰$440萬大一房一廳帶衣帽間",
    "灣仔尚翘峰$1200萬",
    "銅鑼灣🇭🇰大一房_$438萬_平地電梯",
]

OUTPUT_DIR = Path("D:/xiaohongshu_estate/06_output(multiangle)")
ANGLE_ORDER = ["放弃叙事", "优缺点总结", "看房日记", "笋盘推荐"]

MULTIANGLE_TRAINING_DIR = Path("D:/xiaohongshu_estate/04_outputs/multiangle_training/analyzed")


def load_reference_notes(analyzed_dir: Path) -> list[dict]:
    notes = []
    if not analyzed_dir.exists():
        return notes
    for f in sorted(analyzed_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data:
            notes.append(data)
    return notes


def main():
    all_props = writer.load_properties_from_dir()

    targets = []
    for kw in TARGET_KEYWORDS:
        match = next((p for p in all_props if kw in p["name"]), None)
        if match is None:
            print(f"[WARN] 找不到房源: {kw}")
            continue
        targets.append(match)

    print(f"共 {len(targets)} 个房源，每个 {len(ANGLE_ORDER)} 个角度，共 {len(targets) * len(ANGLE_ORDER)} 篇")

    reference_pool = load_reference_notes(MULTIANGLE_TRAINING_DIR)
    print(f"参考范文池: {len(reference_pool)} 条 (来自 {MULTIANGLE_TRAINING_DIR})")

    run_id = a4.get_run_id()
    print(f"run_id = {run_id}")

    for prop in targets:
        for angle in ANGLE_ORDER:
            refs = random.sample(reference_pool, min(2, len(reference_pool))) if reference_pool else []
            a4.run(property_data=prop, angle_key=angle, reference_notes=refs, run_id=run_id, output_dir=OUTPUT_DIR)
            print("-" * 50)


if __name__ == "__main__":
    main()
