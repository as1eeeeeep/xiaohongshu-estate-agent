# -*- coding: utf-8 -*-
"""
批量给笔记配小红书「文字配图」大字报封面 —— Mac 版。
复用一个浏览器会话，逐篇：读 note.txt 标题 → 随机选一个风格 → 抓大字报原图
→ 存为该笔记文件夹里的 photo_1.png（与笔记同文件夹配对）。

前置：07_Agent_XHSCover/xhs_auth_state.json 登录态（跑 login.py 扫码生成）。

用法（在 agent/ 目录下）：
  python 07_Agent_XHSCover/cover_batch.py --notes-dir "/path/.../notes" [--headless] [--seed 42]
"""
import sys
import argparse
import base64
import random
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

STATE_FILE = Path(__file__).parent / "xhs_auth_state.json"
URL = "https://creator.xiaohongshu.com/publish/publish?source=official"

JS_EXTRACT = """
async () => {
    const img = document.querySelector('.swiper-slide-active img.swiper-img')
               || document.querySelector('img.swiper-img');
    if (!img || !img.src) return null;
    try {
        if (img.src.startsWith('blob:')) {
            const resp = await fetch(img.src);
            const blob = await resp.blob();
            return await new Promise(resolve => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.readAsDataURL(blob);
            });
        }
        return img.src;
    } catch(e) { return 'ERROR:' + e.message; }
}
"""

JS_THUMBS = """
() => {
    const allEls = Array.from(document.querySelectorAll('*'));
    const styleNames = ['基础','涂鸦','简约','边框','便签','涂写','备忘','手写','光影','几何'];
    const results = [];
    for (const name of styleNames) {
        const labelEl = allEls.find(el =>
            el.childElementCount === 0 && el.innerText?.trim() === name);
        if (!labelEl) continue;
        let container = labelEl.parentElement;
        for (let i = 0; i < 4; i++) {
            const r = container.getBoundingClientRect();
            if (r.height > 80 && r.width > 60) break;
            container = container.parentElement;
        }
        const r = container.getBoundingClientRect();
        results.push({text: name, x: r.x + r.width/2, y: r.y + r.height/2 - 10});
    }
    return results;
}
"""


def save_image(src: str, path: Path) -> bool:
    if src.startswith("data:"):
        _, b64 = src.split(",", 1)
        path.write_bytes(base64.b64decode(b64))
        return True
    if src.startswith("http"):
        req = urllib.request.Request(src, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://creator.xiaohongshu.com/",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            path.write_bytes(resp.read())
        return True
    return False


def make_cover(page, text: str, out_path: Path) -> str:
    """单篇流程，返回所用风格名；失败抛异常。"""
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2500)
    page.get_by_text("上传图文", exact=True).first.wait_for(timeout=10000)
    page.get_by_text("上传图文", exact=True).first.evaluate("el => el.click()")
    page.wait_for_timeout(1800)
    page.get_by_text("文字配图").first.wait_for(timeout=10000)
    page.get_by_text("文字配图").first.evaluate("el => el.click()")
    page.wait_for_timeout(2000)

    typed = False
    for sel in ["[contenteditable='true']", "textarea", ".ql-editor"]:
        els = page.locator(sel).all()
        if els:
            els[0].click()
            page.keyboard.press("Control+a")
            page.keyboard.type(text, delay=35)
            typed = True
            break
    if not typed:
        raise RuntimeError("未找到文字输入框")
    page.wait_for_timeout(800)

    page.get_by_text("生成图片").first.wait_for(timeout=8000)
    page.get_by_text("生成图片").first.evaluate("el => el.click()")
    page.wait_for_timeout(8000)

    cards = page.evaluate(JS_THUMBS)
    if not cards:
        raise RuntimeError("未找到风格卡片")
    card = random.choice(cards)          # ★ 随机选风格
    page.mouse.click(card["x"], card["y"])
    page.wait_for_timeout(2000)

    dataurl = page.evaluate(JS_EXTRACT)
    if dataurl and not dataurl.startswith("ERROR") and dataurl != "None":
        if save_image(dataurl, out_path):
            return card["text"]
    # 备用精准截图
    el = page.locator(".swiper-slide-active img.swiper-img").first
    if not el.count():
        el = page.locator("img.swiper-img").first
    el.screenshot(path=str(out_path))
    return card["text"] + "(截图)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--notes-dir", required=True, help="notes 目录（含每篇一个子文件夹）")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--seed", type=int, default=None, help="随机种子（可复现风格选择）")
    ap.add_argument("--skip-existing", action="store_true", help="跳过已有 photo_1.png 的笔记（断点续跑）")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)
    if not STATE_FILE.exists():
        print(f"✗ 找不到登录态 {STATE_FILE}，先跑 07_Agent_XHSCover/login.py 扫码登录")
        sys.exit(1)

    notes_dir = Path(args.notes_dir)
    folders = sorted([d for d in notes_dir.iterdir() if d.is_dir() and (d / "note.txt").exists()])
    print(f"共 {len(folders)} 篇笔记，开始配大字报封面...\n")

    ok, fail = 0, 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless, slow_mo=250)
        ctx = browser.new_context(
            storage_state=str(STATE_FILE),
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
        )
        page = ctx.new_page()

        for i, folder in enumerate(folders, 1):
            title = (folder / "note.txt").read_text(encoding="utf-8").splitlines()[0].strip()
            out_path = folder / "photo_1.png"
            if args.skip_existing and out_path.exists():
                print(f"[{i}/{len(folders)}] {title[:28]}  · 跳过(已有封面)")
                continue
            print(f"[{i}/{len(folders)}] {title[:28]}")
            try:
                style = make_cover(page, title, out_path)
                kb = out_path.stat().st_size // 1024
                print(f"        ✓ 风格={style} → photo_1.png ({kb}KB)")
                ok += 1
            except Exception as e:
                print(f"        ✗ 失败: {str(e)[:100]}")
                fail += 1

        page.wait_for_timeout(1000)
        browser.close()

    print(f"\n===== 完成: {ok} 成功 / {fail} 失败 =====")


if __name__ == "__main__":
    main()
