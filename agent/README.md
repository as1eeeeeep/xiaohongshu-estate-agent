# 小红书香港房产图文生成项目快速上手指南 (Quick Start Guide)

本指南旨在帮助重新安装或新加入项目的 Claude Code 助手快速理解整个项目的架构、数据流向、运行指令以及核心的工程约束规则。

---

## 📁 项目目录架构

项目根目录包含三个核心文件夹：`01_materials`（生料素材）、`agent`（代码核心）和 `04_outputs`（管线输出）。

```
d:/xiaohongshu_estate/
├── 01_materials/                   # 原始房源素材与下载库
│   ├── properties/                 # 房源文件夹（包含 info.md 与微信实拍图片）
│   │   ├── 灣仔🇭🇰開放式_$268万_.../
│   │   ├── 铜锣湾超大1房🇭🇰.../
│   │   └── 灣仔尚翘峰$1200萬_.../
│   └── _inbox/                     # 新房源生料临时录入文件夹
│
├── agent/                          # 代码核心目录（Claude 主要运行在此处）
│   ├── .claude/skills/             # 预置给 Claude 的技能指令库（非常重要）
│   │   ├── agent2-analyzer.md      # Agent 2 拆解分析器的运行规范
│   │   └── agent3-writer.md        # Agent 3 笔记与封面图生成器的运行规范
│   ├── 01_Agent_Scraper/           # Agent 1 (爬虫/下载模块，仿真模式)
│   ├── 02_Agent_Analyzer/          # Agent 2 (思路分析模块) -> analyzer.py
│   ├── 03_Agent_Generator/         # Agent 3 (笔记与图文创作) -> writer.py
│   ├── 04_Agent_AmateurViral/      # Agent 4 (素人口吻爆款改写)
│   ├── 05_Agent_TrafficCritic/     # Agent 5 (流量审稿与封面批评)
│   ├── 06_Agent_CoverCreator/      # Agent 6 (房源照片精装修封面生成)
│   ├── shared/                     # 公共配置模块 (ChromaDB, 环境变量等) -> config.py
│   ├── .env                        # 存放 API 秘钥等环境变量
│   └── README.md                   # 本指南文件
│
└── 04_outputs/                     # 成果物输出根目录
    ├── downloads/                  # Agent 1 下载下来的自热爆款小红书笔记（作为 RAG 参照）
    ├── agent_stage1/               # Agent 2 的临时暂存区 (Staging Folder)
    └── {YYYYMMDD_HHMM}/            # 每次运行管线按“精确到分钟的时间戳”创建的目录
        ├── analyzed/               # Agent 2 拆解生成的结构化 JSON 文件
        ├── drafts/                 # Agent 3 创作生成的草稿 JSON 文件
        └── pre-published/          # 最终待发布成果物（双封面、正文 .md、策略 .md）
```

---

## 🔄 核心运行流水线 (Pipeline Workflows)

一个完整的生成流程分为以下三个步骤（通过 `run_batch_six.py` 或手动命令运行）：

### 1. 准备参考笔记 (Stage references for RAG)
将小红书下载的爆款笔记目录（例如 `downloads/6a259c9e0000000013020401_炮台山站一分钟新装修` 等）拷贝到暂存区 `04_outputs/agent_stage1/`。

### 2. 运行 Agent 2 (分析器)
运行以下命令，对暂存区的爆款笔记进行多模态反向思路分析，提取其中的客群定位、钩子设计和留白策略，并写入 `{run_id}/analyzed/` 下：
```bash
# 在 agent/ 目录下运行：
python -m 02_Agent_Analyzer.analyzer --input-dir ../04_outputs/agent_stage1 --output-dir ../04_outputs --run-id {run_id}
```
*注：`run_id` 建议格式为 `YYYYMMDD_HHMM`。*

