"""
从小红书创作者中心「文字配图」功能抓取大字报封面图片。
用法:
    conda run -n xhs_browser python scratch/xhs_cover_grabber.py --text "你的标题文字" --out "输出路径.png"

原理: 复用 Edge 浏览器已登录的 Cookie（user-data-dir），无需重新扫码。
"""
import sys
import argparse
import time
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True, help="输入到「文字配图」的文字")
    parser.add_argument("--out", default="xhs_cover.png", help="保存路径")
    parser.add_argument("--style-index", type=int, default=0, help="选第几个样式（0=第一个）")
    parser.add_argument("--headless", action="store_true", help="无头模式（不显示浏览器）")
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    EDGE_USER_DATA = Path(r"C:\Users\azzi\AppData\Local\Microsoft\Edge\User Data")
    URL = "https://creator.xiaohongshu.com/publish/publish?source=official"

    with sync_playwright() as p:
        print(f"[1/6] 启动 Edge（复用登录态）...")
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(EDGE_USER_DATA),
            channel="msedge",
            headless=args.headless,
            slow_mo=500,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        print(f"[2/6] 打开创作者中心...")
        page.goto(URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        # 点击「上传图文」
        print(f"[3/6] 点击「上传图文」...")
        upload_btn = page.locator("text=上传图文").first
        upload_btn.wait_for(timeout=10000)
        upload_btn.click()
        page.wait_for_timeout(1500)

        # 点击「文字配图」
        print(f"[4/6] 点击「文字配图」...")
        text_img_btn = page.locator("text=文字配图").first
        text_img_btn.wait_for(timeout=10000)
        text_img_btn.click()
        page.wait_for_timeout(2000)

        # 找到文字输入框并输入
        print(f"[5/6] 输入文字: {args.text}")
        # 小红书文字配图的输入框通常是 contenteditable 或 textarea
        input_sel = "textarea, [contenteditable='true'], .ql-editor"
        input_box = page.locator(input_sel).first
        input_box.wait_for(timeout=10000)
        input_box.click()
        # 清空再输入
        input_box.press("Control+a")
        input_box.type(args.text, delay=50)
        page.wait_for_timeout(3000)  # 等生成预览

        # 截取封面预览区域
        print(f"[6/6] 截取封面预览...")
        # 先尝试找预览图容器
        preview_selectors = [
            ".preview-image",
            ".cover-preview",
            ".image-preview",
            "[class*='preview']",
            "[class*='cover']",
            "canvas",
        ]
        saved = False
        for sel in preview_selectors:
            els = page.locator(sel).all()
            if els:
                print(f"  找到预览元素: {sel} ({len(els)} 个)")
                # 取最大的那个（通常是封面）
                best = None
                best_area = 0
                for el in els:
                    try:
                        box = el.bounding_box()
                        if box and box["width"] * box["height"] > best_area:
                            best = el
                            best_area = box["width"] * box["height"]
                    except:
                        pass
                if best and best_area > 10000:
                    best.screenshot(path=args.out)
                    print(f"  ✓ 已保存: {args.out} ({best_area:.0f}px²)")
                    saved = True
                    break

        if not saved:
            # fallback: 截全屏让用户手动确认
            fallback = Path(args.out).with_name("fullpage_" + Path(args.out).name)
            page.screenshot(path=str(fallback), full_page=False)
            print(f"  ⚠ 未找到精准预览区，已截全屏: {fallback}")
            print(f"    请查看截图，然后告诉我预览区的 CSS 选择器或截图位置")

        input("按 Enter 关闭浏览器...")
        ctx.close()


if __name__ == "__main__":
    main()
