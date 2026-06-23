"""为湾仔-1 積福大廈 生成五角度素人笔记"""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from importlib import import_module

a4 = import_module("04_Agent_AmateurViral.writer4")

prop = {
    "name": "灣仔-1_積福大廈",
    "district": "湾仔",
    "sub_district": "铜锣湾/会展",
    "rooms": 1,
    "area_sqft": 332,
    "price_wan": 440,
    "floor": "20樓",
    "lift_type": "平地電梯",
    "building": "積福大廈",
    "building_age": "50年",
    "mtr_station": "銅鑼灣/會展",
    "mtr_walk_min": 6,
    "school_net_name": "灣仔區校網",
    "features": "現一房可間兩房，有少少海景，管理完善，業主友好",
}

output_dir = Path("D:/xiaohongshu_estate/06_output(multiangle)")
hk_tz = timezone(timedelta(hours=8))
run_id = datetime.now(hk_tz).strftime("%Y%m%d_%H%M")
refs = a4.load_reference_notes()

print(f"run_id = {run_id}")
print(f"房源: {prop['name']} | {prop['price_wan']}万 | {prop['area_sqft']}呎 | {prop['building']}")
print()

angles = list(a4.PROPERTY_ANGLES.keys())
for ak in angles:
    label = a4.PROPERTY_ANGLES[ak]
    print(f"--- {label} ---")
    result = a4.run(
        property_data=prop,
        angle_key=ak,
        reference_notes=refs,
        run_id=run_id,
        output_dir=output_dir,
    )
    print(f"  标题: {result[0].hook_title}")
    print()

print(f"完成！目录: {output_dir / run_id}")
print(f"  pre-published/ → {len(angles)} 篇 Markdown")
print(f"  drafts/       → {len(angles)} 篇 JSON")
