# Agent 2 — 爆款笔记拆解器 (Analyzer)

## 角色定位
多模态反向工程小红书房产爆款笔记。输入图文笔记 → 配对 txt+图片 → Base64 编码 → RAG 检索 Top-2 爆款方法论 → 调用多模态 API → 输出结构化 JSON 拆解报告，提炼可复用的留白模板。

Agent 2 不生成内容，只负责**拆解和学习**已有爆款。它的产出直接喂养 Agent 3（Writer）的 SOP 知识库和参考范文库。

---

## 三合一子系统

### 1. `analyzer.py` — 日常拆解管线（核心）
批量处理笔记目录，逐一调用多模态 API 输出 JSON 拆解报告。

### 2. `build_kb.py` — RAG 知识库构建
从 `D:/香港房产账号资料` + `data_pipeline/sop_docs/` 加载运营方法论文档（txt/md/docx/xlsx），分块向量化存入 ChromaDB，供拆解时检索。

### 3. `extract_strategy.py` — 爆款方法论提炼
选取 8 条代表性笔记（封面图 + 正文），一次性喂给多模态模型，输出系统性 Markdown 报告 `爆款方法论_系统总结.md`。这份报告既是 RAG 知识库的核心文档，也是 Agent 3 直接加载的 SOP 参考。

---

## 核心配置

### 模型
| 用途 | 模型 | 说明 |
|---|---|---|
| VISION_MODEL | `gemini-3.1-flash-image-preview`（默认） | 多模态图文分析，支持图片+文本联合推理 |
| EMBEDDING_MODEL | `BAAI/bge-small-zh-v1.5` | 中文文本向量化，RAG 检索 |

- `VISION_MODEL` 可通过环境变量覆盖：`$env:VISION_MODEL = "gemini-2.5-pro"`
- 如当前模型 503 不可用，应尝试更换可用模型（如 `gemini-2.5-pro`、`gemini-2.5-flash`）
- `extract_strategy.py` 同时发送 8 条笔记+封面图，需模型支持大上下文（max_tokens=16384）

### RAG 参数
| 参数 | 值 |
|---|---|
| ChromaDB Collection | `sop_methods` |
| 相似度空间 | cosine |
| 检索 Top-K | 2 |
| 检索 query | 笔记正文前 50 字 |
| Chunk Size | 500 字 |
| Chunk Overlap | 80 字 |
| 向量归一化 | True |

### API 配置
- Base URL: `https://generativelanguage.googleapis.com/v1beta/openai/`
- Temperature: 0.3（拆解需要稳定性，不要创造性）
- Max Tokens: 4096
- 重试次数: 3 次
- 重试间隔: JSON 解析失败等 2s，API 异常等 3s

---

## 输入规范

### 支持的目录结构

**平铺模式**（stage1_raw 默认）：
```
stage1_raw/
  2026-05-01_松鼠鼠找房OE_标题.txt
  2026-05-01_松鼠鼠找房OE_标题_1.jpeg
  2026-05-01_松鼠鼠找房OE_标题_2.jpeg
```
- `.txt` 与图片通过 stem 匹配（图片 `_1` `_2` 后缀自动剥离）
- 支持的图片格式: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`

**子目录模式**（viral_examples 收集的笔记 / Agent 1 下载的笔记）：
```
downloads/6936a96f000000001e03146c_/
  6936a96f000000001e03146c_.txt
  6936a96f000000001e03146c_1.webp
  meta.json          ← Agent 1 写入，含 note_url + note_id
```
- 每个子目录是一条笔记，内含 1 个 `.txt`/`.md` + 若干图片 + 可选 `meta.json`
- `meta.json` 由 Agent 1 (`download_note_content()`) 在下载时自动写入，包含 `note_id` 和 `note_url`
- 子目录名作为 `note_name` 写入 `_meta`，`note_url` 从 `meta.json` 读取
- **note_url 三级降级**：
  1. 优先读 `meta.json` → `note_url`（Agent1 下载时写入的完整分享链接）
  2. 若 `meta.json` 缺失但目录名以 24 位 hex 开头 → 构造 `https://www.xiaohongshu.com/explore/{note_id}`
  3. 若都不是（本地图文素材，无线上来源）→ 填入该笔记目录相对于输入目录的路径，如 `5.20收集爆款/湾仔海景房/`
- `pair_notes_with_images()` 自动检测：先检查是否有子目录含 .txt，有则走子目录模式，否则走平铺模式

### .txt 文件格式（viral_examples 风格）
```
作品标题: <title>
作品描述:
<multi-line content...>

发布时间: YYYY-MM-DD_HH:MM:SS
作者昵称: <author>
作品标签: <tags...>
作品链接: <url>
```

---

## 输出规范

