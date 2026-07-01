# Agent 3 — 爆款图文生成器 (Writer)

## ⚠️ 强制红线：必须调用脚本，禁止手写模仿

**任何批量生成任务必须通过 subprocess 执行真实脚本，禁止自己手写文案来模仿 Agent3 的 persona 风格。**

```bash
python 03_Agent_Generator/writer.py --persona <agent|lean> --count N [--run-id ...]
```

手写内容绕过了 `writer.py` 内置的：
- 固定 system prompt（每个 persona 的人设、Hook Strategy、禁用词列表）
- 程序化输出校验 `_validate_note()`（标题长度 / 禁用词 / emoji数量 / CTA完整性 / lean 红线检查）
- 固定的 `HEAVY_MODEL` 调用（`shared/config.py` 里配置的模型，不是当前对话用的模型）

**例外**：用户明确要求"帮我手写/改写这一篇具体文案"（针对单篇已有内容的人工编辑，不是批量生成新内容）。

这条规则对所有编程助手生效（Claude Code、Codex、其他 agent 均适用）。

---

## 角色定位
基于房源生料 + SOP 爆款方法论 + 参考范文，生成去 AI 味的小红书香港房产图文笔记。支持多视角写作（素人 / 中介 / 极简中介），强制输出结构化 JSON，同时生成可直接发布的 Markdown 文件。

**v3.0**: 移除封面图生成、移除讨论帖 persona、移除策略文件落盘，新增程序化输出校验（`_validate_note()`）作为最后一道兜底关卡，不再完全依赖 system prompt 自律。

**核心设计原则：读着得像真人在小红书上写的，不能有 AI 味、不能有营销腔、不能有网感烂梗。**

---

## 核心配置

| 项目 | 值 |
|---|---|
| 模型 | `HEAVY_MODEL`（当前 `gemini-3.1-pro-preview`，定义在 `shared/config.py`） |
| 降级模型 | `gemini-3.1-flash-lite`（主模型多次失败/未通过校验后） |
| Temperature (写作) | 0.8（创意性写作） |
| Temperature (内部策略规划) | 0.5（需要更精准） |
| Max Tokens | 8192（写作）/ 4096（策略规划） |
| 最大重试 | 3 次 |
| SOP 路径 | `data_pipeline/stage2_parsed/爆款方法论_系统总结.md` |
| Agent 2 分析结果 | `04_outputs/{run_id}/analyzed/*.json` |
| 房源目录 | `01_materials/properties/` |
| 输出基础路径 | `04_outputs/` |

---

## 多视角配置 (Multi-Persona)

通过 `--persona` 参数切换三种写作视角：`amateur` / `agent` / `lean`。

### 三视角对比总览

| 维度 | amateur (素人) | agent (中介) | lean (极简中介) |
|---|---|---|---|
| **身份/人设** | 普通打工人，刚买房/在看房 | 无名字无背景故事，纯功能性中介 | 无名字无背景故事，纯功能性中介 |
| **内容形式** | 围绕一套房源的记录分享 | 推广房源，制造紧迫感 | 简洁客观，配表面痛点 |
| **正文长度** | ≤400 字 | ≤400 字 | ≤300 字 |
| **目的** | 记录、分享、共鸣 | 获客、引导评论/私信 | 获客，但语气更克制真实 |
| **CTA** | 软性引导 | "想看详细资料或拿钥匙看房的，在评论区打PM我给您发这套房子的资料" | 必须完整可读，如"评论PM我给您发资料"，禁止裸写"评论PM" |
| **使用场景** | 素人号日常更新 | 中介号/蓝V号推广 | 中介号推广，更克制不浮夸 |

### Persona: amateur（素人看房/买房记录，默认）

- **身份**: 普通香港上班族，刚买房或正在看房，不是中介、不是 KOL
- **场景**: 下班瘫在沙发上打开小红书记录看房/买房经历
- **语气**: 松弛、有情绪、像发朋友圈，没有推销感
- **用词**: 以"我"开头讲故事，用"你"共情读者
- **允许**: 客观吐槽（走楼梯累、面积小、装修旧），纠结、踩坑经历
- **标题风格**: 多用情绪词和生活感——"终于上车了""看房半年后的决定""值了""这个预算我尽力了"
- **核心区别**: 写东西是为了**记录分享**，不是为了卖房
- **禁止词同共有硬约束**
- **Emoji**: 整篇最多 3-4 个，可用 📍💰💎 标注卖点

