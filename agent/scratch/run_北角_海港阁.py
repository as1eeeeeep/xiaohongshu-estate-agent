"""为北角-海港阁 生成五角度素人笔记（极简txt版）"""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from importlib import import_module

a4 = import_module("04_Agent_AmateurViral.writer4")

prop = {
    "name": "北角_海港閣",
    "district": "北角",
    "sub_district": "北角",
    "rooms": 1,
    "area_sqft": 248,
    "price_wan": 395,
    "floor": "21樓",
    "lift_type": "平地電梯（2部載客電梯）",
    "building": "海港閣",
    "building_age": "50年",
    "mtr_station": "北角",
    "mtr_walk_min": 5,
    "school_net_name": "校網14",
    "management_fee": "約700+/月",
    "rental_yield": "可租約16000/月",
    "features": "一房一廳帶平台！開陽海景，21樓高層，周邊有北角匯商場、健威坊",
}

output_dir = Path("D:/xiaohongshu_estate/06_output(multiangle)")
hk_tz = timezone(timedelta(hours=8))
run_id = datetime.now(hk_tz).strftime("%Y%m%d_%H%M")
refs = a4.load_reference_notes()
system_prompt = a4.load_system_prompt()

print(f"run_id = {run_id}")
print(f"房源: {prop['name']} | {prop['price_wan']}万 | {prop['area_sqft']}呎 | 带平台+海景")
print()

angles = list(a4.PROPERTY_ANGLES.keys())
for ak in angles:
    label = a4.PROPERTY_ANGLES[ak]
    print(f"--- {label} ---")

    user_prompt = a4.build_property_angle_prompt(prop, ak, refs)
    result = a4.call_llm(user_prompt, system_prompt)

    safe_name = a4.sanitize_filename(prop.get("name", "untitled"))
    prefix = f"agent4_{safe_name}_{ak}"
    txt_path = a4.save_simple_txt(result, run_id, output_dir, file_prefix=prefix)
    print(f"  标题: {result.hook_title}")
    print(f"  TXT: {txt_path}")
    print()

print(f"完成！目录: {output_dir / run_id}")
