# -*- coding: utf-8 -*-
"""补C02-C10的封面（只跑封面，不重建文件夹）"""
import sys, re, base64, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

STATE_FILE = Path(r"D:\xiaohongshu_estate\agent\scratch\xhs_auth_state.json")
OUT_DIR    = Path(r"D:\xiaohongshu_estate\06_output(multiangle)\20260615_1904_v2\assembled")
URL        = "https://creator.xiaohongshu.com/publish/publish?source=official"
N_STYLES   = 3

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

def save_image(src: str, path_co: Path):
    if src.startswith("data:"):
        _, b64 = src.split(",", 1)
        path_co.write_bytes(base64.b64decode(b64))
    elif src.startswith("http"):
        req = urllib.request.Request(src, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://creator.xiaohongshu.com/",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            path_co.write_bytes(resp.read())

# 读取需要补的文件夹（有 note.txt 但没有 cover_*.jpg/png 的）
tasks = []
for d in sorted(OUT_DIR.iterdir()):
    if not d.is_dir():
        continue
    note_file = d / "note.txt"
    if not note_file.exists():
        continue
    # check if covers exist
    covers = list(d.glob("cover_*"))
    if len(covers) >= 3:
        continue  # already done

    title = ""
    for line in note_file.read_text(encoding="utf-8").splitlines():
        m = re.match(r"标题[：:]\s*(.+)", line)
        if m:
            title = m.group(1).strip()
            break
    if title:
        tasks.append({"title": title, "dest": d})

print(f"需补封面: {len(tasks)} 篇")
for t in tasks:
    print(f"  {t['title'][:40]}")
if not tasks:
    print("全部完成！")
    sys.exit(0)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=300)
    ctx = browser.new_context(storage_state=str(STATE_FILE), viewport={"width": 1440, "height": 900})
    page = ctx.new_page()

    for idx, task in enumerate(tasks):
        title = task["title"]
        dest  = task["dest"]
        print(f"\n[{idx+1}/{len(tasks)}] {title[:35]}")

        # 进入文字配图
        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
        page.get_by_text("上传图文", exact=True).first.evaluate("el => el.click()")
        page.wait_for_timeout(1500)
        page.get_by_text("文字配图").first.evaluate("el => el.click()")
        page.wait_for_timeout(2000)

        # 输入标题
        for sel in ["[contenteditable='true']", "textarea"]:
            els = page.locator(sel).all()
            if els:
                els[0].click()
                page.keyboard.type(title, delay=40)
                break
        page.wait_for_timeout(1000)

        # 生成图片
        page.get_by_text("生成图片").first.wait_for(timeout=10000)
        page.get_by_text("生成图片").first.evaluate("el => el.click()")
        print("  等待生成...")
        page.wait_for_timeout(8000)

        # 风格卡片
        thumb_cards = page.evaluate("""
        () => {
            const sn = ['基础','涂鸦','简约','边框','便签','涂写','备忘','手写','光影','几何'];
            const allEls = Array.from(document.querySelectorAll('*'));
            const results = [];
            for (const name of sn) {
                const le = allEls.find(el => el.childElementCount===0 && el.innerText?.trim()===name);
                if (!le) continue;
                let c = le.parentElement;
                for (let i=0;i<4;i++) { const r=c.getBoundingClientRect(); if(r.height>80&&r.width>60)break; c=c.parentElement; }
                const r=c.getBoundingClientRect();
                results.push({text:name,x:r.x+r.width/2,y:r.y+r.height/2-10});
            }
            return results;
        }
        """)

        saved = 0
        for card in thumb_cards[:N_STYLES]:
            style = card['text']
            page.mouse.click(card['x'], card['y'])
            page.wait_for_timeout(1800)

            src = page.evaluate(JS_EXTRACT)
            if src and not str(src).startswith("ERROR") and src != "None":
                ext = ".jpg" if ("http" in src and ".jpg" in src) else ".png"
                out_f = dest / f"cover_{style}{ext}"
                try:
                    save_image(src, out_f)
                    print(f"  ✓ cover_{style}{ext} ({out_f.stat().st_size//1024}KB)")
                    saved += 1
                except Exception as e:
                    print(f"  ✗ {style}: {e}")
            else:
                # 截图备用
                try:
                    img_el = page.locator(".swiper-slide-active img.swiper-img").first
                    if not img_el.count(): img_el = page.locator("img.swiper-img").first
                    out_f = dest / f"cover_{style}.png"
                    img_el.screenshot(path=str(out_f))
                    print(f"  ✓ cover_{style}.png (截图)")
                    saved += 1
                except Exception as e2:
                    print(f"  ✗ {style}截图也失败: {e2}")

        print(f"  → {saved}/3 张封面")

    page.wait_for_timeout(2000)
    browser.close()
print("\n完成！")