### Persona: agent（中介推广获客）

- **身份**: 一名香港地产中介，**没有名字、没有背景故事**，只是在做这份工作、对房源信息有专业和信息差优势的人
- **语气**: 直接自信，但不夸张，像在用手机给客户发消息介绍房源
- **用词**: 直接亮卖点，敢于说"这个价在港岛核心区真找不出第二套""我手上已经有几组客正在约看"
- **核心区别**: 每个信息点都有目的——要么是卖点，要么是**制造紧迫感**
- **CTA**: 固定写为"想看详细资料或拿钥匙看房的，在评论区打PM我给您发这套房子的资料"，绝不能说"私信我"或"直接私信我"
- **人群定位**: 每篇先从 4 类人群（大陆投资型买家/大陆家庭买家/港漂上车客/跨境自住客）中锁定一类，全篇只对这类人说话
- **风险必写**: 每篇至少点出一个真实风险（楼龄/维修、估价差距、按揭年期、租务空置、政策变化、装修成本）
- **标题候选**: 输出 6 个候选标题，覆盖数字锚定/身份代入/风险提醒 3 类触发器，每类至少 2 个，最终选 1 个写入 `hook_title`，其余写入 `title_candidates`
- **禁止词 + Emoji 同共有硬约束**

### Persona: lean（极简中介，简洁客观）

- **身份**: 同 agent——一名香港地产中介，**没有名字、没有背景故事**
- **语气**: 简洁但不生硬，用"实话讲""老实说""有一说一"这类口语连接词，让文字有呼吸感，**不能写成参数清单**
- **正文结构**: 标题(12-16字纯干货) → 第1段亮房源+价格 → 第2段具体参数 → 第3段小缺点+转折 → 第4段紧迫感+CTA，全文 200-280 字左右，硬上限 300 字
- **缺点白名单**（只能说这些无关痛痒的表面问题）: 大厦大堂旧式、电梯间不光鲜、厨房传统梗厨非开放式、楼下街景旧、管理费比旧楼高、望街景非海景、要上一层楼梯、单幢楼没会所
- **缺点黑名单（致命伤，绝对禁止当缺点说）**: 楼龄/楼龄数字、面积小/户型大小、按揭做不足、银行估不到价
- **绝对禁止**: 任何装修风格描述（大理石、轻奢、奶油风、ins风、杂志风）、情绪化感叹（"看哭了""太震撼了"）
- **CTA 硬规则**: 必须完整可读，统一写"评论PM我给您发资料"或"想看资料的评论PM"，**禁止只写"评论PM"两三个字**——这条由 `_validate_note()` 程序化校验，不只靠 prompt 自律

### 共用硬约束（三个 persona 都遵守）

**绝对不能出现的词:**
`家人们` `谁懂啊` `绝绝子` `宝子们` `神仙` `笋盘`（用"抵买"代替）`宝藏楼盘` `绝了` `冲它` `太香了` `手慢无` `YYDS` `天花板` `闭眼入` `真香` `宝藏` `必入` `姐妹们` `谁懂` `宝藏小区` `梦中情房`

**禁止浮夸 emoji**: `🔥💥😩🏃‍♂️💨`；全篇 emoji 总数硬上限 5 个（留 1 个容差防止误杀旗帜符号）

**距离/时间准确性硬规则:**
- `mtr_walk_min` 是**步行到地铁站的分钟数**，不是通勤到公司的时间。不准写"通勤 X 分钟""地铁 X 分钟"，只能写"步行 X 分钟到 XX 地铁站"。
- 严格使用房源数据中 `mtr_walk_min` 的值，禁止自行估算或四舍五入。
- `mtr_walk_min: 0` 或缺失时 → 不准提具体分钟数，改用模糊表述"近地铁""步行可达"。
- 绝对禁止"地铁0分钟""出门就是地铁"等不合常理的表述。
- `500m` 等距离数据 → 按 80m/min 折算为步行分钟数（如 500m → 步行6分钟）。

> 以上规则不再只靠 system prompt 自律——`_validate_note()` 会在生成后逐条程序化校验，违规自动触发重试（见下方「输出校验」章节）。

---

