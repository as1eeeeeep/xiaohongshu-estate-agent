# -*- coding: utf-8 -*-
"""
批量打包20篇笔记：
- 随机抽10篇：生成小红书大字报封面（3风格）+ 配1张房源实拍图，每篇建文件夹
- 另外10篇：配1-2张实拍图，建文件夹
"""
import sys, re, random, shutil
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
from playwright.sync_api import sync_playwright

# ── 路径配置 ──────────────────────────────────────────────────────
NOTES_DIR   = Path(r"D:\xiaohongshu_estate\06_output(multiangle)\20260615_1904_v2\pre-published")
PROPS_DIR   = Path(r"D:\xiaohongshu_estate\01_materials\properties\6.16主做")
OUT_DIR     = Path(r"D:\xiaohongshu_estate\06_output(multiangle)\20260615_1904_v2\assembled")
STATE_FILE  = Path(r"D:\xiaohongshu_estate\agent\scratch\xhs_auth_state.json")
XHS_URL     = "https://creator.xiaohongshu.com/publish/publish?source=official"
N_STYLES    = 3
RANDOM_SEED = 42   # 固定种子让结果可复现，改成 None 则每次随机
# ─────────────────────────────────────────────────────────────────

# ── 笔记→房源目录的关键词映射 ──
PROP_MAP = {
    "西營盤":  "【3】西營盤",
    "北角":    "【29】北角",
    "灣仔-1":  "【湾仔-1】",
    "銅鑼灣":  "铜锣湾超大1房",
}

STYLE_NAMES = ['基础','涂鸦','简约','边框','便签','涂写','备忘','手写','光影','几何']

# ── JS 提取大图 ──
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

import base64, urllib.request

def save_image(src: str, path: Path):
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

def parse_title(note_path: Path) -> str:
    text = note_path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"标题[：:]\s*(.+)", text)
    return m.group(1).strip() if m else note_path.stem

def find_prop_dir(note_name: str) -> Path | None:
    for kw, prop_kw in PROP_MAP.items():
        if kw in note_name:
            for d in PROPS_DIR.iterdir():
                if d.is_dir() and prop_kw in d.name:
                    return d
    return None

def get_photos(prop_dir: Path) -> list:
    return sorted([
        f for f in prop_dir.iterdir()
        if f.suffix.lower() in ('.jpg', '.jpeg', '.png') and 'cover' not in f.name.lower()
    ])

def safe_folder_name(title: str) -> str:
    s = re.sub(r'[\\/:*?"<>|？！…｜]', '_', title)
    s = s.replace('\n', ' ').strip()
    s = s[:40].strip('_').strip()
    s = s.rstrip('.')   # Windows 不允许文件夹名以点结尾
    return s.strip()

# ── 1. 读取所有笔记 ──
notes = sorted(NOTES_DIR.glob("*.txt"))
print(f"共找到 {len(notes)} 篇笔记")

# ── 2. 随机分组 ──
rng = random.Random(RANDOM_SEED)
shuffled = notes[:]
rng.shuffle(shuffled)
cover_notes = shuffled[:10]   # 需要生成封面
photo_notes = shuffled[10:]   # 只配照片

print(f"\n【封面组 10篇】")
for n in cover_notes:
    print(f"  {parse_title(n)}")
print(f"\n【配图组 10篇】")
for n in photo_notes:
    print(f"  {parse_title(n)}")

OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── 3. 处理配图组（无需浏览器，直接复制）──
print(f"\n{'='*60}")
print("▸ 处理配图组（1-2张实拍图）")
print('='*60)

for i, note in enumerate(photo_notes, 1):
    title = parse_title(note)
    prop_dir = find_prop_dir(note.name)
    folder_name = f"P{i:02d}_{safe_folder_name(title)}"
    dest = OUT_DIR / folder_name
    dest.mkdir(parents=True, exist_ok=True)

    # 复制笔记
    shutil.copy2(note, dest / "note.txt")

    # 随机配1-2张照片
    if prop_dir:
        photos = get_photos(prop_dir)
        n_photos = rng.randint(1, 2)
        chosen = rng.sample(photos, min(n_photos, len(photos)))
        for i, ph in enumerate(chosen, 1):
            shutil.copy2(ph, dest / f"photo_{i}{ph.suffix}")
        print(f"  ✓ {folder_name[:30]}  [{len(chosen)}张实拍图]")
    else:
        print(f"  ⚠ {folder_name[:30]}  [未找到房源目录]")

