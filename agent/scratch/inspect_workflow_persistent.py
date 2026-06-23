# -*- coding: utf-8 -*-
"""
打开一个不会自动关闭的浏览器窗口，用户自行登录/导航。
助手通过创建 signal_shot.flag 文件触发截图，创建 signal_stop.flag 文件触发关闭。
"""
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).parent
OUT_DIR = BASE / "wf_inspect"
OUT_DIR.mkdir(exist_ok=True)
SIGNAL_SHOT = BASE / "signal_shot.flag"
SIGNAL_STOP = BASE / "signal_stop.flag"
URL = "https://workflow.gnlab.com/b3cekgq6ryryd"

for f in (SIGNAL_SHOT, SIGNAL_STOP):
    if f.exists():
        f.unlink()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1680, "height": 1000})
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    print("[ready] 浏览器已打开，请自行登录并导航到目标页面。准备好后等待截图信号。", flush=True)

    counter = 0
    while True:
        if SIGNAL_STOP.exists():
            print("[stop] 收到停止信号，关闭浏览器。", flush=True)
            SIGNAL_STOP.unlink()
            break
        if SIGNAL_SHOT.exists():
            SIGNAL_SHOT.unlink()
            counter += 1
            shot_path = OUT_DIR / f"shot_{counter:02d}.png"
            txt_path = OUT_DIR / f"shot_{counter:02d}.txt"
            try:
                page.screenshot(path=str(shot_path))
                text = page.evaluate("() => document.body.innerText")
                txt_path.write_text(text, encoding="utf-8")
                print(f"[shot] 已保存 {shot_path.name}", flush=True)
            except Exception as e:
                print(f"[err] 截图失败: {e}", flush=True)
        time.sleep(1)

    browser.close()
print("脚本结束。", flush=True)
