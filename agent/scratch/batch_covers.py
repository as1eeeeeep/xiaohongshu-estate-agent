# -*- coding: utf-8 -*-
"""给 agent4_10notes 里的 10 篇笔记批量生成大字报封面"""
import sys, base64, urllib.request, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path
from playwright.sync_api import sync_playwright

STATE_FILE = Path(__file__).parent / "xhs_auth_state.json"
URL        = "https://creator.xiaohongshu.com/publish/publish?source=official"
NOTES_DIR  = Path(r"D:\xiaohongshu_estate\06_output(multiangle)\20260617_agent4_10notes")

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
    } catch(e) { return 'ERROR:'+e.message; }
}
"""

def save_image(src, path):
    if src.startswith("data:"):
        _, b64 = src.split(",", 1)
        path.write_bytes(base64.b64decode(b64))
    elif src.startswith("http"):
        req = urllib.request.Request(src, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://creator.xiaohongshu.com/",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            path.write_bytes(resp.read())

# 收集所有需要封面的文件夹和标题
tasks = []
for folder in sorted(NOTES_DIR.iterdir()):
    if not folder.is_dir(): continue
    for txt in folder.glob("*.txt"):
        title = txt.read_text(encoding="utf-8").splitlines()[0].strip()
        tasks.append({"title": title, "dest": folder})
        break

print(f"共 {len(tasks)} 篇需要封面")
for i, t in enumerate(tasks):
    print(f"  {i+1}. {t['title'][:40]}")

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

        # 找风格卡片
        cards = page.evaluate("""
        () => {
            const sn = ['基础','涂鸦','简约'];
            const all = Array.from(document.querySelectorAll('*'));
            const r = [];
            for (const name of sn) {
                const le = all.find(el => el.childElementCount===0 && el.innerText?.trim()===name);
                if (!le) continue;
                let c = le.parentElement;
                for (let i=0;i<4;i++) { const rr=c.getBoundingClientRect(); if(rr.height>80&&rr.width>60)break; c=c.parentElement; }
                const rr=c.getBoundingClientRect();
                r.push({text:name,x:rr.x+rr.width/2,y:rr.y+rr.height/2-10});
            }
            return r;
        }
        """)

        for card in cards:
            style = card['text']
            page.mouse.click(card['x'], card['y'])
            page.wait_for_timeout(1800)
            src = page.evaluate(JS_EXTRACT)

            if src and not str(src).startswith("ERROR") and src != "None":
                ext = ".jpg" if ("http" in src and ".jpg" in src) else ".png"
                out_f = dest / f"cover_{style}{ext}"
                try:
                    save_image(src, out_f)
                    print(f"  ✓ {out_f.name} ({out_f.stat().st_size//1024}KB)")
                except Exception as e:
                    print(f"  ✗ {style}: {e}")
            else:
                try:
                    img_el = page.locator(".swiper-slide-active img.swiper-img").first
                    out_f = dest / f"cover_{style}.png"
                    img_el.screenshot(path=str(out_f))
                    print(f"  ✓ {out_f.name} (截图)")
                except Exception as e2:
                    print(f"  ✗ {style}: {e2}")

    page.wait_for_timeout(2000)
    browser.close()

# 每文件夹只保留一张封面，重命名为 photo_1
print("\n合并封面 → photo_1.jpg...")
for folder in sorted(NOTES_DIR.iterdir()):
    if not folder.is_dir(): continue
    covers = sorted(folder.glob("cover_*"))
    if covers:
        # 保留基础的，删其他的
        best = None
        for c in covers:
            if "基础" in c.name:
                best = c
                break
        if not best:
            best = covers[0]
        best.rename(folder / f"photo_1{best.suffix}")
        for c in covers:
            if c != best and c.exists():
                c.unlink()
        print(f"  ✓ {folder.name[:35]}")

print("\n完成！")