## Hook Strategy（房源类型 → 标题+留白策略）

拿到房源数据后，先判断属于哪种类型，再按对应策略写（每条只写一个角度，不输出多版本）：

### 类型 A：海景 + 性价比
- **标题**: 海景 + 价格，例「铜锣湾两房 海景 530万」
- **正文重点**: 窗外景观、采光、通风
- **刻意隐藏**: 楼盘名
- **互动钩子**: 引导评论问具体位置

### 类型 B：绝对低价
- **标题**: 主打价格，例「湾仔 250万 一房 港岛这个价不多见了」
- **正文重点**: 上车门槛低、月供比租金便宜、地段保值
- **刻意隐藏**: 楼盘名
- **互动钩子**: 引导评论问具体位置

### 类型 C：装修好 / 图片好看
- **标题**: 装修或居住感，例「刚装修完 湾仔一房 看了就搬」
- **正文重点**: 空间感、装修细节、住进去的感受
- **刻意隐藏**: 价格或面积（二选一）
- **互动钩子**: 引导评论问价或详情

### 类型 D：校网刚需
- **标题**: 校网 + 房型，例「12校网 湾仔两房 适合带小朋友」
- **正文重点**: 接送方便、周边环境、社区安全
- **刻意隐藏**: 楼盘名
- **互动钩子**: 引导评论问具体位置

---

## 内部策略规划（不落盘，仅指导创作）

**设计目的**: 在正式创作之前，先通过 LLM 做行文思路规划，避免盲目生成。确保每篇笔记都有明确的客群目标、爆款参照、钩子设计和留白策略。

**v3.0 变更**: 规划结果**不再保存为独立文件**（`save_strategy()` 已删除）。LLM 仍会输出结构化的 Markdown 规划文本，但这份文本只会被截取前 3000 字塞进创作 prompt 的「行文思路规划」上下文，写完笔记后即丢弃，不对外暴露、不落盘。

### 策略规划流程

1. **加载人群包**: `load_audience_segments()` 从 `爆款方法论_系统总结.md` 中提取「三、客群精准对位」和「五、可复用爆款模板库」两个章节
2. **加载 Agent 2 分析笔记**: `load_analyzed_notes(run_id)` 优先从当前 run 的 `analyzed/` 目录加载，其次扫描历史 `04_outputs/*/analyzed/`，最后回退到 `stage2_parsed` 子目录
3. **构建策略 Prompt**: `build_strategy_prompt(property_data, audience_segments, analyzed_notes, persona)`
4. **调用 LLM 生成思路**: `call_llm_strategy(strategy_prompt)` — 使用主模型 temperature=0.5，带重试和降级
5. **直接传入创作 prompt**: 规划结果通过 `build_user_prompt(strategy_md=...)` 注入创作上下文，不调用任何保存函数

### 策略规划输出结构（仅用于指导创作，不保存）

LLM 按以下 Markdown 格式输出行文思路：一、目标人群锁定 → 二、爆款参照（须写明 Agent2 分析文件名+绝对路径+原文链接）→ 三、钩子设计 → 四、留白设计 → 五、私信引导（CTA）设计 → 六、正文大纲。

### 跳过策略规划

通过 `--skip-strategy` 参数或 `skip_strategy=True` 可跳过这一步，直接进入内容创作（更快，但创作时缺少人群/钩子的前置规划）。

---

## 正文结构规范

| 段落位置 | 内容要求 |
|---|---|
| 第 1 行 | 一句话开头。痛点/场景/直接说事都可，**不要长篇铺垫** |
| 中间 3-6 段 | 自然短段落，每段一两句话。聊空间、采光、位置、月供、装修，想到哪写到哪。把硬参数（呎数、价格、楼层、地铁分钟数）**自然揉进去**，不列清单 |
| 倒数第 2 段 | 制造**真实紧迫感**——不说"手慢无"，而是用具体事实：「租客下周搬走」「业主想快点放」「前两天有人看了说考虑中」 |
| 最后 1 段 | 互动钩子，自然随口一问，不要太客气、不要太营销腔 |

**标题**: 12-20 字，严格 ≤20 字，大白话，必须包含一个钩子元素（价格/海景/校网/装修）。
**SEO 标签**: 5-10 个，覆盖地名+房型+话题，例如 `#香港买房 #湾仔 #十二校网`

