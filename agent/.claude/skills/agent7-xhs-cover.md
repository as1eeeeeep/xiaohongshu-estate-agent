# Agent 7 — 小红书大字报封面 (XHS 文字配图)

Playwright 自动化小红书创作者中心「文字配图」，把笔记标题做成大字报封面（官方生成的高清原图）。
产出 = 每篇笔记的封面图 `photo_1`。与 Agent6（本地 AI 生图加字）是两套不同来源的封面。

## ⚠️ 强制红线：默认关闭，运行前必须先问用户

**任何编程助手在执行封面生成（`cover_grab.py` / `cover_batch.py`）之前，必须先问用户
「要不要开启大字报封面」，得到明确同意才能跑。** 不允许"跑完笔记顺手自动配封面"。

原因：会启动真实浏览器、用用户已登录的小红书账号做自动化（账号风控风险），是联网外部动作，
不该默认静默执行。问一句，再跑。

## 前置（只需一次）

```bash
cd "/Users/asleep/松鼠找房/agent" && source .venv/bin/activate
python 07_Agent_XHSCover/login.py     # 手机扫码登录，存 xhs_auth_state.json（本目录, gitignore）
```
cookie 失效后重跑 login.py。环境需 playwright + chromium（`python -m playwright install chromium`）。

## 用法

```bash
# 单篇
python 07_Agent_XHSCover/cover_grab.py --text "标题" --out "/path/photo_1.png"
python 07_Agent_XHSCover/cover_grab.py --text "标题" --out-dir "/dir" --n-styles 5  # 多风格对比

# 批量：notes 目录每子文件夹一篇(含 note.txt)，逐篇随机风格 → 存 photo_1.png
python 07_Agent_XHSCover/cover_batch.py --notes-dir "/.../<run_id>/notes" --seed 630
#   --headless 不弹窗（默认弹窗更稳）  --seed 复现风格选择
```

## 要点

- 风格：基础/涂鸦/简约/边框/便签/涂写/备忘…；批量每篇**随机**选一个
- 无损抓原图：JS 把 swiper-img 的 blob 转 base64 落盘（非截图，失败才回退截图）
- 画幅 3:4，文字清晰；审美标准见 `小红书写作创作交接包_20260616/docs/04-大字报封面与生图SOP.md`
- 详细文档：`07_Agent_XHSCover/README.md`
