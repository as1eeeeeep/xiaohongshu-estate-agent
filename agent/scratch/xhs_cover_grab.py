# -*- coding: utf-8 -*-
"""
从小红书「文字配图」获取大字报封面，直接提取原始图片数据（不截图，无损画质）。
每次运行自动保存前 N_STYLES 个风格的高清大图。
"""
import sys, base64, re, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
from playwright.sync_api import sync_playwright

# ── 配置区 ──────────────────────────────────────────────────────
STATE_FILE = Path(__file__).parent / "xhs_auth_state.json"
URL        = "https://creator.xiaohongshu.com/publish/publish?source=official"
OUT_DIR    = Path("D:/xiaohongshu_estate/04_outputs/xhs_textcard_covers")
DEBUG_DIR  = Path(__file__).parent

TEXT      = "西营盘这套440万的房，纠结好久还是没敢买…"
N_STYLES  = 3   # 每次抓前几个风格
# ────────────────────────────────────────────────────────────────

OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── JS：从 swiper-img 提取原图（blob URL 转 base64）──
JS_EXTRACT = """
async () => {
    // 取当前激活 slide 里的 swiper-img
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
        return img.src;  // 普通 URL 直接返回
    } catch(e) {
        return 'ERROR:' + e.message;
    }
}
"""

def save_image(src: str, path: Path, cookies: list = None) -> bool:
    """保存图片：支持 data URL 和 https CDN URL"""
    if src.startswith("data:"):
        header, b64 = src.split(",", 1)
        path.write_bytes(base64.b64decode(b64))
        return True
    if src.startswith("http"):
        # 直接下载 CDN 原图
        req = urllib.request.Request(src, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://creator.xiaohongshu.com/",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            path.write_bytes(resp.read())
        return True
    return False


if not STATE_FILE.exists():
    print("✗ 找不到登录状态，请先运行 xhs_login.py")
    sys.exit(1)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=400)
    ctx = browser.new_context(
        storage_state=str(STATE_FILE),
        viewport={"width": 1440, "height": 900},
        device_scale_factor=2,   # 2x 分辨率（截图备用）
    )
    page = ctx.new_page()

    # ── 1. 打开创作者中心 ──
    print("[1] 打开创作者中心...")
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2500)

    # ── 2. 点「上传图文」Tab ──
    print("[2] 点击「上传图文」...")
    page.get_by_text("上传图文", exact=True).first.wait_for(timeout=8000)
    page.get_by_text("上传图文", exact=True).first.evaluate("el => el.click()")
    page.wait_for_timeout(1800)

    # ── 3. 点「文字配图」──
    print("[3] 点击「文字配图」...")
    page.get_by_text("文字配图").first.wait_for(timeout=10000)
    page.get_by_text("文字配图").first.evaluate("el => el.click()")
    page.wait_for_timeout(2000)

    # ── 4. 输入文字 ──
    print(f"[4] 输入文字...")
    for sel in ["[contenteditable='true']", "textarea", ".ql-editor"]:
        els = page.locator(sel).all()
        if els:
            els[0].click()
            page.keyboard.press("Control+a")
            page.keyboard.type(TEXT, delay=50)
            print(f"  ✓ 输入完成 (selector={sel})")
            break
    page.wait_for_timeout(1000)

    # ── 5. 点「生成图片」──
    print("[5] 点击「生成图片」...")
    page.get_by_text("生成图片").first.wait_for(timeout=8000)
    page.get_by_text("生成图片").first.evaluate("el => el.click()")
    print("  等待封面生成（8秒）...")
    page.wait_for_timeout(8000)
    page.screenshot(path=str(DEBUG_DIR / "debug_generated.png"))

    # ── 6. 找所有风格缩略图并遍历 ──
    print(f"[6] 提取前 {N_STYLES} 个风格的高清封面...")

    # 找风格缩略图容器（右侧列表）
    # 先截全屏看页面结构，并用 JS 找出所有可点击的风格卡
    # 找右侧每个风格项（缩略图 + 标签合在一起的父容器）
    thumb_cards = page.evaluate("""
    () => {
        // 找包含风格标签文字的小容器（整个风格卡=缩略图+标签）
        const allEls = Array.from(document.querySelectorAll('*'));
        const styleNames = ['基础','涂鸦','简约','边框','便签','涂写','备忘','手写','光影','几何'];
        const results = [];
        for (const name of styleNames) {
            // 找到文字匹配的 label 元素
            const labelEl = allEls.find(el =>
                el.childElementCount === 0 &&
                el.innerText?.trim() === name
            );
            if (!labelEl) continue;
            // 往上找父容器（包含缩略图的那层）
            let container = labelEl.parentElement;
            for (let i = 0; i < 4; i++) {
                const r = container.getBoundingClientRect();
                if (r.height > 80 && r.width > 60) break;
                container = container.parentElement;
            }
            const r = container.getBoundingClientRect();
            results.push({
                text: name,
                x: r.x + r.width / 2,
                y: r.y + r.height / 2 - 10,  // 点缩略图中心（略偏上避开label）
                w: r.width, h: r.height,
            });
        }
        return results;
    }
    """)
    print(f"  找到风格卡片: {[c['text'] for c in thumb_cards]}")

    safe_text = re.sub(r'[\\/:*?"<>|]', '_', TEXT)[:30]
    saved_count = 0

    for i, card in enumerate(thumb_cards[:N_STYLES]):
        style_label = card['text']
        print(f"\n  风格 {i+1}/{N_STYLES}: {style_label} (x={card['x']:.0f}, y={card['y']:.0f})")

        # 点击缩略图
        page.mouse.click(card['x'], card['y'])
        page.wait_for_timeout(2000)  # 等大图更新

        # 用 JS 提取大图（async JS 需用 evaluate）
        dataurl = page.evaluate(JS_EXTRACT)  # Playwright 自动 await async function

        if dataurl and not dataurl.startswith("ERROR") and dataurl != "None":
            ext = ".jpg" if (dataurl.startswith("http") and ".jpg" in dataurl) else ".png"
            fname = f"{safe_text}_{style_label}{ext}"
            out_path = OUT_DIR / fname
            try:
                save_image(dataurl, out_path)
                size_kb = out_path.stat().st_size // 1024
                print(f"  ✓ 已保存: {out_path.name} ({size_kb}KB)")
                saved_count += 1
            except Exception as e:
                print(f"  ✗ 保存失败: {e}")
        else:
            # 备用：精准裁剪 swiper-img 区域（2x 分辨率）
            print(f"  ⚠ JS提取失败（{dataurl}），改用精准截图...")
            img_el = page.locator(".swiper-slide-active img.swiper-img").first
            if not img_el.count():
                img_el = page.locator("img.swiper-img").first
            try:
                fname = f"{safe_text}_{style_label}.png"
                out_path = OUT_DIR / fname
                img_el.screenshot(path=str(out_path))
                size_kb = out_path.stat().st_size // 1024
                print(f"  ✓ 精准截图: {out_path.name} ({size_kb}KB)")
                saved_count += 1
            except Exception as e2:
                print(f"  ✗ 截图也失败: {e2}")

    print(f"\n完成！共保存 {saved_count} 张封面 → {OUT_DIR}")
    page.wait_for_timeout(3000)
    browser.close()