### JSON Schema
```json
{
  "note_id": "提取笔记的标题作为ID",
  "visual_analysis": {
    "cover_style": "封面视觉风格描述（色彩、排版、氛围）",
    "core_text": "封面上最具冲击力的核心文案大字"
  },
  "text_analysis": {
    "target_audience": "参考爆款理论，指出该笔记瞄准的精准客群",
    "hook_type": "前20个字使用的是什么钩子类型",
    "conversion_strategy": "刻意隐藏的关键信息（楼盘名/价格/面积）及行动呼吁话术",
    "persona_perspective": "发帖视角分类：素人视角 / 中介视角 / 教学向视角，附判断依据"
  },
  "property_packaging": [
    "卖点包装1：如何将硬参数转化为情绪价值",
    "卖点包装2"
  ],
  "audience_intent": [
    "评论区核心诉求1",
    "评论区核心诉求2"
  ],
  "reusable_template": "基于原文逻辑的 Markdown 填空模板，必须包含留白钩子",
  "_meta": {
    "note_name": "原始文件名（不含扩展名）",
    "note_url": "原笔记链接或本地路径。优先 meta.json；其次从目录名 note_id 构造 XHS 链接；最后用相对路径",
    "images_count": 4,
    "retrieved_sop": "RAG 检索到的 Top-2 SOP 片段原文"
  }
}
```

### 模板留白钩子规则（核心）
`reusable_template` 字段的结尾必须根据房源路线设计信息留白钩子：
- **高价品质路线**：模板提示隐藏【价格】
- **低价性价比路线**：模板提示隐藏【楼盘名】
- **视觉极佳房源**：模板提示隐藏【价格或面积】

模板结尾示例：
```
【留白钩子】想知道这个神仙小区的具体名字？评论区滴滴我！
```

### 输出目录
- `04_outputs/{run_id}/analyzed/` — 每个笔记一个 `.json` 文件
- `run_id` 格式：`YYYYmmdd_HHMM`（如 `20260520_1425`），默认自动生成
- 失败也写空 JSON，确保管线不会卡住

---

## System Prompt 设计哲学

Agent 2 的 system prompt（`system_prompt.txt`）定义了以下角色约束：

### 身份
"拥有百万粉丝操盘经验的顶级小红书房产内容策略专家"，精通视觉排版、人性痛点挖掘、文案结构拆解、高转化"信息留白"引流策略。

### 分析维度（6 步法）
1. **视觉洞察**：封面排版风格 → 核心大字 → 为什么能留住用户
2. **理论映射**：对标 RAG 检索到的 SOP 片段 → 判断瞄准哪类客群 → 解决什么痛点
3. **卖点翻译**：硬参数（呎数/价格/楼层）→ 情绪价值包装的转换手法
4. **留白与引流**（最核心）：刻意隐藏什么信息制造信息差？如何诱导评论/私信？
5. **抽象模板**：提取填空模板，必须包含留白钩子
6. **发帖视角识别**：判断笔记的发帖人身份，综合用词习惯、信息透明度、行文目的，归入五类，然后就算你看出来某些帖子是伪装的，也要按伪装的视角去理解：
   - **素人视角**：普通打工人/业主买家，用"我"讲故事，有个人情绪，像发朋友圈，无推销感
   - **中介视角**：房产经纪人，语气高效，强调稀缺性和紧迫感，刻意隐藏楼盘名引导私信
   - **教学向视角**：房产博主/KOL，客观分析，教方法论，不以卖特定楼盘为目的
   - **讨论向视角**：房产博主/KOL/自媒体/素人/房产经纪人，就某个房产或行业现象发表看法，引导大家一起讨论
   - **求助向视角**：新人小白/购房者，分享自己遇到的问题或困惑，希望获得大家的建议和帮助。

### 输出约束
- **必须且只能输出合法 JSON**
- 禁止 Markdown 代码块包裹（不要 ```json）
- 禁止前置或后置解释文字
- 直接输出 JSON 对象本身

---

## RAG 知识库

### 数据来源
1. `D:/香港房产账号资料/` — 香港房产运营方法论文档（txt/md/docx/xlsx）
2. `data_pipeline/sop_docs/` — 项目内 SOP 补充文档
3. `data_pipeline/stage2_parsed/爆款方法论_系统总结.md` — extract_strategy.py 产出的系统方法论（后期可加入）

### 分块策略
- 按空行 → 自然段边界递归分块
- 每块 ≤ 500 字，块间 overlap 80 字
- 块 ID = MD5(source_name + chunk_index) 前 12 位

### 向量化
- 模型: `BAAI/bge-small-zh-v1.5`
- normalize_embeddings=True
- 存储: ChromaDB PersistentClient，路径 `02_Agent_Analyzer/knowledge_base/`

### 检索流程
1. 取笔记正文前 50 字作为 query
2. 用 `SentenceTransformer.encode()` 生成 query 向量
3. ChromaDB 余弦相似度检索 Top-2
4. 拼接格式: `【来源：{source}】\n{chunk_content}\n\n---\n\n`
5. 若 collection 不存在 → 返回 "(知识库为空，暂无参考方法论)"，不中断流程

---

## CLI 使用

```bash
# 默认：处理 stage1_raw → 04_outputs/{auto_run_id}/analyzed/
python analyzer.py

# 指定输入（5.20 收集的爆款）
python analyzer.py --input-dir "01_materials/viral_examples/5.20收集爆款"

