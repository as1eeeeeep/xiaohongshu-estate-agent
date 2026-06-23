import os
import sys
import re
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

props_dir = Path("D:/xiaohongshu_estate/01_materials/properties/6.16主做")

# Create output folders
output_folders = [
    props_dir / "6.16主做_txt",
    props_dir / "txt"
]

for folder in output_folders:
    folder.mkdir(exist_ok=True)

def convert_md_content(content):
    lines = content.split('\n')
    clean_lines = []
    for line in lines:
        # Skip image markup lines like ![alt text](...)
        if line.strip().startswith('![') or '.jpg' in line.lower() or '.png' in line.lower() or '.jpeg' in line.lower():
            continue
        clean_lines.append(line)
        
    # Trim leading/trailing blank lines
    while clean_lines and clean_lines[0].strip() == '':
        clean_lines.pop(0)
    while clean_lines and clean_lines[-1].strip() == '':
        clean_lines.pop()
        
    return '\n'.join(clean_lines)

print(f"Scanning properties under: {props_dir}")

converted_count = 0

for root, dirs, files in os.walk(props_dir):
    # Skip the output folders themselves to avoid processing our own outputs
    if "6.16主做_txt" in root or "txt" in root:
        continue
        
    for f in files:
        if f.endswith('.md') and not f.startswith('info.md'):
            md_path = Path(root) / f
            print(f"Converting: {md_path.name}")
            
            content = md_path.read_text(encoding="utf-8")
            clean_text = convert_md_content(content)
            
            # Write to both output directories
            txt_name = f.replace('.md', '.txt')
            for folder in output_folders:
                txt_path = folder / txt_name
                txt_path.write_text(clean_text, encoding="utf-8")
                
            print(f"  -> Saved as {txt_name}")
            converted_count += 1

print(f"\nCompleted! Converted {converted_count} files.")
for folder in output_folders:
    print(f"Output folder: {folder}")
