# Agent 7 — 小红书大字报封面 (XHS Cover / 文字配图)

用 Playwright 自动化小红书创作者中心的「文字配图」功能，把笔记标题做成**大字报封面**
（小红书原生生成的高清原图，非截图）。产出就是每篇笔记的封面图 `photo_1`。

> 与 **Agent6（CoverCreator）** 的区别：Agent6 是本地 AI 装修生图 + 排版加字；
> Agent7 是抓**小红书官方「文字配图」**生成的纯文字大字报封面，两者是不同风格的封面来源。

---

## ⚠️ 红线：默认不开启，运行前必须先问用户

**这个功能默认关闭。任何编程助手（Claude Code / Codex / 其他 agent）在跑封面生成
（`cover_grab.py` / `cover_batch.py`）之前，必须先明确询问用户「要不要开启大字报封面」，
得到同意后才能运行。** 原因：

- 它会启动真实浏览器、用用户已登录的小红书账号做自动化操作（有账号风控风险）
- 是联网外部动作，不该默认静默执行
- 用户可能只想要笔记正文，不需要封面

不要因为「跑完笔记顺手配封面」就自动触发。问一句，再跑。

---

## 前置：登录（只需一次）

封面抓取依赖已登录的小红书创作者中心会话，存在 `xhs_auth_state.json`（本目录，已 gitignore）。

```bash
cd "/Users/asleep/松鼠找房/agent"
source .venv/bin/activate
python 07_Agent_XHSCover/login.py   # 弹出浏览器，手机扫码登录，自动保存登录态
```

登录态会复用；cookie 失效（一般 7+ 天）后重跑 `login.py` 即可。

环境依赖：playwright + chromium。首次需 `python -m playwright install chromium`。

---

## 用法

### 单篇

```bash
python 07_Agent_XHSCover/cover_grab.py \
  --text "想在北角588万买2房 有人觉得离谱吗" \
  --out "/path/to/photo_1.png"

# 一次抓前 N 个风格变体（存到 --out-dir，文件名带风格后缀）
python 07_Agent_XHSCover/cover_grab.py --text "标题" --out-dir "/path/dir" --n-styles 5
```

### 批量（给一整批笔记配封面）

输入是一个 `notes/` 目录（每篇一个子文件夹，含 `note.txt`，首行=标题）。
逐篇读标题 → **随机选一个风格** → 抓大字报 → 存为该笔记文件夹里的 `photo_1.png`。

```bash
python 07_Agent_XHSCover/cover_batch.py \
  --notes-dir "/Users/asleep/松鼠找房/06_output(multiangle)/<run_id>/notes" \
  --seed 630          # 可选，固定随机风格选择，便于复现
  # --headless        # 可选，不弹浏览器窗口（默认弹窗，更稳）
```

| 参数 | 说明 |
|---|---|
| `--text` | （单篇）大字报文字，一般用笔记标题 |
| `--out` / `--out-dir` | （单篇）单张输出路径 / 多风格输出目录 |
| `--n-styles` | （单篇）抓前几个风格，默认 1 |
| `--notes-dir` | （批量）notes 目录，每子文件夹一篇 |
| `--seed` | （批量）随机种子，复现风格选择 |
| `--headless` | 无头模式（默认弹窗） |

---

## 风格

小红书「文字配图」内置风格：基础 / 涂鸦 / 简约 / 边框 / 便签 / 涂写 / 备忘 …
批量模式每篇**随机**选一个。单篇模式默认取第一个（基础），或用 `--n-styles` 抓多个对比。

## 原理 & 产出

- 进入创作者中心 → 上传图文 → 文字配图 → 输入标题 → 生成图片 → 遍历风格缩略图
- 用 JS 把 `swiper-img` 的 blob 原图转 base64 直接落盘（**无损**，不是截图；失败才回退精准截图）
- 画幅 3:4（1080×1440 量级），文字清晰无乱码

## 文件

| 文件 | 用途 |
|---|---|
| `login.py` | 首次扫码登录，生成 `xhs_auth_state.json` |
| `cover_grab.py` | 单篇 CLI 抓取器 |
| `cover_batch.py` | 批量给 notes 目录配封面（随机风格） |
| `xhs_auth_state.json` | 登录态（gitignore，不入库） |

> 配套审美标准见 `小红书写作创作交接包_20260616/docs/04-大字报封面与生图SOP.md`。
> 旧 Windows 版脚本在 `agent/scratch/xhs_cover_*.py`（已被本目录的 Mac 版取代）。
