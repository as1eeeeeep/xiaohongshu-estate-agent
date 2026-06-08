# Agent 3 — 爆款图文生成器 (Writer)

## 角色定位
基于房源生料 + SOP 爆款方法论 + 参考范文，生成去 AI 味的小红书香港房产图文笔记。支持多视角写作（素人 vs 中介），强制输出结构化 JSON，同时生成可直接发布的 Markdown 文件。

**v2.0 新功能**: 自动从房源图片中识别客厅照片，用 Gemini 原生图像生成 API 生成小红书封面图。

**核心设计原则：读着得像真人在小红书上写的，不能有 AI 味、不能有营销腔、不能有网感烂梗。**

---

## 核心配置

| 项目 | 值 |
|---|---|
| 模型 | `HEAVY_MODEL`（当前 `gemini-3.1-pro-preview`） |
| 降级模型 | `gemini-3.1-flash-lite`（主模型 3 次失败后） |
| 封面图模型 | `gemini-2.5-flash-image`（Gemini 原生图像生成 API） |
| 封面图 API | `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` |
| Temperature (写作) | 0.8（创意性写作） |
| Temperature (策略规划) | 0.5（策略规划需要更精准） |
| Temperature (封面图) | 0.7（保持真实感 + 适度创意） |
| Max Tokens | 4096 |
| 最大重试 | 3 次 |
| SOP 路径 | `data_pipeline/stage2_parsed/爆款方法论_系统总结.md` |
| Agent 2 分析结果 | `04_outputs/{run_id}/analyzed/*.json` |
| 房源目录 | `01_materials/properties/` |
| 输出基础路径 | `04_outputs/` |

---

## 多视角配置 (Multi-Persona)

通过 `--persona` 参数切换三种写作视角。三种视角的定位、流程和硬约束各不相同。

### 三视角对比总览

| 维度 | amateur (素人) | agent (中介) | discussion (讨论帖) |
|---|---|---|---|
| **需要房源数据?** | ✅ 是 | ✅ 是 | ❌ 不需要 |
| **生成封面图?** | ✅ 是 | ✅ 是 | ❌ 跳过 |
| **策略规划?** | ✅ 是 | ✅ 是 | ❌ 跳过 |
| **内容形式** | 围绕一套房源的记录分享 | 推广房源，制造紧迫感 | 抛话题/讲经历/晒账本 |
| **目的** | 记录、分享、共鸣 | 获客、引导私信 | 激起评论区讨论 |
| **引导私信?** | 软性引导 | 直接引导 | ❌ 不引导 |
| **使用场景** | 素人号日常更新 | 中介号/蓝V号推广 | 素人号养号引流 |

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
- **排版**: 允许简短结构化分段，但要自然

### Persona: agent（中介推广获客）

- **身份**: 阿明，香港做了 8 年地产，专做港岛二手盘
- **场景**: 站在铜锣湾街头，刚带完客看房，趁等红灯用手机备忘录敲笔记
- **语气**: 高效、自信、有信息差优势，像在 WhatsApp 给熟客发消息
- **用词**: 直接亮卖点，敢于说"这个价在湾仔买三房不多""我手上已经有几组在看"
- **标题风格**: 信息密度高，直接亮核心卖点——"12校网 铜锣湾三房 465万""湾仔一房 海景 实际300多呎"
- **核心区别**: 每个信息点都有目的——要么是卖点，要么是**制造紧迫感**
- **CTA**: 直接引导私信——"想看具体资料的，直接私信我"
- **禁止词 + Emoji + 排版同 amateur**

### Persona: discussion（纯讨论帖，激起评论）

- **身份**: 在香港生活了 5 年的普通打工人，打开小红书纯粹想聊聊天
- **场景**: 不介绍房源——抛话题、讲经历、摆观点、晒账本
- **语气**: 像在和朋友喝酒聊天，可以有情绪（后悔/庆幸/纠结/自嘲）
- **允许**: 争议性观点——"租房比买房划算""港岛旧楼不值得""上车后我后悔了"
- **标题**: 12-30 字，要有话题感让人想点进来，例如：
  - 「算了一笔账，在香港租房比买房划算多了」
  - 「月薪 4 万，在香港买房还是太勉强了」
  - 「看了 50 套房，我说点中介不会告诉你的」
  - 「上车一年后的真实账本：月供比你想象的可怕」
- **正文结构**: 第一段直接亮观点 → 中间用数据和亲身经历支撑 → 结尾抛开放式问题
- **禁止词**: 同 amateur + **严禁引导私信、严禁介绍具体房源**
- **Emoji**: 最多 2-3 个，不禁用结构化符号
- **不需要房源数据**，`run()` 检测到 discussion 模式自动跳过封面生成和策略规划

### 共用硬约束（amateur / agent 遵守，discussion 部分适用）

