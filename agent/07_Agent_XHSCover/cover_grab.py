# -*- coding: utf-8 -*-
"""
小红书「文字配图」大字报封面抓取器 —— Mac 版（CLI）。
保留原 xhs_cover_grab.py 已验证的「无损抓原图」流程，去掉 Windows 硬编码，改成命令行参数。

前置：先跑一次 `python 07_Agent_XHSCover/login.py` 扫码登录，生成 xhs_auth_state.json。

用法（在 agent/ 目录下）：
  python 07_Agent_XHSCover/cover_grab.py --text "标题文字" --out "/path/to/photo_1.png"
  # 多抓几个风格变体（存到 --out 同目录，文件名带风格后缀）：
  python 07_Agent_XHSCover/cover_grab.py --text "标题" --out-dir "/path/dir" --n-styles 3
"""
import sys
import argparse
import base64
import re
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

STATE_FILE = Path(__file__).parent / "xhs_auth_state.json"
URL = "https://creator.xiaohongshu.com/publish/publish?source=official"
DEBUG_DIR = Path(__file__).parent

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
    } catch(e) {
        return 'ERROR:' + e.message;
    }
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True, help="输入到「文字配图」的标题文字")
    ap.add_argument("--out", default=None, help="单张封面输出完整路径（取第1个风格）")
    ap.add_argument("--out-dir", default=None, help="多风格输出目录（配合 --n-styles）")
    ap.add_argument("--n-styles", type=int, default=1, help="抓前几个风格，默认1")
    ap.add_argument("--headless", action="store_true", help="无头模式")
    args = ap.parse_args()

    if not args.out and not args.out_dir:
        print("✗ 必须指定 --out 或 --out-dir")
        sys.exit(2)
    if not STATE_FILE.exists():
        print(f"✗ 找不到登录态 {STATE_FILE}\n  请先运行：python 07_Agent_XHSCover/login.py 扫码登录")
        sys.exit(1)

    out_dir = Path(args.out_dir) if args.out_dir else Path(args.out).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless, slow_mo=300)
        ctx = browser.new_context(
            storage_state=str(STATE_FILE),
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
        )
        page = ctx.new_page()

        print("[1] 打开创作者中心...")
        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2500)

        print("[2] 点击「上传图文」...")
        page.get_by_text("上传图文", exact=True).first.wait_for(timeout=8000)
        page.get_by_text("上传图文", exact=True).first.evaluate("el => el.click()")
        page.wait_for_timeout(1800)

        print("[3] 点击「文字配图」...")
        page.get_by_text("文字配图").first.wait_for(timeout=10000)
        page.get_by_text("文字配图").first.evaluate("el => el.click()")
        page.wait_for_timeout(2000)

        print(f"[4] 输入文字: {args.text}")
        typed = False
        for sel in ["[contenteditable='true']", "textarea", ".ql-editor"]:
            els = page.locator(sel).all()
            if els:
                els[0].click()
                page.keyboard.press("Control+a")
                page.keyboard.type(args.text, delay=40)
                typed = True
                break
        if not typed:
            print("  ✗ 未找到文字输入框")
            page.screenshot(path=str(DEBUG_DIR / "mac_debug_noinput.png"))
            browser.close()
            sys.exit(3)
        page.wait_for_timeout(1000)

        print("[5] 点击「生成图片」...")
        page.get_by_text("生成图片").first.wait_for(timeout=8000)
        page.get_by_text("生成图片").first.evaluate("el => el.click()")
        page.wait_for_timeout(8000)

        print(f"[6] 提取前 {args.n_styles} 个风格...")
        thumb_cards = page.evaluate("""
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
        """)
        print(f"  风格卡片: {[c['text'] for c in thumb_cards]}")

        safe_text = re.sub(r'[\\/:*?\"<>|]', '_', args.text)[:30]
        saved = 0
        for i, card in enumerate(thumb_cards[:max(1, args.n_styles)]):
            label = card['text']
            page.mouse.click(card['x'], card['y'])
            page.wait_for_timeout(2000)
            dataurl = page.evaluate(JS_EXTRACT)

            # 决定输出路径
            if args.out and i == 0 and args.n_styles == 1:
                out_path = Path(args.out)
            else:
                ext = ".jpg" if (dataurl and dataurl.startswith("http") and ".jpg" in dataurl) else ".png"
                out_path = out_dir / f"{safe_text}_{label}{ext}"

            ok = False
            if dataurl and not dataurl.startswith("ERROR") and dataurl != "None":
                try:
                    ok = save_image(dataurl, out_path)
                except Exception as e:
                    print(f"  ✗ 保存失败({label}): {e}")
            if not ok:
                # 备用精准截图
                el = page.locator(".swiper-slide-active img.swiper-img").first
                if not el.count():
                    el = page.locator("img.swiper-img").first
                try:
                    if out_path.suffix.lower() not in (".png", ".jpg"):
                        out_path = out_path.with_suffix(".png")
                    el.screenshot(path=str(out_path))
                    ok = True
                except Exception as e2:
                    print(f"  ✗ 截图也失败({label}): {e2}")
            if ok:
                kb = out_path.stat().st_size // 1024
                print(f"  ✓ {label} → {out_path.name} ({kb}KB)")
                saved += 1

        print(f"\n完成：保存 {saved} 张 → {out_dir}")
        page.wait_for_timeout(1500)
        browser.close()
        sys.exit(0 if saved else 4)


if __name__ == "__main__":
    main()
