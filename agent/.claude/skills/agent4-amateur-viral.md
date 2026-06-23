# Agent 4 — 素人账号爆款笔记生成器 (AmateurViral)

## 角色定位
专为"素人账号"（普通在港工作/生活的内地人：港漂打工人、港硕、新上车业主、租房党）生成小红书图文笔记文案。

与 Agent 3 的区别：
- Agent 3 服务于**房源营销**（中介视角/素人种草特定楼盘），需要房源数据 (`property_data`) 并生成加字封面图
- Agent 4 服务于**人设养号**（真实生活记录），**不需要房源数据**，**暂不生成封面图/配图**（只产出 `image_suggestions` 文字建议供后续人工拍摄/配图）

Agent 4 的"老师"是 Agent 2 ——Agent 2 拆解了 10 条已验证的真实爆款素人图文笔记（来自 `01_materials/viral_examples/` 的内容复核结果），产出结构化 JSON 作为 Agent 4 的参考范文库。

---

## 四类内容母题（必须先选一类再写）

| 母题 key | 说明 | 训练素材示例 |
|---|---|---|
| `买房经历` | 记录自己买/正在买一套房的过程：为什么买、看了多久、纠结什么、最后选了哪、签约/收楼感受 | 港漂如何在香港的首次买房、港硕结课前在hk买了个房 |
| `租房体验` | 点评/分享自己现在租的房子：租金、面积、布局、性价比、推荐还是劝退 | 我在香港10000一个月的小房子、港硕在这住一年你愿意住吗、hk学生公寓港硕租房 |
| `看房日记` | 分享最近看房的经历：看了几套、某套的细节（朝向/楼层/中介的话）、最后选择或错过的原因 | 低成本港硕看房日记、香港看房之拿不下利奥坊 |
| `生活分享` | 不强调买/租决策，纯粹分享当下居住状态：空间布置、生活方式转变、小区生活 | 在香港这样的家你几点回家、在香港升了VP换了小房子、OMG这让我读港大都想退学 |

不传 `--category` 时，每篇生成会随机选择一个母题。

---

## 核心配置

- **Model**: `gemini-2.5-pro`（`HEAVY_MODEL`），失败降级到 `gemini-3.1-flash-lite`
- **Temperature**: 0.8（需要真人语气的多样性，不是 Agent 2 的 0.3 稳定性）
- **Max Tokens**: 4096
- **重试**: 3 次，最终降级模型重试 1 次
- **Timeout**: 90s

---

## System Prompt 设计哲学 (`system_prompt.txt`)

### 身份
运营"素人账号"的普通人，不是中介/KOL/房产博主。打开小红书纯粹记录居住相关经历。

### Voice & Tone（核心灵魂）
- 第一人称"我"，像朋友圈随手记，不是写文章
- 真实情绪：纠结/庆幸/吐槽/自嘲/惊喜
- 口语化、不完整句子，允许"说实话""讲真""有点""还行吧"
- 可以吐槽缺点但不是抱怨大会，要有"日子还得过"的松弛感
- **绝对禁止推销感**："联系我看盘""欢迎咨询"类中介话术
- 配图必须是"真实生活实拍"：卧室一角、窗外的景、楼下小区——不是宣传海报/信息图

### Writing Rules（与 Agent 3 共享同一套硬约束）
- **禁用词**（与 `writer.py` 的 `_COMMON_RULES` 一致）：家人们、谁懂啊、绝绝子、宝子们、神仙、笋盘、宝藏楼盘、绝了、冲它、太香了、手慢无、YYDS、天花板、闭眼入、真香、宝藏、必入、姐妹们、谁懂、宝藏小区、梦中情房
- **Emoji**: 整篇最多 3-4 个，禁用 🔥💥😩🏃‍♂️💨，可用 🏠📍💰🇭🇰
- **排版**: 短段落（每段1-2句）、段间空行、可用小标题如"说一下租金"但不要"亮点1/亮点2"式编号
- **港式用词**: 呎、校网、平地电梯、走一层楼梯、唐楼、上车

### 标题
12-25字，大白话，疑问/感叹/数字钩子。

### 正文结构
- 第1句直接进场景/结论，不要"大家好我是XX"
- 中间3-5段自然带出细节（价格/面积/位置/装修/感受）
- 结尾自然互动提问（不是"私信我"）
- 正文 ≤ 400 字

