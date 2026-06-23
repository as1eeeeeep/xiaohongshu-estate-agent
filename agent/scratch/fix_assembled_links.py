import os
import sys
import re
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

assembled_dir = Path("D:/xiaohongshu_estate/04_outputs/batch_20260617_1648/assembled")

def fix_links_in_file(file_path: Path, prop_name: str, version: str):
    content = file_path.read_text(encoding="utf-8")
    
    # 1. Update relative material links
    # Old: ..\..\..\01_materials -> New: ..\..\..\..\..\01_materials
    # We use re.sub or simple replace. Let's make it robust to slash direction.
    content = content.replace("..\\..\\..\\01_materials", "..\\..\\..\\..\\..\\01_materials")
    content = content.replace("../../../01_materials", "../../../../../01_materials")
    
    # 2. Update multiangle training links
    # Old: ..\..\multiangle_training -> New: ..\..\..\..\multiangle_training
    content = content.replace("..\\..\\multiangle_training", "..\\..\\..\\..\\multiangle_training")
    content = content.replace("../../multiangle_training", "../../../../multiangle_training")
    
    # 3. Update local versioned files
    # Any reference to property_cover.png -> property_cover_v1.png, etc.
    # Note: re.escape is used to avoid issues with special characters or emoji in prop_name.
    escaped_prop = re.escape(prop_name)
    
    # Clean cover
    content = re.sub(
        escaped_prop + r"_cover_clean\.(png|jpg|jpeg)",
        prop_name + f"_cover_clean_{version}.\\1",
        content
    )
    
    # Cover
    content = re.sub(
        escaped_prop + r"_cover\.(png|jpg|jpeg)",
        prop_name + f"_cover_{version}.\\1",
        content
    )
    
    # Original image
    content = re.sub(
        escaped_prop + r"_cover_原图\.(png|jpg|jpeg)",
        prop_name + f"_cover_原图_{version}.\\1",
        content
    )
    
    # Strategy
    content = re.sub(
        escaped_prop + r"_(agent_)?strategy\.md",
        prop_name + f"_strategy_{version}.md",
        content
    )
    
    file_path.write_text(content, encoding="utf-8")
    print(f"Fixed links in: {file_path.relative_to(assembled_dir)}")

# Walk through properties and versions
for prop_path in assembled_dir.iterdir():
    if not prop_path.is_dir():
        continue
    prop_name = prop_path.name
    for version in ["v1", "v2"]:
        v_dir = prop_path / version
        if not v_dir.exists():
            continue
        for md_file in v_dir.glob("*.md"):
            fix_links_in_file(md_file, prop_name, version)

print("Markdown links fixing completed.")