**绝对不能出现的词（所有 persona）:**
`家人们` `谁懂啊` `绝绝子` `宝子们` `神仙` `笋盘`（用"抵买"代替）`宝藏楼盘` `绝了` `冲它` `太香了` `手慢无` `YYDS` `天花板` `闭眼入` `真香` `宝藏` `必入` `姐妹们` `谁懂` `宝藏小区` `梦中情房`

**所有 persona 禁止浮夸 emoji**: `🔥💥😩🏃‍♂️💨`

**距离/时间准确性硬规则（amateur / agent，discussion 不适用）:**
- `mtr_walk_min` 是**步行到地铁站的分钟数**，不是通勤到公司的时间。不准写"通勤 X 分钟""地铁 X 分钟"，只能写"步行 X 分钟到 XX 地铁站"。
- 严格使用房源数据中 `mtr_walk_min` 的值，禁止自行估算或四舍五入。
- `mtr_walk_min: 0` 或缺失时 → 不准提具体分钟数，改用模糊表述"近地铁""步行可达"。
- 绝对禁止"地铁0分钟""出门就是地铁"等不合常理的表述。
- `500m` 等距离数据 → 按 80m/min 折算为步行分钟数（如 500m → 步行6分钟）。

---

## Hook Strategy（房源类型 → 标题+留白策略）

> 注意：Hook Strategy 仅适用于 amateur 和 agent。discussion 模式有自己的话题库（见 `_build_discussion_prompt()`）。

拿到房源数据后，先判断属于哪种类型，再按对应策略写：

### 类型 A：海景 + 性价比
- **标题**: 海景 + 价格，例「铜锣湾两房 海景 530万」
- **正文重点**: 窗外景观、采光、通风
- **刻意隐藏**: 楼盘名（不提大厦名称）
- **互动钩子**: 「哪个盘？」引导评论问

### 类型 B：绝对低价
- **标题**: 主打价格，例「湾仔 250万 一房 港岛这个价不多见了」
- **正文重点**: 上车门槛低、月供比租金便宜
- **刻意隐藏**: 楼盘名
- **互动钩子**: 引导私信问具体位置

### 类型 C：装修好 / 图片好看
- **标题**: 装修或居住感，例「刚装修完 湾仔一房 看了就搬」
- **正文重点**: 空间感、装修细节、住进去的感受
- **刻意隐藏**: 价格或面积（二选一）
- **互动钩子**: 引导评论问价

### 类型 D：校网刚需
- **标题**: 校网 + 房型，例「12校网 湾仔两房 适合带小朋友」
- **正文重点**: 接送方便、周边环境、社区安全
- **刻意隐藏**: 楼盘名
- **互动钩子**: 引导私信问具体位置

---

## 封面图生成（Phase 0，v2.0 核心升级）

在策略规划之前自动运行，从房源素材中找客厅照片 → 用 Gemini 原生图像生成 API 生成精致封面图。

### 设计目标（来自用户反馈迭代）

| 要求 | 实现方式 |
|---|---|
| **不能太假** | System Prompt 硬约束："MUST look like a real photograph, NOT 3D render/CGI/AI art"；保持原墙色、地板、窗户、家具布局 |
| **精致有点击欲** | 杂志级摄影风格：暖金色调、柔光、空间纵深、胶卷调色；按房价分 4 档定位（luxury / aspirational / cozy / cheerful） |
| **不能有字** | System Prompt 第一条禁令："ABSOLUTELY NO text, words, characters, numbers, watermarks, or labels" |
| **不能太多盆栽** | 硬限制 "at most ONE small potted plant, the room is NOT a greenhouse" |
| **换个视角** | 允许微调相机角度来更好展示**已可见**的空间——但不能扩展超出原图能证明的范围。只展示原照拍到的东西 |
| **🚫 绝对不能改变面积/户型** 🔴 | **红线规则 #0**：平方呎、地板面积、房间尺寸、天花高度全部固定。可以微调相机角度，但房间大小必须和原图一模一样。原图只拍到客厅一角 → 只呈现那一角，不能凭空造出其他空间。**宁愿不换视角也不能让房间变大** |
| **真实感优先** | 不做家具替换、不加假窗假景、不改变原始户型——只是摄影增强 |

### 封面图风格标准（V2 杂志风）

封面图被定义为 **"top-tier architectural and real estate photographer for luxury property magazines"**，具体风格指南内嵌在 `_COVER_SYSTEM_PROMPT` 中：

**光线 & 氛围**
- 暖调自然日光 — 像金色时刻的阳光透过薄纱窗帘漫入
- 柔和的阴影增加深度，不刺眼不平光
- 偏暖色温 — 微琥珀/金色调让空间温暖舒适

