import sys
import json
import shutil
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Paths
BRAIN_DIR = Path("C:/Users/azzi/.gemini/antigravity-ide/brain/c24f3992-7e21-42d5-b824-0cad3cf40eb0")
PENDING_JSON = Path("D:/xiaohongshu_estate/agent/scratch/pending_covers.json")

if not PENDING_JSON.exists():
    print(f"Error: {PENDING_JSON} not found!")
    exit(1)

with open(PENDING_JSON, "r", encoding="utf-8") as f:
    tasks = json.load(f)

for idx, task in enumerate(tasks):
    # Find generated image matching luxury task
    prefix = f"cover_luxury_task_{idx}_"
    matches = list(BRAIN_DIR.glob(f"{prefix}*.png"))
    if not matches:
        print(f"Error: No generated image found for task {idx} ({task['property_name']})")
        continue
    
    # Sort by modification time to get the newest one if multiple exist
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    generated_img = matches[0]
    
    # Target paths
    target_cover = Path(task["target_cover_path"])
    target_clean = Path(task["target_clean_path"])
    
    # Ensure parent dir exists
    target_cover.parent.mkdir(parents=True, exist_ok=True)
    
    # Copy
    shutil.copy2(generated_img, target_cover)
    shutil.copy2(generated_img, target_clean)
    print(f"Distributed Task {idx}: {generated_img.name} -> {target_cover.name} & {target_clean.name}")

print("Done distributing luxury covers!")
