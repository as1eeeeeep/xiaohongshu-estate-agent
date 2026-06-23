# -*- coding: utf-8 -*-
"""直接运行，避免命令行传中文参数的编码问题"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TEXT = "西营盘这套440万的房，纠结好久还是没敢买…"
OUT  = r"D:\xiaohongshu_estate\agent\scratch\test_xhs_cover.png"

# 直接 import 主模块并调用
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location(
    "grabber",
    str(pathlib.Path(__file__).parent / "xhs_cover_grabber.py")
)
mod = importlib.util.load_from_spec = None  # 不用 import 方式

# 直接内嵌逻辑，简洁版
from pathlib import Path
from playwright.sync_api import sync_playwright

EDGE_USER_DATA = Path(r"C:\Users\azzi\AppData\Local\Microsoft\Edge\User Data")
URL = "https://creator.xiaohongshu.com/publish/publish?source=official"

with sync_playwright() as p:
    print("[1/6] 启动 Edge（复用登录态）...")
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(EDGE_USER_DATA),
        channel="msedge",
        headless=False,
        slow_mo=800,
        args=["--disable-blink-features=AutomationControlled"],
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    print("[2/6] 打开创作者中心...")
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)

    # 截一张初始页面，方便 debug
    page.screenshot(path=r"D:\xiaohongshu_estate\agent\scratch\debug_01_loaded.png")
    print("  debug截图: debug_01_loaded.png")

    # 点击「上传图文」
    print("[3/6] 点击「上传图文」...")
    try:
        btn = page.locator("text=上传图文").first
        btn.wait_for(timeout=8000)
        btn.click()
        page.wait_for_timeout(1500)
        page.screenshot(path=r"D:\xiaohongshu_estate\agent\scratch\debug_02_after_upload.png")
        print("  debug截图: debug_02_after_upload.png")
    except Exception as e:
        print(f"  ⚠ 找不到「上传图文」按钮: {e}")
        page.screenshot(path=r"D:\xiaohongshu_estate\agent\scratch\debug_02_fail.png")

    # 点击「文字配图」
    print("[4/6] 点击「文字配图」...")
    try:
        btn2 = page.locator("text=文字配图").first
        btn2.wait_for(timeout=8000)
        btn2.click()
        page.wait_for_timeout(2000)
        page.screenshot(path=r"D:\xiaohongshu_estate\agent\scratch\debug_03_text_image.png")
        print("  debug截图: debug_03_text_image.png")
    except Exception as e:
        print(f"  ⚠ 找不到「文字配图」按钮: {e}")
        page.screenshot(path=r"D:\xiaohongshu_estate\agent\scratch\debug_03_fail.png")

    # 输入文字
    print(f"[5/6] 输入文字...")
    try:
        input_sel = "textarea, [contenteditable='true'], .ql-editor, input[type='text']"
        input_box = page.locator(input_sel).first
        input_box.wait_for(timeout=8000)
        input_box.click()
        page.keyboard.press("Control+a")
        page.keyboard.type(TEXT, delay=80)
        page.wait_for_timeout(3000)
        page.screenshot(path=r"D:\xiaohongshu_estate\agent\scratch\debug_04_typed.png")
        print("  debug截图: debug_04_typed.png")
    except Exception as e:
        print(f"  ⚠ 输入框操作失败: {e}")
        page.screenshot(path=r"D:\xiaohongshu_estate\agent\scratch\debug_04_fail.png")

    # 截取封面
    print("[6/6] 尝试截取封面预览...")
    preview_selectors = [
        ".preview-image", ".cover-preview", ".image-preview",
        "[class*='preview']", "[class*='cover']", "canvas", "img",
    ]
    saved = False
    for sel in preview_selectors:
        try:
            els = page.locator(sel).all()
            if not els:
                continue
            best, best_area = None, 0
            for el in els:
                box = el.bounding_box()
                if box and box["width"] * box["height"] > best_area:
                    best, best_area = el, box["width"] * box["height"]
            if best and best_area > 30000:
                best.screenshot(path=OUT)
                print(f"  ✓ 封面已保存: {OUT}  ({sel}, {best_area:.0f}px²)")
                saved = True
                break
        except:
            pass

    if not saved:
        page.screenshot(path=r"D:\xiaohongshu_estate\agent\scratch\debug_fullpage.png")
        print("  ⚠ 未能精准截取，已保存全屏: debug_fullpage.png")
        print("  请把截图发给我，我来调整选择器")

    input("按 Enter 关闭浏览器...")
    ctx.close()
