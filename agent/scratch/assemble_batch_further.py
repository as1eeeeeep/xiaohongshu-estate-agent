import os
import shutil
from pathlib import Path

# Path definitions
BATCH_DIR = Path("D:/xiaohongshu_estate/04_outputs/batch_20260617_1648")
ASSEMBLED_DIR = BATCH_DIR / "assembled"

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Walk through each property folder in assembled
for prop_dir in ASSEMBLED_DIR.iterdir():
    if not prop_dir.is_dir():
        continue
        
    print(f"\nProperty: {prop_dir.name}")
    
    # Create v1 and v2 subfolders inside the property folder
    v1_dir = prop_dir / "v1"
    v2_dir = prop_dir / "v2"
    
    v1_dir.mkdir(exist_ok=True)
    v2_dir.mkdir(exist_ok=True)
    
    # Move files to their respective version folder
    for f in list(prop_dir.iterdir()):
        if not f.is_file():
            continue
            
        if "_v1" in f.name:
            dst = v1_dir / f.name
            shutil.move(str(f), str(dst))
            print(f"  Moved: {f.name} -> v1/")
        elif "_v2" in f.name:
            dst = v2_dir / f.name
            shutil.move(str(f), str(dst))
            print(f"  Moved: {f.name} -> v2/")
        else:
            print(f"  Skipped (no v1/v2 suffix): {f.name}")

print("\nFurther assembly completed successfully!")