**构图 & 透视**
- 微调相机角度，更好地呈现**原图已拍到的**空间 —— 不扩展、不推墙、不加面
- 自然视角（眼平或略高），像你站在房间里同一个位置拍照
- 利用原图中已有的前景（地板、家具边缘）→ 中景（沙发/座位区）→ 背景（可见的窗或门）营造纵深感
- 🚫 不能通过透视手段让房间看起来比实际大——面积是固定的，不能改变

**色彩 & 后期**
- 胶卷质感的调色：微褪绿和蓝、暖白、自然木色
- 干净的暖偏向白平衡
- 柔和的对比曲线 — 不压死黑、不爆白
- 允许微妙的暗角引导视觉焦点

**布景 & 整洁度**
- 去除视觉噪音（杂物、线缆、零乱物品），但保持生活气息
- 台面干净整齐
- 最多一两处装饰点缀 — 不加假道具

### Prompt 两层架构

**第一层：System Prompt（`_COVER_SYSTEM_PROMPT`）**
- 定义摄影师的风格身份和完整风格指南
- 适用于所有房源，不变

**第二层：动态 Prompt（`_build_cover_prompt()`）**
- 根据房源具体参数动态构建
- 按房价分 4 档，自动设定风格定位词：

| 价格档位 | 定位 | 氛围关键词 |
|---|---|---|
| ≥ 900 万 | "premium luxury apartment" | understated luxury — quality speaks through space |
| 600-899 万 | "high-quality comfortable home" | warm and aspirational — bookmark as goal |
| 400-599 万 | "solid well-located apartment" | cozy and inviting — practical but charming |
| < 400 万 | "well-priced desirable apartment" | bright and cheerful — compact but full of potential |

- 自动注入装修加分："recently renovated with fresh finishes — make clean surfaces shine"
- 自动注入亮点提炼："Notable features: 交通方便, 管理完善"

### 封面图生成流程

1. **找客厅**: `_find_living_room_image(images, api_key)` 
   - 通过 `VISION_MODEL`（OpenAI 兼容 API）一次性发送最多 8 张房源图片
   - 判断标准：有沙发/茶几/电视柜、客厅布局才算，卧室/厨房/卫生间/走廊都不算
   - 返回客厅图片路径 + 置信度（high/medium/low）
   - 失败时降级取第一张图

2. **构建 Prompt**: `_build_cover_prompt(property_data)`
   - 按价格档位自动确定风格定位词和氛围描述
   - 拼接装修状态、亮点标签等上下文信息
   - 全英文 —— 图像模型对英文指令的理解和遵循度远优于中文

3. **调用生成**: `_call_gemini_image_gen(image_path, prompt, api_key)`
   - System Prompt + 动态 Prompt 合并作为最终文本指令
   - 使用 `gemini-2.5-flash-image` 模型（原生 Gemini API，非 OpenAI 兼容端点）
   - API: `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
   - `responseModalities: ["IMAGE", "TEXT"]` — 图像+文本双模态输出
   - 输入：客厅照片 (base64 inlineData) + 文本 prompt
   - 输出：生成的封面图 PNG bytes（从响应的 inlineData 中提取）
   - Temperature 0.7，超时 120s，重试 2 次

4. **保存**: `generate_cover()` → 输出两个文件到 `{run_id}/pre-published/`：
   - `{property_name}_cover.png` — AI 生成的封面图
   - `{property_name}_cover_原图.jpg` — 封面素材原图（客厅照片的副本，记录封面是用哪张图做的）
   - 笔记 Markdown 的 `🎨 AI 生成封面图` 章节会自动列出封面图 + 素材原图两项链接

### 🔍 素材来源可追溯（必须）

**每次生成封面图，必须在输出目录同时保存一份素材原图的副本。** 这不是可选的——发布者需要知道封面图是用哪张房源照片生成的，方便核对真实性和替换。

- 代码实现：`generate_cover()` 在保存封面后，用 `shutil.copy2()` 把客厅原图复制到同一个目录，命名为 `{property_name}_cover_原图.{ext}`
- `_build_source_refs_section()` 在构建 Markdown 素材章节时，自动探测同名的 `_cover_原图.*` 文件并生成链接
- Markdown 中会显示：
  ```
  ### 🎨 AI 生成封面图
  - [查看封面图](xxx_cover.png)
  - **封面素材原图**: [xxx_cover_原图.jpg](xxx_cover_原图.jpg)
  ```

### ⚠️ 输出位置硬性规范（必须遵守）

**封面图和笔记文案必须输出到同一个目录。** 两者都是同一次管线运行的产物，必须放在同一个 `{run_id}/pre-published/` 下，方便发布时一次性找到所有素材。

- `run()` 函数会自动保证这一点：`generate_cover()` 和 `save_pre_published()` 都写入 `{output_dir}/{run_id}/pre-published/`
- **禁止**为封面图单独创建 `run_id` 或输出到不同子目录
- **禁止**写临时测试脚本用不同的 `run_id` 分别跑封面和文案——始终用 `run()` 一次跑完，或至少确保 `run_id` 相同
- 测试封面效果时，用相同的 `run_id` 调用 `generate_cover()` 和 `save_pre_published()`

```
✅ 正确结构：
{run_id}/pre-published/
  {property_name}_{persona}.md          ← 笔记文案
  {property_name}_{persona}_strategy.md ← 策略思路
  {property_name}_cover.png             ← 封面图

