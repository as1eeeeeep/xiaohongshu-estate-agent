"""
批量拉取小红书图文笔记内容（文本+图片）到本地目录。
使用 xhs read 获取笔记详情，Python requests 下载图片。
XHS-Downloader CLI 有 bug，此脚本替代其功能。
"""

import os
import sys
import json
import re
import subprocess
import time
import requests
from pathlib import Path
from typing import Optional

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure parent `agent` directory is on sys.path for shared config
sys.path.append(str(Path(__file__).resolve().parents[1]))
from shared import OUTPUTS_DIR, DOWNLOADS_DIR

QUALIFIED_URLS = OUTPUTS_DIR / "qualified_urls.txt"
OUTPUT_DIR = DOWNLOADS_DIR
XHS_CLI_CMD = "xhs"
SLEEP_BETWEEN = 3  # 笔记间休眠，防风控
REQUEST_TIMEOUT = 30


def xhs_subprocess(args: list[str], timeout: int = 60) -> dict:
    proc = subprocess.run(
        [XHS_CLI_CMD] + args,
        capture_output=True, text=True, timeout=timeout,
        encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONLEGACYWINDOWSSTDIO": "utf-8"},
    )
    if proc.returncode != 0:
        raise RuntimeError(f"xhs CLI exit={proc.returncode}: {proc.stderr[:200]}")
    envelope = json.loads(proc.stdout)
    if not envelope.get("ok"):
        err = envelope.get("error", {})
        raise RuntimeError(f"xhs API error [{err.get('code')}]: {err.get('message')}")
    return envelope


def parse_note_id(url: str) -> str:
    m = re.search(r"/discovery/item/([a-fA-F0-9]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"/explore/([a-fA-F0-9]+)", url)
    if m:
        return m.group(1)
    return ""


def read_note(note_id: str) -> dict:
    """调用 xhs read 获取笔记详情。"""
    envelope = xhs_subprocess(["read", note_id, "--json"], timeout=60)
    items = envelope.get("data", {}).get("items", [])
    if not items:
        raise RuntimeError(f"笔记 {note_id} 无数据")
    note_card = items[0].get("note_card", {})
    return {
        "title": note_card.get("display_title") or note_card.get("title", "无标题"),
        "desc": note_card.get("desc", ""),
        "images": [
            img.get("url_default") or img.get("url_pre", "")
            for img in note_card.get("image_list", [])
        ],
        "note_id": note_card.get("note_id", note_id),
    }


def sanitize_filename(name: str, max_len: int = 60) -> str:
    """清理文件名中的非法字符。"""
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = name.strip().strip(".")
    return name[:max_len]


def download_image(url: str, save_path: Path) -> bool:
    """下载单张图片，返回是否成功。"""
    if not url or not url.startswith("http"):
        return False
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "Referer": "https://www.xiaohongshu.com/",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        save_path.write_bytes(resp.content)
        return True
    except Exception as e:
        print(f"      [warn] 图片下载失败: {e}")
        return False


def process_url(url: str, output_dir: Path) -> bool:
    """处理单条 URL：读取笔记 → 保存 txt → 下载图片。"""
    note_id = parse_note_id(url)
    if not note_id:
        print(f"  [skip] 无法解析 note_id: {url[:60]}")
        return False

    print(f"  读取笔记: {note_id[:24]} ...")
    try:
        note = read_note(note_id)
    except Exception as e:
        print(f"  [fail] xhs read 失败: {e}")
        return False

    title = note["title"]
    desc = note["desc"]
    images = note["images"]

    # 创建子目录: {note_id}_{sanitized_title}
    safe_title = sanitize_filename(title)
    subdir = output_dir / f"{note_id}_{safe_title}"
    subdir.mkdir(parents=True, exist_ok=True)

    # 保存文本
    txt_path = subdir / f"{note_id}.txt"
    txt_content = f"标题: {title}\n\n{desc}"
    txt_path.write_text(txt_content, encoding="utf-8")
    print(f"    txt: {txt_path.name} ({len(desc)} 字)")

    # 下载图片
    img_count = 0
    for i, img_url in enumerate(images):
        ext = ".webp"
        if ".jpg" in img_url.lower() or ".jpeg" in img_url.lower():
            ext = ".jpg"
        elif ".png" in img_url.lower():
            ext = ".png"
        img_path = subdir / f"{note_id}_{i+1:02d}{ext}"
        if download_image(img_url, img_path):
            img_count += 1
        time.sleep(0.3)  # 图片间微休眠

    print(f"    imgs: {img_count}/{len(images)} 张下载成功")
    print(f"    -> {subdir.name}")
    return True


def main():
    if not QUALIFIED_URLS.exists():
        print(f"文件不存在: {QUALIFIED_URLS}")
        return

    urls = []
    for line in QUALIFIED_URLS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("http"):
            urls.append(line)

    print(f"共 {len(urls)} 条笔记待下载")
    print(f"输出目录: {OUTPUT_DIR}\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    success = 0
    for i, url in enumerate(urls):
        print(f"[{i+1}/{len(urls)}] {url[:90]}...")
        try:
            if process_url(url, OUTPUT_DIR):
                success += 1
        except Exception as e:
            print(f"  [error] 未处理异常: {e}")

        if i < len(urls) - 1:
            time.sleep(SLEEP_BETWEEN)

    print(f"\n{'=' * 50}")
    print(f"完成: {success}/{len(urls)} 条笔记下载成功")
    print(f"输出目录: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
