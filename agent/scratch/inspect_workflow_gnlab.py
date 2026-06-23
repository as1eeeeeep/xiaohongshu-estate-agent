# -*- coding: utf-8 -*-
"""
打开光年AI工作流页面，给用户留时间登录，然后截图+导出可见文字，供分析画布结构。
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
from playwright.sync_api import sync_playwright

STATE_FILE = Path(__file__).parent / "workflow_gnlab_auth_state.json"
URL = "https://workflow.gnlab.com/b3cekgq6ryryd"
OUT_DIR = Path(__file__).parent / "wf_inspect"
OUT_DIR.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=100)
    ctx_kwargs = {"viewport": {"width": 1680, "height": 1000}}
    if STATE_FILE.exists():
        ctx_kwargs["storage_state"] = str(STATE_FILE)
        print("[i] 检测到已保存的登录状态，复用中...")
    ctx = browser.new_context(**ctx_kwargs)
    page = ctx.new_page()

    print(f"[1] 打开 {URL} ...")
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)
    page.screenshot(path=str(OUT_DIR / "step1_initial.png"))
    print("[1] 已保存初始截图 step1_initial.png")

    print("=" * 50)
    print("如果页面要求登录，请在弹出的浏览器窗口里完成登录。")
    print("接下来等待 90 秒，请在这段时间内登录并让画布加载出来...")
    print("=" * 50)
    page.wait_for_timeout(90000)

    page.screenshot(path=str(OUT_DIR / "step2_after_wait.png"), full_page=False)
    print("[2] 已保存等待后截图 step2_after_wait.png")

    try:
        text = page.evaluate("() => document.body.innerText")
        (OUT_DIR / "step2_body_text.txt").write_text(text, encoding="utf-8")
        print("[2] 已导出可见文字 step2_body_text.txt")
    except Exception as e:
        print(f"[!] 导出文字失败: {e}")

    ctx.storage_state(path=str(STATE_FILE))
    print(f"[i] 登录状态已保存到 {STATE_FILE.name}（下次可复用，免登录）")

    page.wait_for_timeout(2000)
    browser.close()
    print("完成。")