### 3. 运行 Agent 3 (文案与封面生成)
运行以下命令，加载对应的房源数据，读取分析器的策略 JSON 以及 SOP 规则，生成行文思路、小红书正文以及加字封面图：
```bash
# 生成指定的房源笔记（中介视角 + 包含封面图，在 agent/ 目录下运行）：
python -m 03_Agent_Generator.writer --persona agent --run-id {run_id}
```
也可以通过 Python 脚本直接调用模块：
```python
from 03_Agent_Generator import writer
writer.run(
    property_data=prop,     # 房源数据 dict
    persona="agent",        # agent (中介) 或 lean (极简中介)
    run_id=run_id,          # 运行时间戳 YYYYMMDD_HHMM
    output_dir=OUTPUTS_DIR,
    skip_strategy=False,
    skip_cover=False
)
```

---

## 🔴 核心工程规则与特定房源特殊逻辑

重新安装的 Claude 必须严格遵守以下关键开发规范：

### 1. 封面图 Style B 叠字规范 (Style B Text Overlays)
所有的封面叠字图生成必须严格遵循 **Style B 风格**（亮黄 + 纯白 + 亮黄交替，外加粗黑边）：
- **第一行**：亮黄大字 (`#FFE300`)
- **第二行**：纯白大字 (`#FFFFFF`)
- **第三行**：亮黄大字 (`#FFE300`)
- **粗黑描边**：在 PIL 的 `draw.text` 方法中，注入 `stroke_width = max(2, int(base_font_size * 0.10))` 且 `stroke_fill = "#000000"`，确保大字在任何深色/浅色图片背景上都有极高的视觉可读性。
- **排版定位**：文字水平居中，Y轴在顶部 8% 至 35% 区域，**绝对禁止**遮挡室内的核心采光窗户和视线焦点。
- **非BMP字符过滤**：自动过滤掉所有 `ord(c) > 0xFFFF` 的字符（如国旗 🇭🇰），防止 Windows 系统下绘制 emoji 时出现豆腐块（`[]`）乱码。

### 2. 双封面保存机制 (Double Cover Outputs)
每一次运行 Agent 3 生成封面时，必须保存两张图片：
- 📷 `{property_name}_cover_clean.png`：100% 干净、无任何文字的精致空间摄影图（奶油风）。
- 🎨 `{property_name}_cover.png`：叠加了 Style B 粗黑描边叠字文案的最终成品封面图。

### 3. 湾仔尚翘峰的“2.jpg”强制底图规则
在为 `灣仔尚翘峰$1200萬_次新樓_兩房_有露台_有泳池` 生成封面时，必须**强制选择 `2.jpg`**（展示阳台和户外泳池实景的真实照片）作为封面底图。
- 逻辑实现：对 `writer._find_living_room_image` 打补丁或加正则逻辑：
```python
# 必须使用 Lookbehind(?<!\d) 确保精确匹配 2.jpg，而不是 12.jpg
if "灣仔尚翘峰" in img["filename"] and re.search(r'(?<!\d)2\.jpg$', img["filename"]):
    return img
```

### 4. API 超时与模型降级策略 (API Timeouts & Fallbacks)
由于 API 可能遇到 503 等限流与过载问题，系统内嵌了超时保护和降级模式：
- **超时设置**：策略分析 `timeout=60` 秒，笔记正文生成 `timeout=90` 秒。
- **降级模型**：主模型为 `gemini-2.5-pro`。如果主模型连续 3 次超时或 JSON 解析失败，则**自动降级使用 `gemini-3.1-flash-lite`** 重新请求，保证流水线不中断。

### 5. 输出规范 (Pre-published Markdown)
`{property_name}_{persona}.md` 只包含标题、正文、标签三部分（`convert_to_markdown()` 直出），
不附加任何素材链接或调试信息——保持发布稿干净，可直接复制进小红书。

---

## 🛠️ Claude 如何开始协助开发？

如果您刚刚重装了 Claude 客户端：
1. **加载技能包**：先阅读 `agent/.claude/skills/` 下的 `agent2-analyzer.md` 和 `agent3-writer.md` 文件。
2. **运行管线**：如果需要批量重新生成，可编写或调用类似 `scratch/run_batch_six.py` 的脚本，在后台执行并检测输出。
3. **输出核对**：检查生成的 Markdown 文件，验证段落语气是否有 AI 味（绝对禁止出现“家人们、绝绝子、笋盘、宝藏”等词），验证导出的 PNG 封面是否已加上粗黑描边字样。
