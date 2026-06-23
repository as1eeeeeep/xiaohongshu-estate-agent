# -*- coding: utf-8 -*-
"""炮台山 + 湾仔-2 各5角度 → 10篇笔记"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"D:\xiaohongshu_estate\agent")

from pathlib import Path
from importlib import import_module

writer4 = import_module("04_Agent_AmateurViral.writer4")

PROPS_DIR = Path(r"D:\xiaohongshu_estate\01_materials\properties\6.16主做")
OUT_DIR   = Path(r"D:\xiaohongshu_estate\04_outputs")

props = [
    {
        "name": "炮台山三房两卫 797呎670万",
        "sub_district": "炮台山",
        "district": "东区",
        "rooms": 3,
        "area_sqft": 797,
        "price_wan": 670,
        "floor": 15,
        "lift_type": "平地电梯（1座4部）",
        "mtr_station": "炮台山",
        "mtr_walk_min": 4,
        "school_net_name": "14校网",
        "renovation": "",
        "property_dir": str(PROPS_DIR / "【34】炮台山三房两卫，797呎670万_大三房！！"),
    },
    {
        "name": "铜锣湾半新楼大两房 850万",
        "sub_district": "铜锣湾",
        "district": "湾仔",
        "rooms": 2,
        "area_sqft": 406,
        "price_wan": 850,
        "floor": 8,
        "lift_type": "平地电梯",
        "mtr_station": "铜锣湾",
        "mtr_walk_min": 2,
        "school_net_name": "湾仔12校网",
        "renovation": "半新楼",
        "property_dir": str(PROPS_DIR / "【湾仔-2】銅鑼灣🇭🇰半新樓_大兩房_$850萬_交通方便🍀🏠"),
    },
]

ANGLES = ["放弃叙事", "优缺点总结", "看房日记", "纠结对比", "意外种草"]

for prop in props:
    name = prop["name"]
    print(f"\n{'='*50}")
    print(f"▸ {name}")
    print('='*50)

    for angle in ANGLES:
        print(f"  [{angle}] 生成中...", end=" ", flush=True)
        try:
            results = writer4.run(
                property_data=prop,
                angle_key=angle,
                output_dir=OUT_DIR,
            )
            for r in results:
                print(f"✓ {r.hook_title}")
        except Exception as e:
            print(f"✗ {e}")

print(f"\n完成！")