### 发布稿素材引用规范（save_pre_published 自动拼接）

`save_pre_published()` 在将 LLM 生成的正文 + SEO 标签写入文件后，自动在 Markdown 末尾追加「📁 关联素材」章节（只含本房源素材 + 参考爆款笔记两部分，**不再有封面图、不再有行文思路链接**）：

```markdown
---

## 📁 关联素材（Ctrl+点击跳转）

### 本房源素材
- **房源信息**: [查看 info.md](..\..\..\01_materials\properties\{name}\info.md)
- **房源图片** ({count} 张):
  - [微信图片_01.jpg](..\..\..\01_materials\properties\{name}\微信图片_01.jpg)
  - ...

### 参考爆款笔记
- **Agent2 分析**: [{filename}](..\..\..\04_outputs\{run_id}\analyzed\{filename})
- **小红书原文**: [{title}]({note_url})
```

> 此章节由 `_build_source_refs_section()` 从 `property_data` 中提取路径自动生成，LLM 不需要输出此部分。所有本地路径用 `os.path.relpath()` 转为相对路径，跨盘符回退绝对路径。

---

## 输出校验（v3.0 新增，最重要的稳定性改动）

**背景**: 在此之前，所有写作规则（禁用词、标题长度、emoji数量、CTA完整性、致命伤红线）全部只活在 system prompt 文本里，模型输出违规内容也会被原样接受、原样存盘——这是输出风格不稳定、容易"受调用环境影响漂移"的根本原因。

**解决方式**: `_validate_note(content, persona)` 在 `_parse_response()` 解析出 `NoteContent` 之后立即跑一遍程序化校验，返回违规说明列表（空列表 = 通过）。校验项：

| 校验项 | 规则 | 适用范围 |
|---|---|---|
| 标题长度 | 必须非空且 ≤20 字 | 全部 persona |
| 禁用词 | 命中 `_BANNED_WORDS` 列表中任意词 | 全部 persona |
| 禁用 emoji | 命中 🔥💥😩🏃‍♂️💨 | 全部 persona |
| emoji 总数 | 通过 `_count_emoji()` 统计非 BMP 字符 + 常见符号区间，上限 5 个 | 全部 persona |
| 正文长度 | lean ≤300 字，其余 ≤400 字 | 全部 persona |
| 距离/时间表述 | 命中"地铁0分钟"/"出门就是地铁"/"通勤X分钟" | 全部 persona |
| CTA 完整性 | 命中孤立的"评论PM"（前后无更多文字） | 全部 persona |
| 装修风格词 | 命中"大理石/轻奢/奶油风/ins风/杂志风" | 仅 lean |
| 致命伤缺点 | 命中"楼龄+数字""面积小/户型小""按揭不足""银行估价跟不上" | 仅 lean |

**触发逻辑（`call_llm()` 内部）**:
1. 主模型最多重试 `MAX_RETRIES`（3）次，每次生成后跑校验；只要有一次通过就立即返回。
2. 主模型重试耗尽仍未通过 → 降级到 `gemini-3.1-flash-lite` 再试一次。
3. 降级模型也未通过 → **按容错策略返回最后一次结果**（带瑕疵但不让整个管线崩溃），同时用 `logger.error` 显著打出未通过的具体原因，方便事后排查，而不是静默接受。

这套校验是规则的**最后一道关卡**，不依赖任何特定 LLM 模型是否"听话"——即便换一个完全不同的模型来跑 `call_llm()`，违反硬约束的输出也会被拦下来重试，而不是被无声地保存发布。

---

## 真实房源加载器

### 数据来源
`01_materials/properties/` 下的每个子目录代表一条房源，包含：
- `info.md` — 非结构化房源信息（面积、价格、楼层、电梯、地铁、校网等）
- 房源实拍图片（2-22 张，jpg/jpeg/png）

### info.md 解析规则
`_parse_info_md()` 从 info.md 提取结构化字段：`rooms`、`price_wan`、`area_sqft`/`area_gross_sqft`、`has_lift`/`lift_type`、`school_net`/`school_net_name`、`mtr_station`/`mtr_walk_min`、`district`/`sub_district`、`building_name`、`highlights`、`images_count`、`info_md_path`、`property_dir`、`images`。

