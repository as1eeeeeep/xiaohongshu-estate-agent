import os
import shutil
import re
import sys
from pathlib import Path

# Paths
BASE_DIR = Path(r"d:\xiaohongshu_estate")
INBOX_DIR = BASE_DIR / "01_materials" / "_inbox"
PROPERTIES_DIR = BASE_DIR / "01_materials" / "properties"

def main():
    # Reconfigure terminal stdout/stderr to UTF-8 on Windows
    if sys.platform.startswith("win"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except AttributeError:
            pass
            
    # Ensure directories exist
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    PROPERTIES_DIR.mkdir(parents=True, exist_ok=True)
    
    raw_file_path = INBOX_DIR / "raw.txt"
    
    if not raw_file_path.exists():
        print(f"Error: {raw_file_path} does not exist.")
        print(f"Please create 'raw.txt' in the {INBOX_DIR} folder with the property details.")
        return

    with open(raw_file_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
        
    if not content:
        print("Error: raw.txt is empty.")
        return

    lines = content.split('\n')
    # Get the first non-empty line to use as the folder name
    title = ""
    for line in lines:
        if line.strip():
            title = line.strip()
            break
            
    if not title:
        print("Error: Could not find a valid title in raw.txt.")
        return
        
    # Sanitize title for folder name (remove invalid characters)
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
    # Replace all whitespace (including non-breaking spaces) with underscores
    safe_title = re.sub(r'\s+', "_", safe_title)
    
    # Create the property folder
    property_dir = PROPERTIES_DIR / safe_title
    property_dir.mkdir(parents=True, exist_ok=True)
    
    # Identify and sort images/videos in the inbox (case-insensitive for extensions)
    images = []
    valid_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif', '.mp4', '.mov'}
    for f in INBOX_DIR.iterdir():
        if f.is_file() and f.suffix.lower() in valid_exts:
            images.append(f)
            
    # Natural sort key helper (e.g. "2.jpg" comes before "10.jpg")
    def natural_sort_key(p):
        return [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', p.name.lower())]
        
    images.sort(key=natural_sort_key)
        
    # Move and rename images, and prepare markdown media links
    md_image_links = []
    for i, img in enumerate(images, 1):
        new_name = f"{safe_title}_{i}{img.suffix.lower()}"
        dest_path = property_dir / new_name
        # If file already exists in destination, it will be overwritten
        shutil.move(str(img), str(dest_path))
        md_image_links.append(f"![alt text]({new_name})")
        
    # Prepare markdown content
    md_content = content + "\n\n" + "\n".join(md_image_links)
    
    # Write the markdown file (always name it info.md for consistency)
    md_file_path = property_dir / "info.md"
    with open(md_file_path, "w", encoding="utf-8") as f:
        f.write(md_content)
        
    # Clean up the inbox raw.txt (empty it instead of deleting it)
    with open(raw_file_path, "w", encoding="utf-8") as f:
        pass  # Just truncate the file to 0 bytes
    
    print(f"Success! Property '{safe_title}' has been processed.")
    print(f"Created folder: {property_dir}")
    print(f"Moved {len(images)} images.")
    print(f"Generated Markdown: {md_file_path}")

if __name__ == "__main__":
    main()
