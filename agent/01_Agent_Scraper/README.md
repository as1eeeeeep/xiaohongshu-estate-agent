# 01 Agent Scraper — 爆款笔记猎人 (Hunter)

自动化筛选高潜力的香港买房/租房小红书图文笔记，输出合格笔记链接并下载全文和图片，供 Agent 2 拆解使用。

工作流：

1. 用香港房产关键词调用 `xhs search`，同时提取 `note_id` + `xsec_token`
2. 拼装桌面端免登录分享链接
3. LLM 视角分类（素人/中介/教学向/投资客等），可按视角过滤
4. 获取评论区，LLM 轻量级意图二分类（有/无购房意图）
5. 满足询盘阈值（询盘数 ≥ 2 或询盘率 ≥ 20%）的笔记进入合格列表
6. 下载合格笔记全文 + 图片

## 安装

```bash
cd "/Users/asleep/松鼠找房/agent"
source .venv/bin/activate
pip install -r requirements.txt
```

需要已安装并登录 `xhs` CLI：

```bash
xhs status   # 确认 authenticated: true
xhs login    # 未登录时执行
```

## 使用

### 标准运行（关键词搜索模式）

```bash
cd "/Users/asleep/松鼠找房/agent"
python -m 01_Agent_Scraper.hunter
```

### 按视角过滤

```bash
python -m 01_Agent_Scraper.hunter --perspective 素人
python -m 01_Agent_Scraper.hunter --perspective 中介
```

### 按博主抓取

```bash
python -m 01_Agent_Scraper.hunter --red-id <小红书号>
```

### 快速启动脚本（预配置关键词 + 视角 + 时效窗口）

| 脚本 | 用途 | 时效 | 视角 | 目标量 |
|---|---|---|---|---|
| `run_amateur_buyhouse.py` | 抓素人买房/入伙/实拍笔记 | 不限时间 | 素人 | 100 条 |
| `run_agent_buyhouse.py` | 抓中介视角买房爆款 | 近 30 天 | 中介 | 80 条 |
| `run_amateur_2months.py` | 抓素人看房/买房日记 | 近 60 天 | 素人 | 80 条 |

```bash
python 01_Agent_Scraper/run_amateur_buyhouse.py
python 01_Agent_Scraper/run_agent_buyhouse.py
python 01_Agent_Scraper/run_amateur_2months.py
```

## 输出

```text
data_pipeline/stage1_raw/
  qualified_urls_{YYYY-MM-DD_HH-MM}.txt   # 本次合格链接归档

04_outputs/
  qualified_leads.json                     # 所有历史合格线索（追加，去重）
  downloads/{note_id}_{title}/
    {note_id}.txt                          # 笔记全文
    *.webp / *.jpg                         # 图片

01_materials/viral_examples/
  {HH时MM分}_爬取结果/                     # 每次运行的爬取结果文件夹（香港时区）
```

## 关键参数（`hunter.py` 头部常量）

| 参数 | 默认值 | 说明 |
|---|---|---|
| `PUBLISHED_WITHIN_DAYS` | 14 | 时效过滤，0 = 不限时间 |
| `MIN_INQUIRY_COUNT` | 2 | 合格最低询盘数 |
| `MIN_INQUIRY_RATIO` | 0.20 | 合格最低询盘率 |
| `SLEEP_BETWEEN_NOTES` | 3s | 笔记间节流 |
| `SLEEP_BETWEEN_SEARCHES` | 2s | 搜索间节流 |

## 防风控

- Cookie 超过 7 天时 xhs CLI 会自动尝试从浏览器刷新
- 触发验证码时自动指数退避重试（30s → 60s → 120s → 240s → 300s），连续 5 次中止
- LLM 调用失败时降级为关键词规则分类

## 与其他 Agent 的关系

```
Agent 1 (Hunter)
    ↓ 输出合格笔记链接 + 下载内容
Agent 2 (Analyzer) — 拆解爆款，提炼方法论
```

详细设计文档：`.claude/skills/agent1-hunter.md`
