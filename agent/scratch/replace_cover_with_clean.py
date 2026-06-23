import shutil
from pathlib import Path

v2_dir = Path("d:/xiaohongshu_estate/04_outputs/batch_622_final/西营盘-10_华利楼/v2")
shutil.copy2(v2_dir / "cover_clean.png", v2_dir / "cover.png")
print("Replaced cover.png with cover_clean.png in final_dir")

batch_dir = Path("d:/xiaohongshu_estate/04_outputs/batch_622_marble_20260623_0944/pre-published/【西营盘-10】华利楼_(WAH_LEE_BUILDING)🇭🇰_2房$398萬_高性价比🏠")
if batch_dir.exists():
    shutil.copy2(
        batch_dir / "【西营盘-10】华利楼_(WAH_LEE_BUILDING)🇭🇰_2房$398萬_高性价比🏠_cover_v2_clean.png",
        batch_dir / "【西营盘-10】华利楼_(WAH_LEE_BUILDING)🇭🇰_2房$398萬_高性价比🏠_cover_v2.png"
    )
    print("Replaced cover_v2.png with cover_v2_clean.png in backup_dir")
else:
    print("Backup directory not found!")
