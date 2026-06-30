# Agent4 — 素人账号爆款笔记生成器 (Amateur Viral Writer)

> **一句话定位**：给定房源数据，自动生成小红书风格的"素人看房笔记"，输出到标准化的打包文件夹（含文案+实拍图），可直接用于发布。

---

## 目录
1. [功能介绍](#功能介绍)
2. [核心规则（必读）](#核心规则必读)
3. [输入格式](#输入格式)
4. [输出格式](#输出格式)
5. [使用方法](#使用方法)
6. [模块结构](#模块结构)
7. [写作角度说明](#写作角度说明)
8. [与其他Agent的协作](#与其他agent的协作)
9. [配置与依赖](#配置与依赖)
10. [常见问题](#常见问题)

---

## 功能介绍

Agent4 从 Agent2 拆解的真实素人爆款笔记中学习写作模式，针对具体房源生成"素人账号"风格的图文笔记文案。

**支持两种模式**：
- **房源多角度模式**：同一套房源 × 12种写作角度，分三大类——忍痛放弃类（放弃叙事/意外种草）｜长什么样类（优缺点总结/看房日记/看房踩坑/长啥样开箱/单价你会买吗）｜询问类（预算现实吗/纠结对比/决赛圈对比/住得下吗/召唤过来人）
- **非房源引流模式**：6种不介绍具体房源的生活/知识类引流内容（避坑指南/区域测评/买房科普/看房复盘/Citywalk/楼市评论）

**核心输出**：每个笔记一个独立文件夹，结构如下：
```
output_dir/{run_id}/notes/{笔记标题}/
    note.txt          # 纯文本笔记（标题+正文+标签）
    photo_2.jpg       # 随机房源实拍图（1-2张，如有）
    photo_3.jpg       # （可选第二张）
```
> `photo_1.jpg` 留给后续通过小红书「文字配图」功能生成的大字报封面，由外部脚本填充。

同时保留传统 JSON/MD 输出到 `drafts/` 和 `pre-published/` 目录（向后兼容）。

---

## 核心规则（必读）

### 小姐姐

笔记中提到带看人物时，统一使用「**小姐姐**」称呼：
- 用「小姐姐」即可，不需要 @任何账号
- **至多1-2句**，不能成为叙事核心

### 绝对禁止的写法

| 类别 | 禁止内容 |
|------|----------|
| 工具展示 | 小姐姐拿出测距仪/卷尺/激光尺/Excel/计算器 |
| 算账叙事 | 小姐姐当场拉表/算月供/做预算分析 |
| 救场套路 | "差点踩坑→小姐姐阻止→我感恩"三段式 |
| 空泛夸赞 | "耐心""靠谱""专业""实在""良心"等形容词 |
| 违禁标签 | `#靠谱中介` `#诚实中介` `#中介推荐` `#靠谱小姐姐` |
| 浮夸词汇 | 家人们/谁懂啊/绝绝子/YYDS/天花板/闭眼入/真香/宝藏 |
| 推销话术 | "联系我看盘""欢迎咨询""私信我" |

### 字数与语气
- **180-320字**（房源模式），≤400字（非房源模式）
- 第一人称"我"，口语化短句，像朋友圈不像文章
- emoji 最多3-4个，只用 🏠📍💰🇭🇰 等平实类型
- 禁止括号包装 CTA 文字——直接写 `在评论区打PM我给您发这套房子的资料`

### 素人写作铁律
- 像真人随手发帖，有纠结/吐槽/自嘲/小惊喜
- 不完整的句子允许，口语词允许（"说实话""讲真""其实"）
- 短段落，每段一两句话
- 结尾是自然互动提问（如"大家觉得呢"），不是推销引导
- 用香港本地叫法：呎、校网、平地电梯、走一层楼梯、唐楼、上车

---

## 输入格式

### 方式一：房源数据字典（房源多角度模式）

```python
property_data = {
    "name": "西營盤🇭🇰$440萬大一房一廳",
    "district": "中西区",
    "sub_district": "西营盘",
    "rooms": 1,
    "area_sqft": 310,
    "price_wan": 440,
    "floor": 20,
    "lift_type": "平地电梯",
    "mtr_station": "西营盘",
    "mtr_walk_min": 4,
    "school_net_name": "11校网",
    "renovation": "有装修",
    "property_dir": "D:/path/to/property/photos/",
    "images": ["1.jpg", "2.jpg", ...],  # 可选
}
```

### 方式二：Agent5 简报（非房源模式）

```python
brief_section = {
    "why_it_works": "引流逻辑说明",
    "key_requirements": ["要求1", "要求2"],
    "agent_integration_hint": "中介身份融入策略",
    "example_sketch": "打样片段参考",
}
```

---

## 输出格式

### 主输出：文件夹（`save_assembled`）

每篇笔记生成一个独立文件夹。示例：
```
04_outputs/20260617_1400/notes/西营盘这套440万的房，纠结好久还是没敢买/
    note.txt           # 标题+正文+标签
    photo_2.jpg        # 房源实拍图（随机1张）
```

### 辅助输出（向后兼容）

- `{run_id}/drafts/*.json` — JSON 草稿（含 cover_text_rows 等完整字段）
- `{run_id}/pre-published/*.md` — Markdown 发布稿
- `{run_id}/pre-published/*.txt` — 纯文本

---

## 使用方法

### Python API（推荐）

```python
import sys
sys.path.insert(0, "D:/xiaohongshu_estate/agent")
from Agent_04_AmateurViral import run, load_reference_notes, save_assembled, PROPERTY_ANGLES

# 1. 加载参考范文（Agent2的拆解结果）
refs = load_reference_notes()

# 2. 针对一个房源，生成5个角度各一篇
property_data = {...}  # 房源数据字典
prop_dir = Path("D:/xiaohongshu_estate/01_materials/properties/6.16主做/【3】西營盤/")

results = []
for angle_key in PROPERTY_ANGLES:
    result = run(
        property_data=property_data,
        angle_key=angle_key,
        reference_notes=refs,
        output_dir=Path("D:/xiaohongshu_estate/04_outputs"),
    )
    results.append(result[0])  # run() 返回 list[NoteContent]

# 3. 结果已自动保存到 output_dir/{run_id}/notes/ 和 drafts/ pre-published/
for r in results:
    print(r.hook_title)
```

### CLI（基本用法）

```bash
# 非房源模式：按母题随机生成
python -m 04_Agent_AmateurViral.writer4 --category "看房日记" -n 3 --run-id 20260617_test

# 查看所有可用角度
python -m 04_Agent_AmateurViral.writer4 --list-angles

# 房源多角度模式：--property-dir 和 --angle 必须同时传，缺 --angle 直接报错
python -m 04_Agent_AmateurViral.writer4 \
  --property-dir "/Users/asleep/松鼠找房/01_materials/properties/6.29主做/【西营盘-10】..." \
  --angle 单价你会买吗 \
  --run-id 20260629_xiyingpan10 \
  --output-dir "/Users/asleep/松鼠找房/06_output(multiangle)"
```

---

## 模块结构

```
04_Agent_AmateurViral/
    __init__.py          # 导出：run, NoteContent, save_assembled, PROPERTY_ANGLES 等
    writer4.py           # 核心：LLM调用、prompt构建、结果保存
    system_prompt.txt    # System Prompt（定义了语气/规则/输出格式）
    README.md            # 本文档
```

### 关键函数速查

| 函数 | 用途 |
|------|------|
| `run(property_data, angle_key, ...)` | 主入口：生成一篇房源角度笔记 |
| `run_non_property(type_name, brief_section, ...)` | 生成一篇非房源引流笔记 |
| `save_assembled(content, property_data, ...)` | 输出到标准文件夹（note.txt + 实拍图） |
| `save_assembled_simple(content, ...)` | 仅输出 note.txt（无照片） |
| `revise_note(original, angle_key, ...)` | 根据Agent5反馈修改笔记 |
| `load_reference_notes(dir)` | 加载Agent2的拆解JSON作为范文 |

### NoteContent Schema

```python
class NoteContent(BaseModel):
    hook_title: str            # 标题，12-25字
    main_content: str          # 正文，换行用 \n
    interactive_question: str  # 结尾互动提问
    seo_tags: list[str]        # 标签，5-10个
    image_suggestions: list[str]  # 配图建议，3-6条
    persona_note: str          # 本篇的素人子人设说明
```

---

## 写作角度说明

### 房源多角度模式（12种，分三大类）

> **强制规则：使用 `--property-dir` 时必须同时传 `--angle`，缺少则报错列出全部角度。**
> Python API 调用同理，`angle_key` 参数不可省略。

**大类一 · 忍痛放弃类**

| 角度 | Key | 基调 | 是否提小姐姐 |
|------|-----|------|-------------|
| 放弃叙事 | `"放弃叙事"` | 纠结后放弃，带遗憾 | 可选（≤1句） |
| 意外种草 | `"意外种草"` | 低预期→反转心动 | 可选（≤1句） |

**大类二 · 长什么样类**

| 角度 | Key | 基调 | 是否提小姐姐 |
|------|-----|------|-------------|
| 优缺点总结 | `"优缺点总结"` | 理性测评，先抑后扬 | 可选 |
| 看房日记 | `"看房日记"` | 日记式，场景感 | 可选/不强制 |
| 看房踩坑 | `"看房踩坑"` | 区域踩坑横扫，这套唯一及格 | 可选（≤1句） |
| 长啥样开箱 | `"长啥样开箱"` | 标题「地名+总价+长啥样」，60-120字短开箱 | 可选 |
| 单价你会买吗 | `"单价你会买吗"` | 算每呎价换算每平方米，结尾「你会买吗」 | 不需要 |

**大类三 · 询问类**

| 角度 | Key | 基调 | 是否提小姐姐 |
|------|-----|------|-------------|
| 预算现实吗 | `"预算现实吗"` | 摆预算+区域+户型，客观问「现实吗」 | 不需要 |
| 纠结对比 | `"纠结对比"` | 还没决定，求建议 | 不需要 |
| 决赛圈对比 | `"决赛圈对比"` | 多盘只谈优点，纠结求建议 | 不需要 |
| 住得下吗 | `"住得下吗"` | 家庭几口人住得下？求过来人 | 不需要 |
| 召唤过来人 | `"召唤过来人"` | 召唤住过/买过的人爆料后悔点 | 不需要 |

> **字数**：长啥样开箱 60-120字；单价你会买吗 / 预算现实吗 120-200字；召唤过来人 150-250字；其余 180-320字。
> **已下架**（2026-06-30 重塑删除）：租客离别、亮点加预算、老公乱签合同、买完后悔、执着踩坑。

### 非房源引流模式（6种）

| 类型 | Key | 说明 | 小姐姐限制 |
|------|-----|------|-----------|
| 避坑指南 | `"避坑指南"` | 置业/租房知识科普 | 禁止出现 |
| 区域生活测评 | `"区域生活测评"` | 某区域生活体验 | 禁止出现 |
| 买房全流程科普 | `"买房全流程科普"` | 买房流程教学 | 禁止出现 |
| 看房复盘日记 | `"看房复盘日记"` | 看了多套后的复盘 | 至多1次 |
| CitywalkHK探区 | `"CitywalkHK探区"` | 步行探索某区域 | 禁止出现 |
| 香港楼市行情评论 | `"香港楼市行情评论"` | 楼市动态点评 | 禁止出现 |

---

## 与其他Agent的协作

```
Agent1 (Scraper)
    ↓ 爬取小红书真实素人笔记
Agent2 (Analyzer)
    ↓ 拆解笔记结构 → analyzed/*.json
Agent4 (AmateurViral)  ← 你在这里
    ↓ 生成新的素人笔记文案
Agent3 (Generator)
    ↓ 生成大字报封面图（photo_1.jpg）
[外部脚本]
    ↓ xhs_cover_grab.py 从小红书「文字配图」抓封面
[组装脚本]
    ↓ assemble_notes.py 配实拍图+封面→最终发布文件夹
```

**Agent4的输出即是最终发布的文件夹**，后续只需要：
1. 运行 `xhs_cover_grab.py` 给封面组的文件夹补上 `photo_1.jpg`（小红书大字报封面）
2. 直接发布到小红书

---

## 配置与依赖

### 依赖
- `openai` — LLM API 调用（通过 `shared.config` 配置）
- `pydantic` — 输出 Schema

### 关键配置（`shared/config.py`）
```python
API_KEY = "..."          # API Key
BASE_URL = "..."         # API Base URL
HEAVY_MODEL = "..."      # 主力模型（当前 gemini-3.1-pro-preview）
```

### 推荐模型
- **主力**：`gemini-3.1-pro-preview`（`shared/config.py` 中的 `HEAVY_MODEL`，与其他 Agent 统一）
- **降级**：`gemini-3.1-flash-lite`（网络波动/主模型报错时自动切换）

---

## 常见问题

### Q: 如何批量生成同一房源的5个角度？
```python
for angle in PROPERTY_ANGLES:
    run(property_data=data, angle_key=angle, reference_notes=refs, output_dir=out)
```

### Q: 输出目录里为什么没有 photo_1.jpg？
`photo_1.jpg` 是小红书「文字配图」生成的大字报封面，需要单独通过 Playwright 脚本 `scratch/xhs_cover_grab.py` 生成。详见该脚本的注释。

### Q: 如需在笔记中 @某个账号怎么办？
修改 `system_prompt.txt` 和 `writer4.py` 的 `AGENT_PERSONA`，添加 @规则。

### Q: 生成的笔记字数不符合要求怎么办？
检查 `system_prompt.txt` 中的字数限制（180-320字），以及 LLM 的 `max_tokens` 设置。
如果持续偏长/偏短，在 `build_property_angle_prompt()` 的写作铁律中调整字数说明。

### Q: 笔记中仍然出现了"拉了个表"或"测距仪"怎么办？
这些词在 `system_prompt.txt` 的"绝对不能出现的看房行为"中已列为禁止项。
如果LLM仍然输出，在 `call_llm()` 之后加后处理过滤，或调整 temperature 参数。
