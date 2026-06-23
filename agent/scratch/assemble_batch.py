import os
import shutil
from pathlib import Path

# Path definitions
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BATCH_DIR = Path("D:/xiaohongshu_estate/04_outputs/batch_20260617_1648")
PRE_PUB_DIR = BATCH_DIR / "pre-published"
ASSEMBLED_DIR = BATCH_DIR / "assembled"

ASSEMBLED_DIR.mkdir(parents=True, exist_ok=True)

# List of 7 property base names to group by
properties = [
    "【29】北角🇭🇰395万开阳海景一房一厅带平台",
    "【34】炮台山三房两卫，797呎670万_大三房！！",
    "【3】西營盤🇭🇰$440萬大一房一廳帶衣帽間_鳳凰層（帶電梯_一梯兩戶）",
    "【湾仔-1】灣仔🇭🇰筍盤_$440萬_（現一房_🉑間兩房）_平地電梯_交通方便_🈶少少海景",
    "【湾仔-2】銅鑼灣🇭🇰半新樓_大兩房_$850萬_交通方便🍀🏠",
    "灣仔🇭🇰開放式_$268万_有電梯（要走一層樓梯）",
    "铜锣湾超大1房🇭🇰（可间两房）_$445万_有電梯"
]

# Walk through pre-published files
for f in PRE_PUB_DIR.iterdir():
    if not f.is_file():
        continue
        
    matched_prop = None
    for prop in properties:
        # Check if the filename contains the property base name
        if prop in f.name:
            matched_prop = prop
            break
            
    if matched_prop:
        # Create target subfolder in assembled
        prop_subfolder = ASSEMBLED_DIR / matched_prop
        prop_subfolder.mkdir(parents=True, exist_ok=True)
        
        # Move file to the assembled subfolder
        dst_path = prop_subfolder / f.name
        shutil.move(str(f), str(dst_path))
        print(f"Moved: {f.name} -> assembled/{matched_prop}/")
    else:
        print(f"No match for file: {f.name}")

print("\nAssembly completed successfully!")
