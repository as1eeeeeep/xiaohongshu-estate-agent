"""assembled/*/C{XX}.txt → assembled_md/*/{folder_name}.md"""
import shutil
from pathlib import Path

SRC = Path("D:/xiaohongshu_estate/06_output(multiangle)/20260615_1904_v2/assembled")
DST = Path("D:/xiaohongshu_estate/06_output(multiangle)/20260615_1904_v2/assembled_md")

DST.mkdir(parents=True, exist_ok=True)

count = 0
for src_folder in sorted(SRC.iterdir()):
    if not src_folder.is_dir():
        continue

    folder_name = src_folder.name
    dst_folder = DST / folder_name
    dst_folder.mkdir(parents=True, exist_ok=True)

    # 找 txt 文件（可能是 C{XX}.txt 或 note.txt）
    txt_files = list(src_folder.glob("*.txt"))
    if not txt_files:
        print(f"[SKIP] {folder_name}: 没有 txt 文件")
        continue

    txt_path = txt_files[0]
    content = txt_path.read_text(encoding="utf-8")

    # 写 md（用文件夹名做文件名）
    md_path = dst_folder / f"{folder_name}.md"
    md_path.write_text(content, encoding="utf-8")
    print(f"[OK] {folder_name}")

    # 复制图片
    for img in sorted(src_folder.glob("*.jpg")) + sorted(src_folder.glob("*.png")):
        shutil.copy2(img, dst_folder / img.name)

    count += 1

print(f"\n完成！共转换 {count} 篇")
print(f"输出: {DST}")