### 加载函数
- `load_properties_from_dir(shuffle=True)` — 扫描全部房源，随机打乱
- `_pick_properties(count=3)` — 随机选 N 套，不够时用 mock 补足
- `load_analyzed_notes(run_id)` — 加载 Agent 2 分析笔记

---

## CLI 参数

```
python writer.py [options]
```

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `--persona` | `amateur\|agent\|lean` | `amateur` | 写作视角 |
| `--count` | int | 1 | 生成篇数，随机选 N 套房源 |
| `--output-dir` | Path | `04_outputs/` | 输出基础路径 |
| `--property-dir` | Path | `01_materials/properties/` | 房源目录 |
| `--run-id` | str | 自动生成 | 管线运行时间戳 (YYYYmmdd_HHMM) |
| `--skip-strategy` | flag | false | 跳过内部策略规划阶段，直接创作 |

示例：
```bash
# 素人视角生成 3 篇
python writer.py --persona amateur --count 3

# 中介视角生成 1 篇，指定运行 ID
python writer.py --persona agent --run-id 20260521_1500

# 极简中介视角，跳过策略规划（快速模式）
python writer.py --persona lean --count 3 --skip-strategy
```

---

## 输出 Schema

### JSON 草稿 (NoteContent)
```json
{
  "hook_title": "湾仔250万正规一房 港岛核心区这个价不多见",
  "title_candidates": ["...", "..."],
  "main_content": "分段口语正文，\\n 表示换行...",
  "interactive_question": "要不要先看看户型图？",
  "seo_tags": ["香港买房", "湾仔", "香港上车盘"],
  "persona_note": "港漂上车客"
}
```

### 输出路径规则
```
{output_dir}/{run_id}/
  drafts/
    draft_{persona}_{timestamp}.json    ← LLM 原始输出（已通过校验）
  pre-published/
    {property_name}_{persona}.md        ← 可直接发布的图文 Markdown
```

- `run_id` 由 `get_run_id()` 自动生成（香港时间 YYYYmmdd_HHMMSS），或通过 `--run-id` 手动指定
- `property_name` 经过 `sanitize_filename()` 安全化处理
- 不再生成 `_strategy.md`、`_cover.png`、`_cover_原图.*`——这些产物已随 v3.0 重构移除

---

## LLM 调用与容错

1. **主调用**: 使用 `HEAVY_MODEL`，temperature=0.8，max_tokens=8192
2. **重试**: 最多 3 次；JSON 解析失败或**程序化校验未通过**均视为可恢复失败，触发重试
3. **降级**: 3 次均失败/未通过校验时自动切换 `gemini-3.1-flash-lite` 试一次
4. **JSON 解析**: 自动剥离 markdown 代码块包裹，支持正则兜底提取 + 截断修复（补全未闭合引号/括号）
5. **JSON 字段容错**: LLM 返回多余字段时静默忽略，只提取 schema 定义的字段
6. **最终容错**: 即便重试和降级都未通过校验，仍返回最后一次结果（不让管线崩溃），但用 `logger.error` 显著标出违规详情

---

## 数据流

```
01_materials/properties/*/info.md              ← 真实房源生料
        │
        ▼
  _parse_info_md() → dict                      ← 结构化房源数据
        │
        ▼
  ═══════════ 阶段 1: 内部策略规划（不落盘）═══════════
        │
        ├─ load_audience_segments()            ← 人群包 + 模板库
        ├─ load_analyzed_notes()                ← Agent 2 拆解笔记
        ├─ build_strategy_prompt()
        └─ call_llm_strategy()                  ← LLM (temp=0.5)，结果只存内存
        │
  ═══════════ 阶段 2: 笔记创作 + 程序化校验 ═══════════
        │
        ├─ build_user_prompt(strategy_md)      ← SOP + 范文 + 房源 + 内部思路
        ├─ call_llm(user_prompt, persona)      ← LLM (temp=0.8)
        │       ├─ _parse_response()           ← 解析 JSON
        │       ├─ _validate_note()            ← 程序化校验，不过则重试/降级
        │       ├─ save_draft() → JSON 草稿     ← {run_id}/drafts/
        │       └─ save_pre_published() → .md  ← {run_id}/pre-published/
        │              └─ 自动拼接 📁关联素材
        ▼
    最终输出: JSON draft + 发布.md（含相对路径素材链接）
```