❌ 错误结构（封面和文案分离）：
{runa_id}/pre-published/{name}.md
{runb_id}/pre-published/{name}_cover.png   ← 找不到对应关系
```

### 容错设计
- 封面图生成失败**不影响笔记生成**——封面是锦上添花，笔记正文是核心
- 无图片的房源自动跳过
- 客厅识别失败 → 降级取第一张
- API 超时/失败 → 重试，最终失败静默跳过
- `--skip-cover` 可完全禁用，回退到纯文本模式

---

## 策略规划阶段（写前构思，两阶段管线 Phase 1）

**设计目的**: 在正式创作之前，先通过 LLM 做行文思路规划，避免盲目生成。确保每篇笔记都有明确的客群目标、爆款参照、钩子设计和留白策略。

### 策略规划流程

1. **加载人群包**: `load_audience_segments()` 从 `爆款方法论_系统总结.md` 中提取「三、客群精准对位」和「五、可复用爆款模板库」两个章节
2. **加载 Agent 2 分析笔记**: `load_analyzed_notes(run_id)` 优先从当前 run 的 `analyzed/` 目录加载，其次扫描历史 `04_outputs/*/analyzed/`，最后回退到 `stage2_parsed` 子目录
3. **构建策略 Prompt**: `build_strategy_prompt(property_data, audience_segments, analyzed_notes, persona)` 将房源数据 + 人群包 + 爆款分析 + 写作视角拼接，**每条分析笔记携带：`source_file`（Agent2 分析 JSON 文件名）、`source_absolute_path`（Agent2 分析 JSON 的绝对路径——内部存储用，`_build_source_refs_section()` 输出 Markdown 时自动按 `os.path.relpath()` 转为相对路径）、`note_url`（原文链接）**，要求 LLM 输出结构化行文思路
4. **调用 LLM 生成思路**: `call_llm_strategy(strategy_prompt)` — 使用主模型 temperature=0.5，带重试和降级（同主模型重试逻辑）
5. **保存策略 Markdown**: `save_strategy(strategy_md, property_name, persona, run_id)` → `{run_id}/pre-published/{name}_{persona}_strategy.md`，**保存时必须在策略文件末尾自动拼接「关联素材」章节（见下方素材引用规范）**

### 策略规划输出结构

LLM 必须按以下 Markdown 格式输出行文思路：

| 章节 | 内容要求 |
|---|---|
| **一、目标人群锁定** | 从 5 类人群（新港人刚需/校网家长/投资客/高预算改善/精准研究型）中选择，结合房源参数说明理由 |
| **二、爆款参照** | 从 Agent 2 拆解的爆款笔记中选出最匹配的一条，**硬性要求：必须同时写明 (1) Agent2分析文件名 和 (2) 原文链接 和 (3) Agent2分析JSON的相对路径（可 Ctrl+点击跳转，由 `_build_source_refs_section()` 自动生成）**，三者缺一不可。再说明要借鉴什么（钩子手法/留白策略/结构/话术） |
| **三、钩子设计** | 钩子类型 + 2-3 个备选标题（12-30 字） + 前 3 句话的开头段落 |
| **四、留白设计** | 刻意隐藏什么信息 + 目的 |
| **五、私信引导（CTA）设计** | 引导方式（直接指令式/利益交换式/问题引导式） + 结尾互动措辞 |
| **六、正文大纲** | 5-8 句要点列出每段核心内容 |

> **硬性约束**：二、爆款参照中必须同时包含 **Agent2分析文件名**（如 `687b2f37000000002300586d_香港租房，港岛房源！！！.json`）、**原文链接**（如 `https://www.xiaohongshu.com/discovery/item/...`）、**Agent2分析JSON相对路径**（如 `..\..\..\04_outputs\20260602_1017\analyzed\687b2f37000000002300586d_香港租房，港岛房源！！！.json`，由 `_build_source_refs_section()` 自动根据输出文件位置计算），三者缺一不可。缺少任一项视为策略规划不合格。

### 策略 Markdown 素材引用规范（save_strategy 自动拼接）

`save_strategy()` 在保存 LLM 生成的策略内容后，**必须自动在文件末尾追加以下「关联素材」章节**，将本房源用到的所有素材文件以可点击的**相对路径**列出（由 `os.path.relpath()` 从输出 md 文件所在目录计算）：

```markdown
---

## 📁 关联素材（Ctrl+点击跳转）

### 本房源素材
- **房源信息**: [查看 info.md](..\..\..\01_materials\properties\銅鑼灣_大兩房_$588萬...\info.md)
- **房源图片** ({count} 张):
  - [微信图片_01.jpg](..\..\..\01_materials\properties\銅鑼灣_大兩房_$588萬...\微信图片_01.jpg)
  - ...

### 参考爆款笔记
- **Agent2 分析**: [{analysis_filename}](..\..\..\04_outputs\20260602_1017\analyzed\{analysis_filename})
- **小红书原文**: [{note_url_text}]({note_url})
```

> **路径要求**：所有本地文件路径使用**相对路径**（从输出 md 所在目录 `04_outputs/{run_id}/pre-published/` 向上 `..\..\..` 到达项目根再定位目标文件），使在 VS Code / IDE 中 Ctrl+点击可直接跳转打开文件。`save_strategy()` 调用 `_build_source_refs_section(output_path, ...)`，从 `property_data` 中提取 `info_md_path` 和 `images` 字段自动生成此章节，LLM 无需输出此部分。

### 跳过策略规划

通过 `--skip-strategy` 参数或 `skip_strategy=True` 可跳过 Phase 1，直接进入内容创作（保持向后兼容，适用于快速迭代场景）。

---

## 正文结构规范

| 段落位置 | 内容要求 |
|---|---|
| 第 1 行 | 一句话开头。痛点/场景/直接说事都可，**不要长篇铺垫** |
| 中间 3-6 段 | 自然短段落，每段一两句话。聊空间、采光、位置、月供、装修，想到哪写到哪。把硬参数（呎数、价格、楼层、地铁分钟数）**自然揉进去**，不列清单 |
| 倒数第 2 段 | 制造**真实紧迫感**——不说"手慢无"，而是用具体事实：「租客下周搬走」「业主想快点放」「前两天有人看了说考虑中」「这套我手上拿了几天了，估计很快」 |
| 最后 1 段 | 互动钩子，自然随口一问，不要太客气、不要太营销腔 |

**标题**: 12-30 字，大白话，必须包含一个钩子元素（价格/海景/校网/装修），不要夸张符号。  
**SEO 标签**: 5-10 个，覆盖地名+房型+话题，例如 `#香港买房 #湾仔 #十二校网`  
**配图建议**: 3-6 张，第 1 张封面图用标题核心信息做大字，后面放室内实拍、窗外景观、户型图、周边街景

### 发布稿素材引用规范（save_pre_published 自动拼接）

`save_pre_published()` 在将 LLM 生成的正文 + SEO 标签写入文件后，**必须自动在 Markdown 末尾追加「📁 关联素材」章节**，与本房源策略文件中的素材引用格式完全一致，方便发布者快速定位原始素材：

```markdown
---

## 📁 关联素材（Ctrl+点击跳转）

### 🎨 AI 生成封面图
- [查看封面图](.\{property_name}_cover.png)
- **封面素材原图**: [\{property_name}_cover_原图.jpg](.\{property_name}_cover_原图.jpg)

### 本房源素材
- **房源信息**: [查看 info.md](..\..\..\01_materials\properties\{name}\info.md)
- **房源图片** ({count} 张):
  - [微信图片_01.jpg](..\..\..\01_materials\properties\{name}\微信图片_01.jpg)
  - ...

### 参考爆款笔记
- **Agent2 分析**: [{filename}](..\..\..\04_outputs\{run_id}\analyzed\{filename})
- **小红书原文**: [{title}]({note_url})

### 行文思路
- [查看策略规划](.\{property_name}_{persona}_strategy.md)
```

> **注意**：此章节由 `save_pre_published()` 函数从 `property_data` 和 `strategy_context` 中提取路径自动生成，**LLM 不需要输出此部分**。所有本地文件路径使用**相对路径**（`os.path.relpath()` 从输出 md 位置计算），跨盘符时回退到绝对路径。Ctrl+点击可跳转。

---

## 真实房源加载器

### 数据来源
`01_materials/properties/` 下的每个子目录代表一条房源，包含：
- `info.md` — 非结构化房源信息（面积、价格、楼层、电梯、地铁、校网等）
- `微信图片_*.jpg` — 实拍图片（2-8 张）

### info.md 解析规则
`_parse_info_md()` 从 info.md 提取结构化字段，同时记录文件绝对路径（内部存储用；输出时 `_build_source_refs_section()` 自动转为相对路径）：

| 字段 | 提取方式 |
|---|---|
| `rooms` | 从标题正则匹配：三房/兩房/一房/開放式 → 3/2/1/0 |
| `price_wan` | 正则 `$(\d+)\s*[万萬]` |
| `area_sqft` / `area_gross_sqft` | 实用面积 / 建筑面积 行 |
| `has_lift` / `lift_type` | 平地電梯 / 有電梯 / 没電梯 / 唐楼 |
| `school_net` / `school_net_name` | 括号内十二/12/34 校网 |
| `mtr_station` / `mtr_walk_min` | 优先匹配分钟格式地铁行（`地铁.*Nmin`），其次匹配距离格式（`地铁.*500m`）→ 按 80m/min 折算为分钟数（如 500m → 6min）。默认值为 0（表示未知） |
| `district` / `sub_district` | 湾仔/銅鑼灣/跑馬地 |
| `building_name` | `#` 开头的行 |
| `highlights` | 含管理/收租/投资/回报 的行 |
| `images_count` | 目录下 jpg/jpeg/png 文件数 |
| `info_md_path` | `info.md` 的绝对路径（内部存储，`Path.resolve()`） |
| `property_dir` | 房源子目录的绝对路径（内部存储） |
| `images` | 图片文件名列表 + 各自绝对路径 `[{filename, abs_path}]`（内部存储） |

### 加载函数
- `load_properties_from_dir(shuffle=True)` — 扫描全部房源，随机打乱；每条返回 dict 含内部绝对路径字段，输出 Markdown 时自动转相对路径
- `_pick_properties(count=3)` — 随机选 N 套，不够时用 mock 补足
- `load_analyzed_notes(run_id)` — 加载 Agent 2 分析笔记，每条返回 dict 含 `source_file`、`source_absolute_path`（内部绝对路径）、`note_url`

---

## CLI 参数

```
python writer.py [options]
```

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `--persona` | `amateur\|agent` | `amateur` | 写作视角 |
| `--count` | int | 1 | 生成篇数，随机选 N 套房源 |
| `--output-dir` | Path | `04_outputs/` | 输出基础路径 |
| `--property-dir` | Path | `01_materials/properties/` | 房源目录 |
| `--run-id` | str | 自动生成 | 管线运行时间戳 (YYYYmmdd_HHMM) |
| `--skip-strategy` | flag | false | 跳过策略规划阶段，直接创作 |
| `--skip-cover` | flag | false | 跳过封面图生成阶段 |

示例：
```bash
# 素人视角生成 3 篇（含封面图）
python writer.py --persona amateur --count 3

# 中介视角生成 1 篇，指定运行 ID
python writer.py --persona agent --run-id 20260521_1500

# 跳过策略规划，直接创作（快速模式）
python writer.py --persona amateur --count 3 --skip-strategy

# 跳过封面图生成（纯文本模式）
python writer.py --persona amateur --count 3 --skip-cover
```

---

## 输出 Schema

### JSON 草稿 (NoteContent)
```json
{
  "hook_title": "湾仔250万正规一房 港岛核心区这个价不多见",
  "main_content": "分段口语正文，\\n 表示换行...",
  "interactive_question": "要不要先看看户型图？",
  "seo_tags": ["#香港买房", "#湾仔", "#香港上车盘"]
}
```

### 输出路径规则
```
{output_dir}/{run_id}/
  drafts/
    draft_{persona}_{timestamp}.json         ← LLM 原始输出
  pre-published/
    {property_name}_{persona}.md             ← 可直接发布的图文 Markdown
    {property_name}_{persona}_strategy.md    ← 行文思路规划（策略规划阶段输出）
    {property_name}_cover.png               ← AI 生成封面图（v2.0 新增）
    {property_name}_cover_原图.jpg           ← 封面素材原图副本（记录用哪张图做的封面）
```

- `run_id` 由 `get_run_id()` 自动生成（香港时间 YYYYmmdd_HHMMSS），或通过 `--run-id` 手动指定
- `property_name` 经过 `sanitize_filename()` 安全化处理（去特殊字符）
- `_strategy.md` 仅在未跳过策略规划阶段时生成
- `_cover.png` 仅在未跳过封面图生成且房源有图片时生成
- **⚠️ 封面图和文案必须同一个 `run_id`，输出到同一个 `pre-published/` 目录。禁止分开输出。**
- `_strategy.md` 和 `{property_name}_{persona}.md` 末尾均由保存函数自动拼接「📁 关联素材」章节（含 info.md、图片、Agent2 分析 JSON、封面图的相对路径，由 `os.path.relpath()` 从输出位置计算），LLM 无需输出此部分
- `save_pre_published()` 会自动在 Markdown 中插入封面图的相对路径链接（`🎨 AI 生成封面图` 小节）

---

## LLM 调用与容错

1. **主调用**: 使用 `HEAVY_MODEL`，temperature=0.8，max_tokens=4096
2. **重试**: 最多 3 次，JSON 解析失败自动重试
3. **降级**: 3 次均失败时自动切换 `gemini-3.1-flash-lite` 试一次
4. **JSON 解析**: 自动剥离 markdown 代码块包裹（`` ```json ``` `），支持正则兜底提取 `{...}`
5. **JSON 字段容错**: LLM 返回多余字段时静默忽略，仅提取 `hook_title` / `main_content` / `interactive_question` / `seo_tags` 四个必填字段

---

## 数据流

```
01_materials/properties/*/info.md              ← 真实房源生料
        │
        ▼
  _parse_info_md() → dict                      ← 结构化房源数据
        │                              （绝对路径 → 内部存储）
        ▼
  ═══════════ Phase 0: 封面图生成 ═══════════  (v2.0 新增)
        │
        ├─ _find_living_room_image()           ← VISION_MODEL 识别客厅
        ├─ _build_cover_prompt()               ← 构建英文图像 prompt
        ├─ _call_gemini_image_gen()            ← Gemini 原生图像 API
        │       │
        │       └─ generate_cover()            ← cover.png
        │
  ═══════════ Phase 1: 策略规划 ═══════════
        │
        ├─ load_audience_segments()            ← 人群包 + 模板库
        ├─ load_analyzed_notes()               ← Agent 2 拆解笔记
        │       └─ 每条带 source_absolute_path   （绝对路径 → 内部存储）
        ├─ build_strategy_prompt()
        ├─ call_llm_strategy()                 ← LLM (temp=0.5)
        │       │
        │       └─ save_strategy()             ← strategy.md
        │              └─ 自动拼接 📁关联素材    （relpath 转相对路径）
        │
  ═══════════ Phase 2: 笔记创作 ═══════════
        │
        ├─ build_user_prompt(strategy_md)      ← SOP + 范文 + 房源 + 思路
        ├─ call_llm(user_prompt, persona)      ← LLM (temp=0.8)
        │       │
        │       ├─ save_draft() → JSON 草稿    ← {run_id}/drafts/
        │       └─ save_pre_published() → .md  ← {run_id}/pre-published/
        │              └─ 自动拼接 📁关联素材    （relpath 转相对路径）
        │
        ▼
    最终输出: JSON draft + 发布.md（含相对路径素材链接） + 策略思路.md + 封面图.png
