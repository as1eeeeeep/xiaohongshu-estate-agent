# -*- coding: utf-8 -*-
"""调试：在生成封面页面上找到大预览卡片的 CSS 选择器"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path
from playwright.sync_api import sync_playwright

STATE_FILE = Path(__file__).parent / "xhs_auth_state.json"
URL = "https://creator.xiaohongshu.com/publish/publish?source=official"
TEXT = "西营盘这套440万的房，纠结好久还是没敢买…"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=300)
    ctx = browser.new_context(storage_state=str(STATE_FILE), viewport={"width": 1440, "height": 900})
    page = ctx.new_page()

    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)
    page.get_by_text("上传图文", exact=True).first.evaluate("el => el.click()")
    page.wait_for_timeout(1500)
    page.get_by_text("文字配图").first.evaluate("el => el.click()")
    page.wait_for_timeout(2000)

    els = page.locator("[contenteditable='true']").all()
    els[0].click()
    page.keyboard.press("Control+a")
    page.keyboard.type(TEXT, delay=40)
    page.wait_for_timeout(800)

    page.get_by_text("生成图片").first.evaluate("el => el.click()")
    page.wait_for_timeout(8000)

    # 打印左侧所有中等大小元素的 class 和 bbox
    info = page.evaluate("""
    () => {
        const results = [];
        for (const el of document.querySelectorAll('*')) {
            const r = el.getBoundingClientRect();
            // 只看左侧区域（x < 600），中等大小（面积在 40000~300000 之间）
            if (r.left < 600 && r.left >= 0 && r.width > 150 && r.height > 150) {
                const area = r.width * r.height;
                if (area > 40000 && area < 400000) {
                    results.push({
                        tag: el.tagName,
                        cls: el.className.toString().slice(0, 80),
                        id: el.id,
                        x: Math.round(r.x), y: Math.round(r.y),
                        w: Math.round(r.width), h: Math.round(r.height),
                        area: Math.round(area),
                    });
                }
            }
        }
        // 按面积降序
        return results.sort((a,b) => b.area - a.area).slice(0, 20);
    }
    """)

    print("=== 左侧区域候选元素（按面积降序）===")
    for item in info:
        print(f"  {item['tag']} cls=[{item['cls']}] id=[{item['id']}]")
        print(f"    bbox: x={item['x']} y={item['y']} w={item['w']} h={item['h']} area={item['area']}")
        print()

    page.wait_for_timeout(3000)
    browser.close()