# 指定输出目录和 run_id
python analyzer.py --input-dir "..." --output-dir "04_outputs" --run-id "20260521_0930"

# 遇到 503 时切换模型
$env:VISION_MODEL = "gemini-2.5-pro"; python analyzer.py --input-dir "..."
```

### 参数
| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `--input-dir` | Path | `data_pipeline/stage1_raw` | 输入目录 |
| `--output-dir` | Path | `04_outputs` | 输出根目录（会自动追加 run_id/analyzed） |
| `--run-id` | str | 自动生成 `YYYYmmdd_HHMM` | 管线运行时间戳 |

---

## extract_strategy.py — 爆款方法论提炼

### 设计意图
一次性把 8 条代表性笔记（封面图 + 正文）发给模型，让它横向对比总结系统方法论。产出是一份 Markdown 报告，覆盖 5 大维度：
1. 标题与封面视觉策略（逐条分析 + 4-6 种标题公式模板）
2. 钩子与正文结构（前 3 句钩子拆解 + 黄金分段模板）
3. 客群精准对位（每条笔记瞄准的客群 + 话术体系）
4. 信息留白与转化钩子（隐藏什么 + 3-5 种 CTA 公式）
5. 可复用爆款模板库（按客群分类的填空模板）

### 精选笔记策略维度
| 笔记 | 策略维度 |
|---|---|
| 湾仔368万平地电梯房 | 价格冲击 + 稀缺捡漏 |
| 香港女生月薪一万8买房 | 身份带入 + 月薪买房 |
| 湾仔十二校网两房 | 校网刚需 + 宝妈 |
| 465万拿下12校网3房 | 捡漏 + 校网双重钩子 |
| 湾仔海景半新楼 | 品质景观 + 情绪价值 |
| 跑马地十二校网收租 | 投资收租 + 校网组合 |
| 海盈山户型全解析 | 户型解析 + 新盘 |
| AI找房工具 | AI工具 + 话题引流 |

### 内容限制
- 每条笔记正文截断到 2000 字
- 封面图以 Base64 data URL 传入
- `max_tokens=16384`，temperature=0.4

---

## 防风控与容错

### API 错误处理
- **503 (high demand)**：自动重试 3 次，间隔 3s。3 次仍失败则该笔记写空 JSON
- **JSON 解析失败**：自动重试 3 次，间隔 2s
- **非 503 异常**：同样重试 3 次，不区分错误类型
- 不要在重试耗尽后中断整个批量任务 — 跳过当前笔记继续下一个

### 图片处理
- `gemini-3.1-flash-image-preview` 通过 OpenAI 兼容 API **支持** `image_url` content block
- 图片以 Base64 data URL（`data:{mime};base64,{data}`）嵌入 messages，与文本组成 multimodal user content
- MIME 类型按文件扩展名映射（.jpg→image/jpeg, .png→image/png, .webp→image/webp 等）

### Windows 编码
- `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`
- 所有文件读写指定 `encoding="utf-8"`

### ChromaDB
- 使用 `PersistentClient`，路径 `knowledge_base/`
- 关闭 `anonymized_telemetry`
- 若 knowledge_base 目录被锁（SQLite busy），等待后重试

---

## 文件路径速查

| 用途 | 路径 |
|---|---|
| 核心拆解脚本 | `agent/02_Agent_Analyzer/analyzer.py` |
| 知识库构建 | `agent/02_Agent_Analyzer/build_kb.py` |
| 策略提炼 | `agent/02_Agent_Analyzer/extract_strategy.py` |
| System Prompt | `agent/02_Agent_Analyzer/system_prompt.txt` |
| ChromaDB 持久化 | `agent/02_Agent_Analyzer/knowledge_base/` |
| 默认输入 | `agent/data_pipeline/stage1_raw/` |
| 默认输出 | `04_outputs/{run_id}/analyzed/` |
| 策略报告输出 | `agent/data_pipeline/stage2_parsed/爆款方法论_系统总结.md` |
| 知识库源文档 | `D:/香港房产账号资料/`, `agent/data_pipeline/sop_docs/` |
| 手动收集的爆款 | `01_materials/viral_examples/` |

---

## 与上下游的协作

### 上游 — Agent 1 (Hunter)
- Agent 1 爬取的笔记存入 `data_pipeline/stage1_raw/` → Agent 2 默认输入
- Agent 1 筛选的合格 URL 存入 `01_materials/viral_examples/` → Agent 2 可通过 `--input-dir` 处理

### 下游 — Agent 3 (Writer)
- Agent 2 产出的 `爆款方法论_系统总结.md` → Agent 3 加载为 SOP 参考
- Agent 2 产出的拆解 JSON → Agent 3 可提取为参考范文模板
- 拆解报告中 `reusable_template` 字段 → 直接指导 Agent 3 的正文结构

### 运行顺序
```
Agent 1 (Hunter) → 爬取笔记到 stage1_raw
       ↓
Agent 2 (Analyzer) → 拆解笔记，产出 JSON + 爆款方法论
       ↓
Agent 3 (Writer) → 加载 SOP + 参考范文，生成新笔记
```