`--skip-strategy` 参数可跳过阶段 1。

---

## 文件路径速查

| 用途 | 路径 |
|---|---|
| 主脚本 | `agent/03_Agent_Generator/writer.py` |
| SOP 方法论 | `data_pipeline/stage2_parsed/爆款方法论_系统总结.md` |
| Agent 2 分析结果 | `04_outputs/{run_id}/analyzed/*.json` |
| 房源目录 | `01_materials/properties/` |
| 默认输出 | `04_outputs/{run_id}/drafts/` + `04_outputs/{run_id}/pre-published/` |
| 共享配置 | `agent/shared/config.py` |
| 系统 Prompt | 内嵌在 writer.py 的 `SYSTEM_PROMPT_AMATEUR` / `SYSTEM_PROMPT_AGENT` / `SYSTEM_PROMPT_LEAN_AGENT` |
| 校验函数 | `_validate_note()`、`_count_emoji()` |
| 策略规划函数 | `load_audience_segments()`, `load_analyzed_notes()`, `build_strategy_prompt()`, `call_llm_strategy()` |

---

## 关键设计决策与避坑

1. **去 AI 味是最高优先级**。宁可句子不完整、语法不规范，也绝不能像 ChatGPT 写的。
2. **三个 Persona 的本质差异在视角和克制程度，不在格式**。amateur 是 buyer 视角（记录/共情/吐槽）；agent 是 seller 视角（信息差/稀缺性/紧迫感）；lean 也是 seller 视角但更克制简洁、配真实表面痛点。三者都**没有虚构的人物名字或背景故事**——之前的"阿明，8年经验"设定已移除，因为给中介加戏会让输出更不可控、更容易被识破是 AI 生成。
3. **留白策略是转化核心**。每种房源类型都必须刻意隐藏至少一个关键信息（楼盘名/价格/面积），这是引导用户评论或私信的核心机制。
4. **真实紧迫感 > 虚假紧迫感**。用「前两天有人看了说考虑中」「租客下周搬走」这类具体事实制造紧迫感，禁止用「手慢无」这类 AI 味浓厚的虚假话术。
5. **info.md 解析要容错**。不同房产中介写的 info.md 格式差异大，正则匹配要宽松，关键字段缺失时用 fallback 值。
6. **模型选型**。生成任务用 `HEAVY_MODEL`，API 过载时降级到 `gemini-3.1-flash-lite`。
7. **内部策略规划先于创作，但不落盘**。先让 LLM 完成客群锁定 → 爆款参照 → 钩子/留白/CTA 设计 → 正文大纲，再把这份思路传入创作 prompt 约束生成方向，比直接让 LLM 自由发挥质量更高。但规划结果只是过程产物，不对外暴露——发布目录里不应该出现 `_strategy.md`。
8. **素材路径由代码自动拼接，LLM 不参与**。`_build_source_refs_section()` 从 `property_data` 字典中提取路径自动拼接相对路径，LLM 不知道文件系统路径，不能让它生成。
9. **程序化校验是稳定性的核心机制（v3.0 新增）**。System prompt 写得再细，LLM 仍可能在某次调用中跑偏——尤其是当上层调用者（其他编程助手/不同模型）绕过标准 `run()` 流程、自己拼 prompt 调用时。`_validate_note()` 把硬性规则从"纯靠模型自律"升级成"代码兜底强制"：标题长度、禁用词、emoji数量、CTA完整性、lean的致命伤红线，全部在输出落盘前做一次机械检查，不通过就重试或降级，而不是默默接受走样的内容。这是回应"Agent3 输出不稳定、受调用环境影响"问题的关键修复——校验逻辑和调用的是哪个模型、被谁调用完全无关，任何模型生成的内容都要过这一关。
10. **封面图生成、讨论帖 persona、策略文件落盘三项功能已在 v3.0 完全移除**。如果在旧文档、旧脚本或旧记忆中看到 `generate_cover()`、`_build_discussion_prompt()`、`save_strategy()`、`--skip-cover`、`--persona discussion` 等引用，那些已经是过时信息——当前代码库里这些符号都不存在了。`agent/scratch/` 目录下一些历史一次性脚本仍引用这些已删除的函数，那些脚本本身已不可运行，但不影响 `writer.py` 主流程。
