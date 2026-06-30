# -*- coding: utf-8 -*-
"""
首次登录小红书，保存登录状态到文件。只需跑一次。
登录成功后会自动检测并保存，无需按 Enter。
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
from playwright.sync_api import sync_playwright

STATE_FILE = Path(__file__).parent / "xhs_auth_state.json"
URL = "https://creator.xiaohongshu.com/publish/publish?source=official"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=300)
    ctx = browser.new_context()
    page = ctx.new_page()

    print("打开小红书创作者中心...")
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)

    print("=" * 50)
    print("请在弹出的浏览器里完成登录（扫码或账号密码）")
    print("登录成功后会自动保存，请耐心等待（最多等3分钟）...")
    print("=" * 50)

    # 等待登录成功：检测页面上出现「发布笔记」或「上传图文」等元素
    try:
        page.wait_for_selector(
            "text=上传图文, text=发布笔记, text=创作灵感, [class*='publish']",
            timeout=180000  # 最多等3分钟
        )
        print("✓ 检测到已登录！")
    except Exception:
        print("⚠ 超时未检测到登录成功，仍尝试保存当前状态...")

    ctx.storage_state(path=str(STATE_FILE))
    print(f"✓ 登录状态已保存: {STATE_FILE}")
    print("3秒后自动关闭浏览器...")
    page.wait_for_timeout(3000)
    browser.close()
    print("完成！")
