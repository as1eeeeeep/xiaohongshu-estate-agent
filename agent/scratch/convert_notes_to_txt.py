import os
import sys
import re
import shutil
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

assembled_dir = Path("D:/xiaohongshu_estate/04_outputs/batch_20260617_1648/assembled")
output_base_dir = Path("D:/xiaohongshu_estate/06_output(multiangle)/6.16主做")

# Create output directories
output_base_dir.mkdir(parents=True, exist_ok=True)
flat_dir = output_base_dir / "flat"
structured_dir = output_base_dir / "structured"

flat_dir.mkdir(exist_ok=True)
structured_dir.mkdir(exist_ok=True)

def extract_note(md_path):
    content = md_path.read_text(encoding="utf-8")
    lines = content.split('\n')
    
    title = ""
    body_lines = []
    tags = ""
    found_title = False
    
    for line in lines:
        line_str = line.strip()
        
        # 1. Title
        if not found_title:
            if line_str.startswith('# '):
                title = line_str[2:].strip()
                found_title = True
                continue
            elif line_str.startswith('#'):
                title = line_str.lstrip('#').strip()
                found_title = True
                continue
            else:
                continue
        
        # 2. Skip disclaimer
        if "封面图片为装修效果参考" in line_str or "仅供展示装修后的空间效果" in line_str:
            continue
            
        # 3. Stop at reference / asset separator
        if line_str.startswith('---') or line_str.startswith('## 📁'):
            break
            
        # 4. Check if it's the tag line
        if line_str.startswith('#') and not line_str.startswith('# '):
            if '#' in line_str:
                tags = line_str
                continue
        
        # 5. Append to body
        body_lines.append(line)
        
    # Remove leading/trailing empty lines in body
    while body_lines and body_lines[0].strip() == '':
        body_lines.pop(0)
    while body_lines and body_lines[-1].strip() == '':
        body_lines.pop()
        
    body = '\n'.join(body_lines)
    return title, body, tags

def sanitize_filename(name: str) -> str:
    # Replace invalid windows filename characters
    return re.sub(r'[\\/*?:"<>|]', '', name).strip()

print(f"Scanning assembled directory: {assembled_dir}")

notes_processed = 0

for prop_path in assembled_dir.iterdir():
    if not prop_path.is_dir():
        continue
    
    prop_name = prop_path.name
    for version in ["v1", "v2"]:
        v_dir = prop_path / version
        if not v_dir.exists():
            continue
            
        # Find note file (exclude strategy files)
        md_files = [f for f in v_dir.glob(f"*_{version}.md") if "strategy" not in f.name]
        if not md_files:
            continue
        md_file = md_files[0]
        
        # Extract title, body, and tags
        title, body, tags = extract_note(md_file)
        if not title:
            print(f"  Warning: No title found in {md_file.name}")
            continue
            
        # Write clean txt file content
        txt_content = f"{title}\n\n{body}\n\n{tags}\n"
        
        # 1. Output flat file
        flat_txt_name = f"{prop_name}_{version}.txt"
        flat_txt_path = flat_dir / flat_txt_name
        flat_txt_path.write_text(txt_content, encoding="utf-8")
        
        # 2. Output structured note directory
        safe_title = sanitize_filename(title)
        note_folder = structured_dir / safe_title
        note_folder.mkdir(exist_ok=True)
        
        structured_txt_path = note_folder / "note.txt"
        structured_txt_path.write_text(txt_content, encoding="utf-8")
        
        # Copy cover image as photo_1.png
        cover_src = v_dir / f"{prop_name}_cover_{version}.png"
        if cover_src.exists():
            shutil.copy2(cover_src, note_folder / "photo_1.png")
            
        # Copy original photo as photo_2.jpg
        orig_src = v_dir / f"{prop_name}_cover_原图_{version}.jpg"
        if orig_src.exists():
            shutil.copy2(orig_src, note_folder / f"photo_2{orig_src.suffix}")
            
        print(f"  Processed: {prop_name} ({version}) -> '{title[:30]}...'")
        notes_processed += 1

print(f"\nDone! Processed {notes_processed} notes.")
print(f"Flat text files: {flat_dir}")
print(f"Structured note folders: {structured_dir}")