### Output Format
严格 JSON，字段：`hook_title` / `main_content` / `interactive_question` / `seo_tags` / `image_suggestions` / `persona_note`
- `main_content` 换行用 `\n`
- `persona_note`：一句话说明本篇采用的素人子人设（如"港硕租房党，刚搬进学生公寓"）
- `image_suggestions`：3-6条，每条是"真实生活实拍"该拍什么（非信息图/海报）
- 只输出一个最终版本

---

## 参考范文库（Agent 2 教学产出）

- **来源**: Agent 2 对 `04_outputs/agent4_training_notes/`（10条已审核合格的真实素人爆款笔记）的拆解结果
- **位置**: `04_outputs/agent4_training/analyzed/*.json`（9条有效，1条因图片格式问题拆解失败为 `null`，已被 `load_reference_notes()` 自动跳过）
- **使用方式**: `build_user_prompt()` 每次随机抽取 3 条参考范文，提取其 `text_analysis.persona_perspective` / `hook_type` / `target_audience`、`visual_analysis.cover_style`、`text_analysis.conversion_strategy`、`reusable_template`（截断400字），拼入 user prompt 供模型学习结构和钩子手法（不要照抄措辞）

如需重新生成参考范文库（例如补充新的爆款笔记）：
```bash
# 1. 把新笔记目录拷贝到 04_outputs/agent4_training_notes/
# 2. 重新运行 Agent 2 拆解
python -m 02_Agent_Analyzer.analyzer --input-dir ../04_outputs/agent4_training_notes --output-dir ../04_outputs --run-id agent4_training
```

---

## CLI 使用

```bash
# 在 agent/ 目录下运行，需设置编码环境变量（Windows）
$env:PYTHONIOENCODING="utf-8"; $env:PYTHONLEGACYWINDOWSSTDIO="utf-8"

# 列出所有母题
python -m 04_Agent_AmateurViral.writer4 --list-categories

# 指定母题生成 1 篇
python -m 04_Agent_AmateurViral.writer4 --category 租房体验 -n 1

# 随机母题，生成 3 篇
python -m 04_Agent_AmateurViral.writer4 -n 3 --run-id 20260612_1600
```

### 参数
| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `--category` | str | None（随机） | `买房经历` / `租房体验` / `看房日记` / `生活分享` |
| `-n, --num` | int | 1 | 生成篇数 |
| `--run-id` | str | 自动生成 `YYYYmmdd_HHMM` | 管线运行时间戳 |
| `--list-categories` | flag | - | 列出母题后退出 |

### Python 调用
```python
from importlib import import_module
writer4 = import_module("04_Agent_AmateurViral.writer4")

results = writer4.run(category="买房经历", n=1, run_id="20260612_1600")
```

---

## 输出规范

- **草稿**: `04_outputs/{run_id}/drafts/draft_agent4_{category}_{timestamp}.json`（含完整 `NoteContent` + `_category`）
- **发布稿**: `04_outputs/{run_id}/pre-published/amateur_{category}_{title}_{timestamp}.md`
  - 包含标题、人设说明、正文、互动提问、SEO标签、配图建议（无封面图）

---

## 文件路径速查

| 用途 | 路径 |
|---|---|
| 核心生成脚本 | `agent/04_Agent_AmateurViral/writer4.py` |
| System Prompt | `agent/04_Agent_AmateurViral/system_prompt.txt` |
| 参考范文库（Agent2拆解产出） | `04_outputs/agent4_training/analyzed/*.json` |
| 训练素材原始笔记 | `04_outputs/agent4_training_notes/` |
| 输出草稿/发布稿 | `04_outputs/{run_id}/drafts/`, `04_outputs/{run_id}/pre-published/` |

---

## 与上下游的协作

```
Agent 1 (Hunter) → 爬取并筛选真实素人爆款笔记 → 01_materials/viral_examples/
       ↓
人工内容复核 → 挑选高质量素人视角笔记 → 04_outputs/agent4_training_notes/
       ↓
Agent 2 (Analyzer) → 拆解教学素材 → 04_outputs/agent4_training/analyzed/*.json
       ↓
Agent 4 (AmateurViral) → 学习拆解结果 + 母题模板 → 生成新的素人养号笔记
```

Agent 4 与 Agent 3 相互独立，共享 `shared/config.py` 的模型配置和 `_COMMON_RULES` 风格的写作约束，但服务于不同目的（养号 vs 房源营销）。