```

`--skip-cover` 参数可跳过 Phase 0，`--skip-strategy` 参数可跳过 Phase 1。

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
| 系统 Prompt | 内嵌在 writer.py 的 `SYSTEM_PROMPT_AMATEUR` / `SYSTEM_PROMPT_AGENT` |
| 封面图 Prompt | 内嵌在 writer.py 的 `_COVER_SYSTEM_PROMPT` / `_build_cover_prompt()` |
| 策略规划函数 | `load_audience_segments()`, `load_analyzed_notes()`, `build_strategy_prompt()`, `call_llm_strategy()`, `save_strategy()` |
| 封面图函数 | `generate_cover()`, `_find_living_room_image()`, `_build_cover_prompt()`, `_call_gemini_image_gen()` |

---

## 关键设计决策与避坑

1. **去 AI 味是最高优先级**。宁可句子不完整、语法不规范，也绝不能像 ChatGPT 写的。每次修改 Prompt 后必须跑一次验证，检查是否出现禁用词、是否每段都加 emoji、是否有列表结构。
2. **两个 Persona 的本质差异不在格式而在视角**。素人是 buyer 视角（记录/共情/吐槽），中介是 seller 视角（信息差/稀缺性/紧迫感）。同一条房源信息，两种视角写出来的内容应该完全不同。
3. **留白策略是转化核心**。每种房源类型都必须刻意隐藏至少一个关键信息（楼盘名/价格/面积），这是引导用户评论或私信的核心机制。不能把所有信息都写出来。
4. **真实紧迫感 > 虚假紧迫感**。用「前两天有人看了说考虑中」「租客下周搬走」这类具体事实制造紧迫感，禁止用「手慢无」「最后一套」这类 AI 味浓厚的虚假话术。
5. **info.md 解析要容错**。不同房产中介写的 info.md 格式差异大（繁简混用、emoji 穿插、字段顺序不同），正则匹配要宽松，关键字段缺失时用 fallback 值。
6. **模型选型**。生成任务用 `HEAVY_MODEL`（需要创意和风格控制），不是轻量分类任务。API 过载时降级到 `gemini-3.1-flash-lite`，虽然风格控制会弱一些但至少不中断管线。
7. **策略规划先于创作（两阶段管线）**。先让 LLM 完成客群锁定 → 爆款参照 → 钩子/留白/CTA 设计 → 正文大纲，再将行文思路传入创作 prompt 约束生成方向。这比直接让 LLM 自由发挥质量更高、更可控。策略规划用 temperature 0.5（强调准确性），正文创作用 temperature 0.8（强调创意和自然度）。可通过 `--skip-strategy` 跳过 Phase 1 以兼容原有单阶段调用。
8. **素材路径由代码自动拼接，LLM 不参与**。`save_strategy()` 和 `save_pre_published()` 末尾的「📁 关联素材」章节由 `_build_source_refs_section(output_path, ...)` 从 `property_data` 字典中提取路径**自动拼接**，用 `os.path.relpath()` 转为相对于输出 md 文件的**相对路径**（如 `..\..\..\01_materials\properties\{name}\info.md`）。LLM 不知道文件系统路径，不能让它生成。`_parse_info_md()` 内部用 `Path.resolve()` 存绝对路径，`_build_source_refs_section()` 输出时转相对路径，跨盘符时回退绝对路径。确保在 VS Code 中 Ctrl+点击可直接跳转。
9. **封面图是锦上添花，不是核心功能，但必须和文案输出到同一个目录**。封面图生成（Phase 0）在任何情况下失败都不应阻断笔记生成管线。使用独立的异常捕获，所有封面相关错误只记录警告日志并继续。通过 `--skip-cover` 可完全禁用封面生成，回退到纯文本模式。
10. **图像生成用原生 Gemini API，不用 OpenAI 兼容端点**。OpenAI 兼容端点 (`/v1beta/openai/`) 不支持 `responseModalities: ["IMAGE", "TEXT"]`，必须用原生 Gemini API (`/v1beta/models/{model}:generateContent`)。客厅识别仍用 OpenAI 兼容端点（只做 vision understanding 不做 generation）。封面生成 prompt 用英文——图像模型对英文指令的理解和遵循度远优于中文。
11. **封面图 Prompt 两层架构**。System Prompt（`_COVER_SYSTEM_PROMPT`）定义不变的摄影师身份和风格指南，动态 Prompt（`_build_cover_prompt()`）根据房源参数注入具体定位和氛围。两者合并作为最终文本指令发送给图像模型。这种架构确保风格一致性的同时，每套房源都有个性化的呈现。
12. **真实感是封面图的最高优先级，在此基础上强化精致度（V2 迭代结论）**。V1 版本生成的封面图真实感好、AI 味不重，但不够精致吸引人。V2 在保持真实感约束不变的前提下，系统性升级了摄影风格：暖金色调、胶卷质感调色、杂志级构图（前景→中景→背景纵深）、按房价分档定位、暖偏向白平衡、柔和对比曲线。核心原则是"像 Architectural Digest 杂志里的照片，但不是 CGI"——精致感来自摄影技术，不是来自换家具或加特效。每次修改提示词后必须实际生成验证：是否看起来像真照片？是否精致到让人想点进去？
13. **封面图的「不能有字」是硬约束**。小红书封面图通常会在图片上叠加大字标题，但这个叠加是发布时在 App 内手工加的，不是 AI 生成时做。AI 生成的底图必须是无文字的干净照片，供后续加字使用。这个约束写在 System Prompt 第一条且多处强调。
14. **封面图生成先于策略规划和笔记创作（Phase 0）**。放在 Phase 0 而非 Phase 2 之后的原因是：(a) 封面图生成不依赖策略规划或笔记正文——只需要房源图片和基础参数；(b) 图像 API 调用时间长（~10-45s），尽早触发可以让它与其他阶段并行；(c) 如果失败，不影响后面的笔记正文生成。
15. **V2 动态 Prompt 按价格分档是必要的信息注入**。Gemini 图像模型对"luxury" vs "cozy budget-friendly"这类抽象概念的理解直接影响成图质感。如果不给价格锚点，模型默认走中性风格，800呎 900万的铜锣湾豪宅和 260呎 250万的湾仔唐楼会生成几乎一样的氛围——这不合理。按价格四档注入风格关键词后，高价位房源自动获得更大气、更通透的透视和更克制的奢华感。
16. **封面图和文案必须同一个 `run_id`，不允许分开输出**。每次 Agent 3 管线运行时，`run()` 函数内的 `generate_cover()` 和 `save_pre_published()` 共用同一个 `run_id` 参数，自然保证封面图和笔记文案落在同一个 `{run_id}/pre-published/` 目录下。**禁止**写临时脚本给封面图和文案分别指定不同的 `run_id`——这会导致封面图在 A 目录、文案在 B 目录，发布时找不到对应关系。如果只要测封面效果，用一个脚本调用完整的 `run()` 或至少确保 `run_id` 一致。跑完 Agent 3 后，所有产物（笔记 .md、策略 .md、封面 .png、原客厅 .jpg）应该都在同一个 `pre-published/` 目录下，一目了然。