# ── 4. 处理封面组（需要浏览器）──
print(f"\n{'='*60}")
print("▸ 处理封面组（生成大字报封面 + 1张实拍图）")
print('='*60)

if not STATE_FILE.exists():
    print("✗ 找不到登录状态，请先运行 xhs_login.py")
    sys.exit(1)

cover_tasks = []
for i, note in enumerate(cover_notes, 1):
    title = parse_title(note)
    prop_dir = find_prop_dir(note.name)
    folder_name = f"C{i:02d}_{safe_folder_name(title)}"
    dest = OUT_DIR / folder_name
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(note, dest / "note.txt")

    # 配1张实拍图
    if prop_dir:
        photos = get_photos(prop_dir)
        if photos:
            chosen = rng.choice(photos)
            shutil.copy2(chosen, dest / f"photo{chosen.suffix}")
    cover_tasks.append({"title": title, "dest": dest, "folder": folder_name, "note": note})

print(f"共 {len(cover_tasks)} 个标题需要生成封面，启动浏览器...")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=400)
    ctx = browser.new_context(
        storage_state=str(STATE_FILE),
        viewport={"width": 1440, "height": 900},
    )
    page = ctx.new_page()

    for idx, task in enumerate(cover_tasks):
        title  = task["title"]
        dest   = task["dest"]
        folder = task["folder"]
        print(f"\n[{idx+1}/{len(cover_tasks)}] {title[:35]}")

        # 每次重新进入文字配图页面（最可靠）
        print("  进入文字配图页面...")
        page.goto(XHS_URL, wait_until="domcontentloaded", timeout=30000)
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

        # 点「生成图片」
        page.get_by_text("生成图片").first.wait_for(timeout=8000)
        page.get_by_text("生成图片").first.evaluate("el => el.click()")
        print("  等待封面生成（8秒）...")
        page.wait_for_timeout(8000)

        # 找风格卡片
        thumb_cards = page.evaluate("""
        () => {
            const styleNames = ['基础','涂鸦','简约','边框','便签','涂写','备忘','手写','光影','几何'];
            const allEls = Array.from(document.querySelectorAll('*'));
            const results = [];
            for (const name of styleNames) {
                const labelEl = allEls.find(el =>
                    el.childElementCount === 0 && el.innerText?.trim() === name
                );
                if (!labelEl) continue;
                let container = labelEl.parentElement;
                for (let i = 0; i < 4; i++) {
                    const r = container.getBoundingClientRect();
                    if (r.height > 80 && r.width > 60) break;
                    container = container.parentElement;
                }
                const r = container.getBoundingClientRect();
                results.push({
                    text: name,
                    x: r.x + r.width/2,
                    y: r.y + r.height/2 - 10,
                });
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
                ext = ".jpg" if (src.startswith("http") and ".jpg" in src) else ".png"
                out_path = dest / f"cover_{style}{ext}"
                try:
                    save_image(src, out_path)
                    kb = out_path.stat().st_size // 1024
                    print(f"  ✓ cover_{style}{ext} ({kb}KB)")
                    saved += 1
                except Exception as e:
                    print(f"  ✗ cover_{style} 保存失败: {e}")
            else:
                # 备用截图
                img_el = page.locator(".swiper-slide-active img.swiper-img").first
                if not img_el.count():
                    img_el = page.locator("img.swiper-img").first
                try:
                    out_path = dest / f"cover_{style}.png"
                    img_el.screenshot(path=str(out_path))
                    print(f"  ✓ cover_{style}.png (截图备用)")
                    saved += 1
                except Exception as e:
                    print(f"  ✗ cover_{style} 截图也失败: {e}")

        print(f"  → 文件夹: {dest.name}  (封面{saved}张)")

    page.wait_for_timeout(2000)
    browser.close()

print(f"\n{'='*60}")
print(f"全部完成！输出目录：{OUT_DIR}")
print(f"文件夹数量：{len(list(OUT_DIR.iterdir()))}")
