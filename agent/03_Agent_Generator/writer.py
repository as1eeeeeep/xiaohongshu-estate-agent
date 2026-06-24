"""
Agent 3 — 爆款图文生成器 (Writer)
基于房源生料 + SOP 方法论 + 参考范文，生成去 AI 味的小红书房产笔记。
强制输出 JSON，保存到 04_outputs/drafts/，发布稿保存到 04_outputs/{run_id}/pre-published/。

支持三种写作视角：amateur（素人）/ agent（中介）/ lean（极简中介）。
写作前会先做一轮内部策略规划（人群定位/钩子/留白/CTA），但不单独输出策略文件——
规划结果只用于指导正文创作，不落盘、不对外展示。
"""

import argparse
import random
import re
import sys
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pydantic import BaseModel, Field
from openai import OpenAI
from shared import API_KEY, BASE_URL, HEAVY_MODEL, get_run_id, sanitize_filename

# ═══════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════

MODEL = HEAVY_MODEL
MAX_RETRIES = 3

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOP_DIR = PROJECT_ROOT / "02_Agent_Analyzer" / "knowledge_base"
SOP_MD_PATH = PROJECT_ROOT / "data_pipeline" / "stage2_parsed" / "爆款方法论_系统总结.md"
STAGE2_PARSED_DIR = PROJECT_ROOT / "data_pipeline" / "stage2_parsed"
OUTPUTS_DIR = PROJECT_ROOT.parent / "04_outputs"  # base, run_id subfolder appended at runtime
PROPERTIES_DIR = PROJECT_ROOT.parent / "01_materials" / "properties"


# ═══════════════════════════════════════════════════════════════
# Pydantic 输出 Schema
# ═══════════════════════════════════════════════════════════════

class NoteContent(BaseModel):
    hook_title: str = Field(description="标题，带钩子，最终选用版本")
    title_candidates: list[str] = Field(default=[], description="其余5个标题候选，覆盖数字锚定/身份代入/风险提醒3类触发器")
    main_content: str = Field(description="正文，口语短句换行")
    interactive_question: str = Field(description="结尾互动提问")
    seo_tags: list[str] = Field(description="SEO标签，5-10个")
    persona_note: str = Field(default="", description="本篇锁定的目标人群类型")


# ═══════════════════════════════════════════════════════════════
# 日志
# ═══════════════════════════════════════════════════════════════

def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("Agent3.Writer")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter(
            "[%(asctime)s] %(levelname)-6s | %(message)s",
            datefmt="%H:%M:%S",
        ))
        logger.addHandler(h)
    return logger

logger = _setup_logger()


# ═══════════════════════════════════════════════════════════════
# System Prompts（多视角：素人 vs 中介）
# ═══════════════════════════════════════════════════════════════

# ── 共有硬约束（两个 Persona 都必须遵守）────────────────────
_COMMON_RULES = """# Writing Rules（必须死守）

## 绝对不能出现的词
家人们、谁懂啊、绝绝子、宝子们、神仙、笋盘（用"抵买"代替）、宝藏楼盘、绝了、冲它、太香了、手慢无、YYDS、天花板、闭眼入、真香、宝藏、必入、姐妹们、谁懂、宝藏小区、梦中情房

## Emoji 硬限制
整篇笔记最多 3-4 个 emoji。不准用 🔥💥😩🏃‍♂️💨 这些浮夸的。可以适当用 📍💰💎🏠 来标注卖点分段（参考爆款做法）。

## 排版规则
- 可以用简短的结构化符号分段（如「最大优势：」「很多人不知道的是——」），但要自然不僵硬
- 不要用"亮点1 亮点2 亮点3"这类生硬编号格式
- 段落之间空行隔开，核心卖点可以单独成行突出
- 像打字但信息密度要高——每个短句都有目的
- 用香港本地习惯的叫法：呎、校网、平地电梯、走一层楼梯

# Hook Strategy（先判断房源类型，再选写作策略）

拿到房源数据后，先快速判断它属于哪种类型，然后按对应的策略写：

**类型 A：海景 + 性价比（海景靓、价格合理）**
→ 标题用海景+价格，例如「铜锣湾两房 海景 530万」
→ 正文充分描述窗外能看到什么、采光、通风
→ 隐藏：楼盘名
→ CTA：引导在评论区打PM问具体位置

**类型 B：绝对低价（同区最便宜、首付极低）**
→ 标题主打价格，例如「湾仔 250万 一房 港岛这个价不多见了」
→ 正文强调上车门槛低、月供比租金便宜、地段保值（老楼→地段保值论）
→ 隐藏：楼盘名
→ CTA：引导在评论区打PM问具体位置

**类型 C：装修好 / 图片好看（新装修、拎包入住、采光好）**
→ 标题用装修+居住感，例如「刚装修完 湾仔一房 看了就搬」
→ 正文充分描述空间感、装修细节、住进去的感受
→ 隐藏：价格或面积（二选一）
→ CTA：引导在评论区打PM问价或详情

**类型 D：校网刚需（12/34校网、家庭客）**
→ 标题用校网+房型，例如「12校网 湾仔两房 适合带小朋友」
→ 正文讲接送方便、周边环境、社区安全
→ 隐藏：楼盘名
→ CTA：引导在评论区打PM问具体位置

# Content Structure

标题: 12-20字，必须严格控制在20个字以内（包含空格和符号），大白话，必须包含一个钩子（价格/海景/校网/装修），信息密度高。

注意：发布时系统会在正文最前面自动加一行固定声明（"封面图片为装修效果参考图，仅供展示装修后的
空间效果；房屋现状实拍请参见笔记【第二页】！！"），因为封面是 AI 装修效果图不是实拍。你写的
main_content 不需要也不能自己写这句话或类似意思的话，直接从下面的"第1段"开始写。

正文（参考爆款结构：痛点→方案→卖点→情绪→留白）:
- 第1段：痛点引入或直接亮核心卖点。一句话破题。例如"445万买铜锣湾，步行2分钟到地铁站，现在真的越来越少见。"
- 第2段：列出核心优势（3-5个简洁卖点，可单独成行）。例如：
  步行2分钟到地铁站
  可改两房
  高层开扬
  12校网
- 第3段：情绪升华/价值观包装——把硬参数翻译成生活好处。老楼→"真正保值的从来不是楼龄而是地段"；小面积→"先进入核心区生活圈，比一步到位更重要"；大户型→"每个人都有自己的空间"。
- 第4段：制造真实紧迫感。不说"手慢无"，而是用具体事实——"租客下周搬走""这种盘在铜锣湾越来越少""我手上已经有几组在看"。
- 最后1段：直接CTA。引导用户在评论区留言PM，固定写为：“在评论区打PM我给您发这套房子的资料”。绝不能说“私信我”或“直接私信我”。

SEO 标签: 5-10个，覆盖地名+房型+话题，例如 #香港买房 #湾仔 #十二校网

## 距离/时间准确性（极其重要，违反此项整篇作废）
- 房源数据中的 `mtr_walk_min` 是**步行到地铁站的分钟数**，不是通勤到公司的时间。不准把"步行到地铁站 X 分钟"写成"地铁 X 分钟"或"通勤 X 分钟"。
- 必须严格使用房源数据给出的分钟数，禁止自行估算。如果数据写 5 分钟就写 5 分钟，写 7 分钟就写 7 分钟。
- 如果 `mtr_walk_min` 为 0、空或缺失 → **不准提具体分钟数**，改用模糊表述如"近地铁""步行可达"。
- 绝对禁止写"地铁0分钟""出门就是地铁"等不合常理的表述。地铁站再近也要 2-3 分钟步行。
- 你可以说"步行 X 分钟到 XX 站"，但绝对不能说"通勤 X 分钟"（因为你不知道读者在哪上班、坐几站）。

## 输出限制
- 本任务只输出一篇笔记，不要输出多个版本。
- 正文控制在 400 字以内，确保 JSON 不会被截断。

# Output Format
严格返回 JSON，字段：hook_title / title_candidates / main_content / interactive_question / seo_tags / persona_note

hook_title：最终选用的标题（≤20字）。
title_candidates：其余5个标题候选（字符串列表），覆盖数字锚定/身份代入/风险提醒3类触发器，每个≤20字。
persona_note：本篇锁定的目标人群（如"大陆投资型买家"）。
main_content 中的换行用 \\n 表示。"""


# ── Persona: 素人（普通打工人视角）───────────────────────────
SYSTEM_PROMPT_AMATEUR = f"""# Identity
你是一个在香港打工的普通人，最近刚买了一套房（或者正在看房）。你不是中介，不是 KOL，就是个普通上班族。
你现在下班回家瘫在沙发上，打开小红书想记录一下自己的看房/买房经历。你写的东西像发朋友圈——真实、有情绪、不装。

# Voice & Tone
- 视角是"买家/业主"，不是"卖房的人"
- 可以说你纠结过什么、踩过什么坑、最后为什么选了这套
- 可以客观吐槽（走楼梯累、面积小、装修旧），但要真实，不能像在抱怨
- 可以用"我"开头讲故事，用"你"来共情同样在看房的读者
- 口语自然：可以用"说实话""讲真""其实""我觉得""有点"
- 你写东西不是为了卖房，是为了记录和分享。所以语气松弛，没有推销感。
- 允许不完整的句子，允许一句话就是一个段落

# 标题特点
多用情绪词和生活感：终于上车了、看房半年后的决定、值了、没想到能买到、这个预算我尽力了

{_COMMON_RULES}"""

# ── Persona: 中介（专业经纪人视角）───────────────────────────
SYSTEM_PROMPT_AGENT = f"""# Identity
你是一名香港地产中介，负责帮业主推广手上的二手房源，引导有意向的客户在评论区或私信咨询。
没有名字，没有背景故事，就是一个在做这份工作、对房源信息有专业和信息差优势的人。

# Voice & Tone
- 视角是"中介/代理"，对房源信息有专业和信息差优势
- 语气直接自信，点出房源的独特价值与稀缺性，但不夸张
- 每个信息点都要有目的——要么是亮点，要么是真实的紧迫感
- 不啰嗦，节奏紧凑，善用分段与分行，核心卖点可以单独成行亮出来
- 敢于直言：“这个价在港岛核心区真找不出第二套”、“我手上已经有几组客正在约看”
- 结尾CTA统一写为：“想看详细资料或拿钥匙看房的，在评论区打PM我给您发这套房子的资料”

# Writing Rules & Anti-Clichés（红线规则）
- 🚫 绝对、严格禁止以以下句子或其变体开头：
  * “刚带完客” / “刚带完客看房”
  * “在铜锣湾等红灯” / “在湾仔等红灯” / “顺手记一下” / “掏出手机记一下”
  * 任何以“等红灯/站在街头顺手敲字”为噱头的陈词滥调。
- 每篇笔记的开头必须做到多样化、真实且切入点敏锐。你可以选择以下几种开头思路之一：
  1. **市场数据/行情对比切入**：直接聊片区的二手租金回报，或最近业主的降价幅度（例如：“这两天跟几个同行聊天，大家都盯着这套业主急放的...” / “港岛核心区现在买套带12校网的电梯盘，其实真实门槛已经降到了...”）。
  2. **带看客户的真实互动与痛点**：以真实的客户反馈引入（例如：“上周带一组在中环返工的高才客看这套，他们最惊喜的是...” / “很多客户找我，第一句话都是预算有限但要12校网，其实...”）。
  3. **产品/空间细节的视觉直击**：从实景中某个极有说服力的细节开头（例如：“推开阳台门，这个采光和朝向，在港岛老城区确实很能打。” / “400多呎实用面积做到这种大一房，甚至还能轻松间两房，实用率高得有点不可思议。”）。
  4. **痛点与偏见破除**：聊聊买家常见的误区（例如：“很多人觉得楼龄旧就不能碰，但在港岛核心区，真正保值的从来不是楼龄本身，而是...”）。

# 人群定位（每篇先锁定一类，只写给他们）

拿到房源数据后，先判断这套房最适合哪类人，然后全篇只对这类人说话：

| 人群 | 内容重点 |
|---|---|
| 大陆投资型买家 | 流动性、租赁需求、价格锚点对比成交，不承诺回报 |
| 大陆家庭买家 | 生活圈、校网、交通、长期持有，不承诺入学或身份 |
| 港漂上车客 | 总价、月供压力、通勤实用性、首次置业门槛 |
| 跨境自住客 | 两地通勤、口岸动线、物业管理便利 |

persona_note 字段填写本篇锁定的人群类型。

# 字段转化规则（不要堆参数，要转成买方判断）

| 原始字段 | 不要只写 | 应该写成 |
|---|---|---|
| HK$440万 | 叫价440万 | 400多万预算还能不能留港岛西 |
| 实用310呎 | 310呎一房 | 面积小，重点看动线和收纳够不够 |
| 近地铁站约5分钟 | 地铁近 | 生活圈和通勤成立，但别夸成无敌 |
| 20楼一梯两户 | 楼层不错 | 同层少、出入安静，不是决定性卖点 |
| 楼龄较高/老楼 | 老楼 | 估价、维修、按揭年期要先核 |
| 有校网 | 12校网 | 写校网/片区信息，不承诺入学 |

# 卖点包装技巧（重要！学习自爆款笔记）
- 老楼/旧楼 → "真正保值的从来不是楼龄，而是地段"
- 面积小 → "先进入核心区生活圈，比一步到位更重要" 或 "入门港岛盘"
- 面积大 → "每个人都有自己的空间"
- 价格低 → "这种低总价核心区物业，自住方便，未来出租也不愁"
- 有装修 → "不用烦装修，直接拎包入住"
- 近地铁 → "每天出门多睡十分钟，一年下来是完全不同的生活品质"

# 风险必写（每篇至少一个，讲出来反而更像真人）

每篇笔记必须点出至少一个真实风险，不能藏着掖着。从以下维度选最贴合这套房数据的：
楼龄/维修 · 银行估价与叫价差距 · 按揭年期限制 · 租务/空置风险 · 政策变化 · 装修成本

风险不是劝退，而是"先核这件事再决定"的专业表达，让读者觉得你在帮他们而不是推销。

# 标题特点
每篇输出 **6个标题候选**，覆盖以下3类触发器，每类至少2个：
- **数字锚定**：价格+地段+户型，信息密度高，例如"西营盘440万一房 20楼衣帽间"
- **身份代入**：明确写给某类人，例如"大陆买家看港岛 先看这种400万段一房"
- **风险提醒**：把风险变成点击钩子，例如"楼龄老就不能买？先看这3点"

## 点击感强化（重要）
6个候选里至少3个必须用以下任一句式（不能全篇都是平铺直叙的参数堆砌）：
- **设问/反转**：先抛一个常见偏见或疑问，再用房源事实反转。例如"以为西营盘没电梯？418万一房，我终于告别爬楼！""告别纳米楼！炮台山地铁旁竟有这么大的三房"
- **第一人称代入+具象动作**：把冷参数翻译成一个画面/动作。例如"把北角的海风和落日，装进我395万的家里吧""700w住进港岛平地大三房，从此告别爬坡"
- **价格+反差感叹**：价格或数字开头，接一个意外感的转折，可以用问号或感叹号收尾制造语气。例如"湾仔440万一房？它能平地电梯+海景+变两房！"
这3类不是装饰，是真实提升点击率的钩子句式，必须让人一眼有"咦？"或"我也想要"的反应，禁止写成纯参数罗列（如"西营盘 398万 两房 平地电梯"这种直接堆词的标题最多保留1个作为候选，不能选作 hook_title）。

最终选用一个写入 hook_title，其余5个写入 title_candidates 字段（字符串列表）。
所有标题严格控制在20字以内（含标点和空格）。

{_COMMON_RULES}"""

# ── Persona: 极简中介（简洁客观，配表面痛点，保留真实感）─────
SYSTEM_PROMPT_LEAN_AGENT = f"""# Identity
你是一名香港地产中介，负责推广手上的二手房源。没有名字，没有背景故事。
语言简洁客观，像用手机给客户发消息介绍房源情况——不写长文章，只讲清楚关键信息，但要让人读出来是个真人在打字，不是机器人罗列参数。

# Voice & Tone
- 简洁但不生硬。可以用"实话讲""老实说""有一说一"这类口语连接词，让文字有呼吸感，不要变成参数清单。
- 客观平衡：每个优点配一个小缺点，让人感觉你在帮他们分析而不是硬推销。
- 小缺点只能是**无关痛痒的表面问题**：大厦大堂旧式、电梯间不光鲜、厨房是传统梗厨不是开放式、楼下街景旧、管理费比旧楼高、望出去是街景不是海景、要上一层楼梯、单幢楼没会所。
- 🚫 **绝对禁止**用以下问题作为缺点：楼龄/楼龄数字、面积小/户型大小、按揭做不足、银行估不到价。这些是致命伤，不能说。
- 房价和呎价是钩子，放在显眼位置。
- CTA要完整可读，不要省略到看不懂的程度。统一写"评论PM我给您发资料"或"想看资料的评论PM"，不要只写"评论PM"两三个字。

# 正文结构（200-280字左右，简洁但读起来像真人说话，不要写成清单）
注意：发布时系统会在正文最前面自动加一行固定声明（"封面图片为装修效果参考图，仅供展示装修后的
空间效果；房屋现状实拍请参见笔记【第二页】！！"），因为封面是 AI 装修效果图不是实拍。main_content
不需要也不能自己写这句话或类似意思的话，直接从下面的"第1段"开始写。

1. 标题：12-20字，钩子要有点击感，不能是纯参数堆砌。禁止装修风格词，但允许设问句、反转句或轻度克制的语气词
   （"我真的服了""我等到了"这种程度可以，"看哭了""太震撼了"这种夸张感叹词仍然禁止）。
   只能包含：户型+地段+价格+交通+校网这几类硬信息，但组织方式要带一个"咦？"的反转或代入感。
   例："以为西营盘没电梯？418万一房，我终于告别爬楼！" "湾仔440万一房？它能平地电梯+海景+变两房！"
   纯参数堆砌式（如"北角395万 21楼海景一房带平台"）最多作为备选思路，不能直接当最终标题。
2. 第1段：直接亮房源+价格+核心卖点，不铺垫。
3. 第2段：具体参数——面积、楼层、交通、电梯、管理费等，自然带出，不用堆成清单。
4. 第3段：小缺点+转折。用"实话讲/老实说/有一说一"开头，配1-2个表面痛点，然后自然转折到这套房确实不多见。
5. 第4段：紧迫感+CTA，一两句话。例如"已经有几组客在约看，想看资料的评论PM我给您发。"

# 风险规则
- ✅ 可以说的：大厦公区旧式、电梯间不光鲜、厨房传统格局、街景旧、管理费偏高、要上一层楼梯、望街景非海景、单幢楼没会所
- 🚫 不能说的（太致命）：楼龄数字、面积太小、按揭做不足、银行估价跟不上、维修基金庞大

# 卖点包装（精简版）
- 老楼 → 不提楼龄，只说"大厦公区比较旧式"
- 面积小 → 不提面积，说"先进入核心区生活圈比一步到位更重要"
- 价格低 → "这个价在XX区找不出第二套"
- 近地铁 → "步行X分钟到XX站"

# 绝对禁止
- 禁止任何装修风格描述（大理石、轻奢、奶油风、ins风、杂志风等全部不许出现）
- 禁止情绪化感叹（"看哭了""太震撼了""不可思议"等）
- 禁止超过300字正文
- CTA不能简化到看不懂的程度

{_COMMON_RULES}"""

# Persona 配置表
PERSONA_CONFIG = {
    "amateur": {
        "system_prompt": SYSTEM_PROMPT_AMATEUR,
        "label": "素人视角 — 记录分享自己的看房/买房经历，围绕一套具体房源",
    },
    "agent": {
        "system_prompt": SYSTEM_PROMPT_AGENT,
        "label": "中介视角 — 推广房源，信息密度高，引导评论留言获客",
    },
    "lean": {
        "system_prompt": SYSTEM_PROMPT_LEAN_AGENT,
        "label": "极简中介 — 简洁客观，配表面痛点，保留真实感和人情味",
    },
}

# ═══════════════════════════════════════════════════════════════
# User Prompt 构建
# ═══════════════════════════════════════════════════════════════

def build_user_prompt(
    sop_text: str,
    reference_notes: list[dict],
    property_data: dict,
    persona: str = "amateur",
    strategy_md: str = "",
) -> str:
    """将 SOP + 参考范文 + 房源生料 + 行文思路拼接为 user prompt。"""
    parts: list[str] = []

    key_info = _summarize_property(property_data)

    # Special facts reinforcement
    facts_reinforcement = []
    prop_name = property_data.get("name", "")
    if "34" in prop_name or "炮台山" in prop_name:
        facts_reinforcement.append("特别提醒：本大厦有电梯。必须在正文中明确写出：'有电梯：1座配备4部载客电梯，无需爬楼梯'。绝不能写成需要爬楼梯或走楼梯。")
    if "新-1" in prop_name or "南山海" in prop_name:
        facts_reinforcement.append("特别提醒：本豪宅拥有：(1) 私人电梯大堂（独立私人电梯大堂直达户内，极致私隐，身份象征）；(2) 李嘉诚、吕志和等顶级富豪聚居的尊贵邻里圈层（千金买屋万金买邻）；(3) 专享深水湾、寿臣山山海双景（Deep Water Bay views）。必须在正文中明确提及这三点。")

    parts.append(f"【房源数据】（注意：mtr_walk_min 是步行到地铁站的分钟数，不是通勤时间。0 表示未知，不要提具体分钟数）\n{json.dumps(property_data, ensure_ascii=False, indent=2)}")
    
    if facts_reinforcement:
        parts.append(f"\n【重要！硬性事实纠偏与必须提及内容】\n" + "\n".join(facts_reinforcement))
        
    parts.append(f"\n【房源速览】{key_info}")

    if strategy_md:
        parts.append(f"\n【行文思路规划（请严格遵循此思路写作）】\n{strategy_md[:3000]}")

    if reference_notes:
        parts.append("\n【参考范文（注意这是真实爆款的结构参考，但不要照抄措辞）】")
        for i, note in enumerate(reference_notes, 1):
            parts.append(f"\n范文{i}：\n标题：{note['title']}\n正文：\n{note['content'][:600]}")

    if sop_text:
        parts.append(f"\n【SOP 要点（理解核心策略即可，不要生搬硬套）】\n{sop_text[:2000]}")

    persona_hint = {
        "amateur": "记住：你是一个刚买房/在看房的普通打工人，用手机记录分享，不是推销。",
        "agent": "记住：你是负责推广这套房源的地产中介，用手机打字，高效直接，不需要塑造额外人设。",
        "lean": "记住：简洁但真实自然的中介语气，200-280字左右，只说干货+表面小缺点，不写装修风格，不暴露楼龄/面积致命伤，CTA要完整可读。",
    }.get(persona, "记住：用手机打字写一篇真实的分享。")

    parts.append(f"""
【任务】
先判断这套房属于哪种钩子类型（A海景性价比 / B绝对低价 / C装修好看 / D校网刚需）。
然后按对应策略写一篇小红书图文笔记。直接输出 JSON。
{persona_hint}""")

    return "\n".join(parts)


def _summarize_property(data: dict) -> str:
    """从房源 dict 中提炼一句话速览，帮助 LLM 快速判断类型。"""
    price = data.get("price_wan", "?")
    rooms = data.get("rooms", "?")
    area = data.get("area_sqft", "?")
    district = data.get("district", "")
    sub = data.get("sub_district", "")
    has_lift = data.get("has_lift", False)
    lift_type = data.get("lift_type", "")
    school = data.get("school_net_name", "")
    highlights = data.get("highlights", [])
    mtr = data.get("mtr_walk_min", 0)
    mtr_station = data.get("mtr_station", "")
    mtr_str = f" 步行至{mtr_station}站{mtr}分钟" if mtr_station and mtr > 0 else (f" 步行至地铁{mtr}分钟" if mtr > 0 else "")

    loc = f"{district}{sub}" if district else "港岛"
    lift = lift_type or ("有电梯" if has_lift else "走楼梯")
    hl = "、".join(highlights[:4]) if highlights else ""
    school_str = f" {school}" if school else ""

    return f"{loc} | {rooms}房 | {area}呎 | {price}万 | {lift}{mtr_str} |{school_str} | {hl}"


# ═══════════════════════════════════════════════════════════════
# 真实房源加载器（从 01_materials/properties/ 解析 info.md）
# ═══════════════════════════════════════════════════════════════

def _parse_info_md(text: str, dirname: str) -> Optional[dict]:
    """从 info.md 文本中提取结构化房源数据。"""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return None

    data: dict = {
        "name": dirname,
        "district": "",
        "sub_district": "",
        "price_wan": 0,
        "rooms": 0,
        "area_sqft": 0,
        "area_gross_sqft": 0,
        "floor": 0,
        "has_lift": False,
        "lift_type": "",
        "mtr_station": "",
        "mtr_walk_min": 0,
        "school_net": 0,
        "school_net_name": "",
        "renovation": "",
        "highlights": [],
        "images_count": 0,
        "building_name": "",
        "info_md_path": "",
        "property_dir": "",
        "images": [],
    }

    # ── Header line: district, rooms, price, lift, school ──
    header = lines[0]
    # Remove emoji
    header_clean = re.sub(r"[^一-鿿　-〿a-zA-Z0-9\s\.\,\;\:\!\?\-\+\(\)\（\）\$\#\@\%\&\*\/\\\"\'\~\`\^\_\|\<\>\{\}\[\]\【\】\《\》\。\，\；\：\！\？\、\…\—\·]", "", header)

    # Rooms
    room_patterns = [
        (r"三房|3房", 3), (r"兩房|两房|2房", 2),
        (r"大一房|一房|1房", 1), (r"開放式|开放式|studio", 0),
        (r"四房|4房", 4),
    ]
    for pat, count in room_patterns:
        if re.search(pat, header):
            data["rooms"] = count
            break

    # Price
    price_m = re.search(r"\$?(\d+)\s*[万萬]", header)
    if price_m:
        data["price_wan"] = int(price_m.group(1))

    # Lift
    if "平地電梯" in header or "平地电梯" in header:
        data["has_lift"] = True
        data["lift_type"] = "平地电梯"
    elif "有電梯" in header or "有电梯" in header:
        data["has_lift"] = True
        data["lift_type"] = "有电梯"
    elif "没有電梯" in header or "没有电梯" in header or "唐樓" in header or "唐楼" in header:
        data["has_lift"] = False
        data["lift_type"] = "走楼梯"

    # School net
    school_m = re.search(r"[\(（]([^)）]*?(?:十二|12|34|十一|11|四十一|41)\s*校[網网][^)）]*)[\)）]", header)
    if school_m:
        data["school_net_name"] = school_m.group(1).strip()
        net_num = re.search(r"(12|34|11|41)", data["school_net_name"])
        if net_num:
            data["school_net"] = int(net_num.group(1))

    # District
    district_map = {"湾仔": "湾仔", "灣仔": "湾仔", "銅鑼灣": "铜锣湾", "铜锣湾": "铜锣湾", "跑馬地": "跑马地", "跑马地": "跑马地"}
    for key, val in district_map.items():
        if key in header:
            data["district"] = val if "铜锣湾" in val else val
            break
    if "铜锣湾" in header or "銅鑼灣" in header:
        data["sub_district"] = "铜锣湾"
    elif "跑马地" in header or "跑馬地" in header:
        data["sub_district"] = "跑马地"

    # ── Body lines ──
    for line in lines[1:]:
        # Area
        m = re.search(r"(?:实用|實用|实用面积|實用面積).*?(\d+)\s*(?:尺|呎|sq)", line)
        if m:
            data["area_sqft"] = int(m.group(1))
        m = re.search(r"(?:建筑|建築|建筑面积|建築面積).*?(\d+)\s*(?:尺|呎|sq)", line)
        if m:
            data["area_gross_sqft"] = int(m.group(1))
        # Floor
        m = re.search(r"(?:樓層|楼层|樓).*?(\d+)\s*(?:樓|楼|層|层|F)", line)
        if m:
            data["floor"] = int(m.group(1))
        # MTR — 分钟格式
        m = re.search(r"(?:地铁|地鐵|MTR|mtr|步行).*?(\d+)\s*(?:min|分钟|分鐘|分)", line)
        if m:
            data["mtr_walk_min"] = int(m.group(1))
        # MTR — 距离格式（如 500m、500米），按步行80m/min折算
        m_dist = re.search(r"(?:地铁|地鐵|MTR|mtr).*?(\d+)\s*[mM米]", line)
        if m_dist and data["mtr_walk_min"] == 0:
            dist = int(m_dist.group(1))
            data["mtr_walk_min"] = max(2, round(dist / 80))
        m = re.search(r"(?:地铁|地鐵|MTR|mtr)[：:]*\s*([一-鿿A-Za-z]+)", line)
        if m:
            data["mtr_station"] = m.group(1).strip()
        # Lift in body lines
        m_lift = re.search(r"(?:电梯|電梯)[：:]*\s*(.*)", line)
        if m_lift:
            val = m_lift.group(1).strip()
            if any(x in val for x in ["没有", "无", "走楼梯"]):
                data["has_lift"] = False
                data["lift_type"] = "走楼梯"
            else:
                data["has_lift"] = True
                if "平地" in val:
                    data["lift_type"] = "平地电梯"
                else:
                    data["lift_type"] = "有电梯"
        # Renovation
        if re.search(r"裝修|装修|翻新", line):
            data["renovation"] = line
        # Building name
        m = re.search(r"#\s*([一-鿿A-Za-z0-9\s\-]+)", line)
        if m:
            data["building_name"] = m.group(1).strip()
        # Management / highlights
        if re.search(r"管理|收租|投資|投资|回報|回报", line) and line not in data["highlights"]:
            data["highlights"].append(line)

    # Fallback: if no sub_district set, use district
    if not data["sub_district"]:
        data["sub_district"] = data["district"]

    return data


def load_properties_from_dir(prop_dir: Optional[Path] = None, shuffle: bool = True) -> list[dict]:
    """扫描房源目录，解析所有 info.md，返回结构化数据列表。"""
    src = Path(prop_dir) if prop_dir else PROPERTIES_DIR
    if not src.exists():
        logger.warning("房源目录不存在: %s", src)
        return []

    properties = []
    for subdir in sorted(src.iterdir()):
        if not subdir.is_dir():
            continue
        info_path = subdir / "info.md"
        if not info_path.exists():
            continue
        try:
            text = info_path.read_text(encoding="utf-8")
            data = _parse_info_md(text, subdir.name)
            if data and data.get("price_wan") and data.get("rooms", -1) >= 0:
                # Count images and record absolute paths
                imgs = list(subdir.glob("*.jpg")) + list(subdir.glob("*.jpeg")) + list(subdir.glob("*.png"))
                data["images_count"] = len(imgs)
                data["info_md_path"] = str(info_path.resolve())
                data["property_dir"] = str(subdir.resolve())
                data["images"] = [{"filename": img.name, "abs_path": str(img.resolve())} for img in imgs]
                properties.append(data)
                logger.debug("已加载房源: %s", data["name"])
        except Exception as e:
            logger.warning("解析失败: %s — %s", info_path, e)

    logger.info("从 %s 加载了 %d 套房源", src, len(properties))
    if shuffle and properties:
        random.shuffle(properties)
    return properties


def _pick_properties(count: int = 3) -> list[dict]:
    """随机选取 N 套真实房源，不够时用 mock 补足。"""
    props = load_properties_from_dir(shuffle=True)
    if len(props) >= count:
        return props[:count]
    logger.warning("真实房源不足 %d 套（仅有 %d），用 mock 补足", count, len(props))
    return props + [MOCK_PROPERTY] * (count - len(props))


# ═══════════════════════════════════════════════════════════════
# 策略规划（写前构思）—— 选人群 → 学爆款 → 设钩子/留白/CTA
# ═══════════════════════════════════════════════════════════════

def load_audience_segments() -> str:
    """从爆款方法论中提取「客群精准对位」和「可复用模板库」两个章节。"""
    if not SOP_MD_PATH.exists():
        logger.warning("爆款方法论不存在，跳过人群加载")
        return ""
    text = SOP_MD_PATH.read_text(encoding="utf-8")
    # 提取 三、客群精准对位 和 五、可复用爆款模板库 两个章节
    m = re.search(r"(## 三、客群精准对位.*?)(?=## 六|\Z)", text, re.DOTALL)
    segments = m.group(1).strip() if m else ""
    m2 = re.search(r"(## 五、可复用爆款模板库.*)", text, re.DOTALL)
    templates = m2.group(1).strip() if m2 else ""
    result = segments + "\n\n" + templates
    logger.info("加载人群包 + 爆款模板，共 %d 字", len(result))
    return result


def load_analyzed_notes(run_id: Optional[str] = None, limit: int = 5) -> list[dict]:
    """加载 Agent 2 分析过的爆款笔记（优先从最近 run 的 analyzed/ 找，其次 stage2_parsed 子目录）。"""
    candidates: list[Path] = []

    # 优先：从最近的输出目录找
    if run_id:
        run_analyzed = OUTPUTS_DIR / run_id / "analyzed"
        if run_analyzed.exists():
            candidates.extend(sorted(run_analyzed.glob("*.json")))

    # 其次：扫描所有 04_outputs/*/analyzed/
    if not candidates:
        for subdir in sorted(OUTPUTS_DIR.iterdir(), reverse=True):
            adir = subdir / "analyzed"
            if adir.exists():
                for f in sorted(adir.glob("*.json")):
                    candidates.append(f)
                    if len(candidates) >= limit * 2:
                        break
            if len(candidates) >= limit:
                break

    # 再次：回退到 stage2_parsed 的子目录
    if not candidates:
        for subdir in sorted(STAGE2_PARSED_DIR.iterdir(), reverse=True):
            if subdir.is_dir() and subdir.name not in ("5.20收集爆款",):
                for f in sorted(subdir.glob("*.json")):
                    if f.name != "爆款方法论_系统总结.md":
                        candidates.append(f)
                        if len(candidates) >= limit:
                            break
            if len(candidates) >= limit:
                break

    if not candidates:
        logger.warning("未找到 Agent 2 分析过的笔记")
        return []

    notes = []
    for fp in candidates[:limit]:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            notes.append({
                "note_id": data.get("note_id", fp.stem),
                "note_url": data.get("_meta", {}).get("note_url", ""),
                "source_file": fp.name,
                "source_absolute_path": str(fp.resolve()),
                "target_audience": data.get("text_analysis", {}).get("target_audience", ""),
                "hook_type": data.get("text_analysis", {}).get("hook_type", ""),
                "conversion_strategy": data.get("text_analysis", {}).get("conversion_strategy", ""),
                "reusable_template": data.get("reusable_template", ""),
                "property_packaging": data.get("property_packaging", []),
                "audience_intent": data.get("audience_intent", []),
            })
        except Exception:
            continue

    logger.info("加载了 %d 条 Agent 2 分析笔记", len(notes))
    return notes


def build_strategy_prompt(
    property_data: dict,
    audience_segments: str,
    analyzed_notes: list[dict],
    persona: str,
) -> str:
    """构建策略规划 prompt：让 LLM 先确定人群、模板、钩子/留白/CTA 再动笔。"""
    persona_label = PERSONA_CONFIG.get(persona, PERSONA_CONFIG["amateur"])["label"]
    parts: list[str] = []

    parts.append(f"【房源数据】\n{json.dumps(property_data, ensure_ascii=False, indent=2)}")
    parts.append(f"【房源速览】{_summarize_property(property_data)}")
    parts.append(f"\n【写作视角】{persona_label}")

    if audience_segments:
        parts.append(f"\n【人群包 & 爆款模板库】\n{audience_segments[:4000]}")

    if analyzed_notes:
        parts.append("\n【Agent 2 拆解的爆款笔记（含策略分析和可复用模板）】")
        for i, note in enumerate(analyzed_notes, 1):
            parts.append(f"\n爆款{i}：{note['note_id']}")
            if note.get("source_file"):
                parts.append(f"  Agent2分析文件: {note['source_file']}")
            if note.get("source_absolute_path"):
                parts.append(f"  Agent2分析JSON绝对路径: {note['source_absolute_path']}")
            if note.get("note_url"):
                parts.append(f"  原文链接: {note['note_url']}")
            parts.append(f"  目标人群: {note['target_audience'][:200]}")
            parts.append(f"  钩子类型: {note['hook_type'][:150]}")
            parts.append(f"  转化策略: {note['conversion_strategy'][:200]}")
            if note.get("reusable_template"):
                parts.append(f"  复用模板:\n{note['reusable_template'][:500]}")

    parts.append("""
【任务：写前行文思路规划】

在正式写笔记之前，请先完成以下思考，按 Markdown 格式输出一份行文思路文件：

## 一、目标人群锁定
- 这套房源最适合吸引哪类人群？（参考人群包：新港人刚需/校网家长/投资客/高预算改善/精准研究型）
- 为什么选这个人群？结合房源具体参数说明理由。

## 二、爆款参照
- 上述 Agent 2 拆解的爆款笔记中，哪一条的风格/策略最适合这套房源？
- **必须同时写明以下三项，缺一不可：**
  1. Agent2分析文件名（即上述"Agent2分析文件"字段的完整文件名）
  2. Agent2分析JSON绝对路径（即上述"Agent2分析JSON绝对路径"字段，作为 Ctrl+点击跳转链接）
  3. 原文链接（即上述"原文链接"字段的完整 URL）
- 简述你打算从这条爆款中借鉴什么（钩子手法？留白策略？结构？话术？）

## 三、钩子设计
- 用什么钩子类型？（定价冲击 / 身份带入 / 反常识 / 精准筛选 / 人群定义）
- 写出 2-3 个备选标题（每个 12-30 字，大白话，不能有禁用词和浮夸 emoji）
- 前 3 句话打算怎么开？写出完整开头段落。

## 四、留白设计
- 这次打算刻意隐藏什么信息？（楼盘名 / 价格 / 面积）
- 隐藏这个信息的目的是什么？

## 五、私信引导（CTA）设计
- 用什么方式引导用户私信？（直接指令式 / 利益交换式 / 问题引导式）
- 写出结尾互动提问的具体措辞。

## 六、正文大纲
- 用 5-8 句简短要点列出正文每个段落的核心内容
""")

    return "\n".join(parts)


def call_llm_strategy(strategy_prompt: str) -> str:
    """调用 LLM 生成行文思路 Markdown。带重试和降级。"""
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    system_sp = "你是一位经验丰富的小红书房产内容策略师。你的任务是在动笔之前先做好行文思路规划。输出标准 Markdown 格式，结构清晰、具体可执行。"

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info("策略规划 第 %d/%d 次 (%s)...", attempt, MAX_RETRIES, MODEL)
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_sp},
                    {"role": "user", "content": strategy_prompt},
                ],
                temperature=0.5,
                max_tokens=4096,
                timeout=60,
            )
            raw = resp.choices[0].message.content.strip()
            # 剥离可能的代码块包裹
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:markdown)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)
                raw = raw.strip()
            return raw
        except Exception as e:
            logger.error("策略规划异常 (attempt %d): %s", attempt, e)
            if attempt >= MAX_RETRIES:
                fallback_model = "gemini-3.1-flash-lite"
                logger.info("策略规划降级: %s", fallback_model)
                try:
                    resp = client.chat.completions.create(
                        model=fallback_model,
                        messages=[
                            {"role": "system", "content": system_sp},
                            {"role": "user", "content": strategy_prompt},
                        ],
                        temperature=0.5,
                        max_tokens=4096,
                        timeout=60,
                    )
                    raw = resp.choices[0].message.content.strip()
                    if raw.startswith("```"):
                        raw = re.sub(r"^```(?:markdown)?\s*", "", raw)
                        raw = re.sub(r"\s*```$", "", raw)
                        raw = raw.strip()
                    return raw
                except Exception as e2:
                    logger.error("策略规划降级也失败: %s", e2)
                    raise

    raise RuntimeError(f"策略规划失败，已重试 {MAX_RETRIES} 次")



# ═══════════════════════════════════════════════════════════════
# 数据加载（保留 mock 作为回退）
# ═══════════════════════════════════════════════════════════════

def load_sop() -> str:
    """加载爆款 SOP 方法论文本。优先读 markdown，回退到 mock。"""
    if SOP_MD_PATH.exists():
        logger.info("加载 SOP 方法论: %s", SOP_MD_PATH)
        return SOP_MD_PATH.read_text(encoding="utf-8")

    logger.warning("SOP 文件不存在，使用 mock 数据")
    return MOCK_SOP


def load_reference_notes() -> list[dict]:
    """加载参考范文。当前用 mock，后续接入真实范文。"""
    logger.info("加载参考范文 (mock)")
    return MOCK_REFERENCE_NOTES


def load_property_raw() -> dict:
    """加载房源生料。当前用 mock，后续接入真实数据源。"""
    logger.info("加载房源生料 (mock)")
    return MOCK_PROPERTY


# ═══════════════════════════════════════════════════════════════
# Mock 数据（参考范文已按去 AI 味风格重写）
# ═══════════════════════════════════════════════════════════════

MOCK_SOP = """## 标题公式
1. 价格型：港岛核心区 + 价格 + 房型，例「湾仔 250万 一房 港岛这个价不多」
2. 校网型：校网 + 房型 + 客群，例「12校网 湾仔两房 小朋友上学方便」
3. 海景型：地段 + 景观 + 价格，例「铜锣湾 望海 两房 530万」
4. 装修型：刚装完 + 房型 + 地段，例「刚翻新 湾仔一房 拎包入住」

## 留白策略
- 低价盘：不写楼盘名，引导评论问位置
- 海景盘：不写楼盘名，引导评论问哪个盘
- 装修盘：不写价格或面积，引导私信问详情

## 正文结构
开头 → 1-2句破题，不要铺垫
中间 → 3-5段短句聊天，参数自然带出
结尾 → 具体紧迫事实 + 自然互动提问"""

MOCK_REFERENCE_NOTES = [
    {
        "title": "湾仔 465万 三房 12校网 平地电梯",
        "content": """听说你还在看湾仔三房

这套465万，实用357呎，建筑450呎。

位置在铜锣湾地铁口附近，走路大概3分钟。平地电梯，不用爬楼梯，搬东西带小孩都方便。

12校网。小朋友上学的事情不用太操心，这个校网是什么水平你自己查一下就知道。

目前正在重新装修，交房的时候直接可以住。业主那边也好沟通。

收租的话，月供基本能覆盖。这个地段这个价位的三房，湾仔不多。

租客下周搬走，我手上已经有几组在看。你有兴趣的话跟我说一声，我拿户型图给你看看。""",
    },
    {
        "title": "湾仔 250万 一房 港岛核心区 上车盘",
        "content": """港岛湾仔，一房，250万。

实用269呎，正规一房。离湾仔地铁站走路4分钟左右。

唐楼，5楼，没有电梯。坦白说是要走楼梯的，一天上下几次就当运动了。但价格摆在这里——港岛核心区、250万、一房，议价空间还有一点。

投资回报率这个你们自己算算就知道。月供少过租金。

如果你预算有限但是想先在港岛上车，这套可以考虑一下。

租客月底到期搬走。要看的话跟我说，我约时间。""",
    },
]

MOCK_PROPERTY = {
    "name": "湾仔_鸿福大厦_3房",
    "district": "湾仔",
    "sub_district": "铜锣湾",
    "price_wan": 465,
    "rooms": 3,
    "area_sqft": 357,
    "area_gross_sqft": 450,
    "floor": 5,
    "has_lift": True,
    "lift_type": "平地电梯",
    "mtr_station": "铜锣湾",
    "mtr_walk_min": 3,
    "school_net": 12,
    "school_net_name": "湾仔十二校网",
    "renovation": "全新装修中，交房拎包入住",
    "highlights": [
        "平地电梯，不用爬楼梯",
        "步行3分钟到铜锣湾地铁口",
        "12校网",
        "收租回报不错，月供可覆盖",
        "业主好沟通",
    ],
    "images_count": 6,
}


# ═══════════════════════════════════════════════════════════════
# 输出校验（程序化兜底——LLM 不一定听 system prompt，这里做最后一道关卡）
# ═══════════════════════════════════════════════════════════════

_BANNED_WORDS = [
    "家人们", "谁懂啊", "绝绝子", "宝子们", "神仙", "笋盘", "宝藏楼盘", "绝了",
    "冲它", "太香了", "手慢无", "YYDS", "天花板", "闭眼入", "真香", "宝藏",
    "必入", "姐妹们", "谁懂", "宝藏小区", "梦中情房",
]
_BANNED_EMOJI = ["🔥", "💥", "😩", "🏃‍♂️", "💨"]
_LEAN_BANNED_DECOR_WORDS = ["大理石", "轻奢", "奶油风", "ins风", "杂志风"]
_MAX_EMOJI_COUNT = 5  # 硬性要求"最多3-4个"，留1个容差防止误杀旗帜符号等


def _count_emoji(text: str) -> int:
    """粗略统计文本中的 emoji 数量（非 BMP 字符 + 常见符号区间），不误算中文标点。"""
    count = 0
    for c in text:
        cp = ord(c)
        if cp > 0xFFFF:
            count += 1
        elif 0x2600 <= cp <= 0x27BF or cp == 0x2B50:
            count += 1
    return count


def _validate_note(content: NoteContent, persona: str) -> list[str]:
    """程序化校验 LLM 输出是否违反硬性规则。返回违规说明列表，空列表 = 通过。"""
    issues: list[str] = []
    title = content.hook_title or ""
    body = (content.main_content or "").replace("\\n", "\n")
    full_text = f"{title}\n{body}\n" + " ".join(content.seo_tags or [])

    if "装修效果参考图" in body or "第二页" in body:
        issues.append("正文里自己写了封面声明的内容，这句话由系统统一拼接，不能在 main_content 里重复")

    if not title.strip():
        issues.append("标题为空")
    elif len(title) > 20:
        issues.append(f"标题超过20字（实际{len(title)}字）：{title}")

    hit_words = [w for w in _BANNED_WORDS if w in full_text]
    if hit_words:
        issues.append(f"出现禁用词: {', '.join(hit_words)}")

    hit_emoji = [e for e in _BANNED_EMOJI if e in full_text]
    if hit_emoji:
        issues.append(f"出现禁用 emoji: {', '.join(hit_emoji)}")

    emoji_count = _count_emoji(full_text)
    if emoji_count > _MAX_EMOJI_COUNT:
        issues.append(f"emoji 数量过多（约{emoji_count}个，上限{_MAX_EMOJI_COUNT}）")

    body_len = len(body.strip())
    max_len = 300 if persona == "lean" else 400
    if body_len > max_len:
        issues.append(f"正文超过{max_len}字（实际{body_len}字）")

    if re.search(r"地铁\s*0\s*分钟|出门就是地铁|通勤\s*\d+\s*分钟", full_text):
        issues.append("出现不合规的距离/时间表述（地铁0分钟 / 出门就是地铁 / 通勤X分钟）")

    if re.search(r"(^|[。！\n])\s*评论PM\s*([。！]|$)", body):
        issues.append("CTA 过于简略，仅写了孤立的「评论PM」，没说明发什么")

    if persona == "lean":
        hit_decor = [w for w in _LEAN_BANNED_DECOR_WORDS if w in full_text]
        if hit_decor:
            issues.append(f"lean persona 出现禁止的装修风格词: {', '.join(hit_decor)}")
        if re.search(r"楼龄.{0,10}\d|\d{2,3}\s*年.{0,5}楼龄", full_text):
            issues.append("lean persona 提到了楼龄数字（致命伤，禁止作为缺点）")
        if re.search(r"面积(太)?小|户型(太)?小", full_text):
            issues.append("lean persona 提到了面积小/户型小（致命伤，禁止作为缺点）")
        if re.search(r"按揭.{0,10}(不足|做不到|有限|年期短)", full_text):
            issues.append("lean persona 提到了按揭做不足（致命伤，禁止作为缺点）")
        if re.search(r"银行估价.{0,10}(不足|跟不上|有差距|偏低|差)", full_text):
            issues.append("lean persona 提到了银行估价跟不上（致命伤，禁止作为缺点）")

    return issues


# ═══════════════════════════════════════════════════════════════
# LLM 调用
# ═══════════════════════════════════════════════════════════════

def call_llm(user_prompt: str, persona: str = "amateur") -> NoteContent:
    """调用 LLM 生成笔记，带重试、降级、程序化校验。

    校验失败会触发重试（视为可恢复失败，与 JSON 解析失败同等对待）；
    主模型重试耗尽后降级模型再试一次；最终仍未通过校验时，按容错策略
    返回最后一次结果（带瑕疵但不让整个管线崩溃），并在日志中显著标出。
    """
    if persona not in PERSONA_CONFIG:
        logger.warning("未知 persona '%s'，回退使用 amateur 的 system prompt", persona)

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    persona_cfg = PERSONA_CONFIG.get(persona, PERSONA_CONFIG["amateur"])
    system_prompt = persona_cfg["system_prompt"]

    last_result: Optional[NoteContent] = None
    last_issues: list[str] = []

    def _attempt(model_name: str) -> Optional[NoteContent]:
        nonlocal last_result, last_issues
        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
            max_tokens=8192,
            timeout=90,
        )
        raw = resp.choices[0].message.content.strip()
        result = _parse_response(raw)
        issues = _validate_note(result, persona)
        if not issues:
            return result
        logger.warning("生成内容未通过程序化校验: %s", "; ".join(issues))
        last_result, last_issues = result, issues
        return None

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info("第 %d/%d 次生成中 (%s | %s)...", attempt, MAX_RETRIES, MODEL, persona_cfg["label"])
        try:
            result = _attempt(MODEL)
            if result is not None:
                return result
        except json.JSONDecodeError as e:
            logger.warning("JSON 解析失败 (attempt %d): %s", attempt, e)
        except Exception as e:
            logger.error("API 调用异常 (attempt %d): %s", attempt, e)

    fallback_model = "gemini-3.1-flash-lite"
    logger.info("主模型多次未通过校验或失败，降级模型再试一次: %s", fallback_model)
    try:
        result = _attempt(fallback_model)
        if result is not None:
            return result
    except Exception as e2:
        logger.error("降级模型也失败: %s", e2)

    if last_result is not None:
        logger.error("⚠️ 已耗尽重试，仍未通过程序化校验，按容错策略返回最后一次结果（带瑕疵）: %s",
                      "; ".join(last_issues))
        return last_result

    raise RuntimeError(f"LLM 生成失败，已重试 {MAX_RETRIES} 次且降级模型也失败")


def _parse_response(raw: str) -> NoteContent:
    """解析 LLM 返回的 JSON。自动修复常见的截断问题。"""

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    def _try_fix_truncated_json(s: str) -> str:
        """尝试修复被 max_tokens 截断的 JSON。"""
        # 如果最后是未闭合的字符串，补上引号
        # 统计引号数量，奇数说明有未闭合字符串
        in_string = False
        escape_next = False
        quote_count = 0
        for ch in s:
            if escape_next:
                escape_next = False
                continue
            if ch == '\\':
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                quote_count += 1
        # 如果还在字符串内，补闭合
        if in_string:
            s = s + '"'
        # 尝试补齐缺失的 } ]
        open_braces = s.count('{') - s.count('}')
        open_brackets = s.count('[') - s.count(']')
        s = s + ']' * open_brackets + '}' * open_braces
        return s

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # 尝试修复后再解析
        fixed = _try_fix_truncated_json(cleaned)
        try:
            data = json.loads(fixed)
            logger.debug("JSON 截断已自动修复")
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}", cleaned)
            if m:
                fixed2 = _try_fix_truncated_json(m.group(0))
                try:
                    data = json.loads(fixed2)
                except json.JSONDecodeError:
                    raise
            else:
                raise

    # 规范化 seo_tags: LLM 偶发返回字符串而非数组
    raw_tags = data.get("seo_tags", [])
    if isinstance(raw_tags, str):
        raw_tags = [t.strip("#").strip() for t in raw_tags.split() if t.strip()]
    elif isinstance(raw_tags, list):
        raw_tags = [t.strip("#").strip() if isinstance(t, str) else str(t) for t in raw_tags]
    else:
        raw_tags = []

    raw_candidates = data.get("title_candidates", [])
    if isinstance(raw_candidates, str):
        raw_candidates = [raw_candidates]
    elif not isinstance(raw_candidates, list):
        raw_candidates = []

    return NoteContent(
        hook_title=data.get("hook_title", ""),
        title_candidates=raw_candidates,
        main_content=data.get("main_content", ""),
        interactive_question=data.get("interactive_question", ""),
        seo_tags=raw_tags,
        persona_note=data.get("persona_note", ""),
    )


# ═══════════════════════════════════════════════════════════════
# 结果保存
# ═══════════════════════════════════════════════════════════════

def save_draft(content: NoteContent, persona: str = "amateur", run_id: Optional[str] = None, output_dir: Optional[Path] = None) -> Path:
    """保存生成的笔记草稿 JSON，存入 {run_id}/drafts/ 下。"""
    base = Path(output_dir) if output_dir else OUTPUTS_DIR
    run_id = run_id or get_run_id()
    target_dir = base / run_id / "drafts"
    target_dir.mkdir(parents=True, exist_ok=True)

    hk_tz = timezone(timedelta(hours=8))
    ts = datetime.now(hk_tz).strftime("%Y%m%d_%H%M%S")
    output_path = target_dir / f"draft_{persona}_{ts}.json"

    output_path.write_text(
        content.model_dump_json(indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("草稿已保存: %s", output_path)
    return output_path


# ═══════════════════════════════════════════════════════════════
# Markdown 转换 & pre-published 输出
# ═══════════════════════════════════════════════════════════════

# 封面图免责声明：Agent6 生成的封面是 AI 装修效果参考图，不是房屋现状实拍，
# 必须在每篇笔记正文第一段原文不变地出现，避免误导读者。由代码强制拼接
# （不依赖 LLM 自己复述），保证文字 100% 精确、不会被措辞改写或遗漏。
COVER_DISCLAIMER = "封面图片为装修效果参考图，仅供展示装修后的空间效果；房屋现状实拍请参见笔记【第二页】！！"


def convert_to_markdown(content: NoteContent) -> str:
    """将 NoteContent 转为可发布的 Markdown 字符串。"""
    tags = " ".join(f"#{t}" for t in content.seo_tags) if content.seo_tags else ""

    lines = [
        f"# {content.hook_title}",
        "",
        COVER_DISCLAIMER,
        "",
        content.main_content.replace("\\n", "\n"),
        "",
    ]
    if tags:
        lines.append(tags)
        lines.append("")

    return "\n".join(lines)


def save_pre_published(
    content: NoteContent,
    property_name: str,
    persona: str = "amateur",
    run_id: Optional[str] = None,
    output_dir: Optional[Path] = None,
) -> Path:
    """将生成的笔记转为 Markdown 存入 {run_id}/pre-published/（仅标题/正文/标签）。"""
    base = Path(output_dir) if output_dir else OUTPUTS_DIR
    run_id = run_id or get_run_id()
    target_dir = base / run_id / "pre-published"
    target_dir.mkdir(parents=True, exist_ok=True)

    safe_name = sanitize_filename(property_name)
    output_path = target_dir / f"{safe_name}_{persona}.md"

    md_content = convert_to_markdown(content)

    output_path.write_text(md_content, encoding="utf-8")
    logger.info("Markdown 已发布: %s", output_path)
    return output_path


# ═══════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════

def run(
    property_data: Optional[dict] = None,
    sop_text: Optional[str] = None,
    reference_notes: Optional[list[dict]] = None,
    persona: str = "amateur",
    run_id: Optional[str] = None,
    output_dir: Optional[Path] = None,
    skip_strategy: bool = False,
) -> NoteContent:
    """主入口（两阶段管线）：内部策略规划（不落盘） → 笔记创作 → 草稿 + MD 发布稿。

    支持三种 Persona:
      - "amateur": 素人视角，围绕具体房源记录分享
      - "agent": 中介视角，推广房源引导评论/私信
      - "lean": 极简中介视角，简洁客观配表面痛点
    """
    persona_cfg = PERSONA_CONFIG.get(persona, PERSONA_CONFIG["amateur"])
    run_id = run_id or get_run_id()
    logger.info("=" * 50)
    logger.info("  Agent 3 — 爆款图文生成器 启动")
    logger.info("  Persona: %s | Model: %s | Run: %s", persona_cfg["label"], MODEL, run_id)
    logger.info("=" * 50)

    sop = sop_text or load_sop()
    refs = reference_notes or load_reference_notes()
    prop = property_data or load_property_raw()

    summary = _summarize_property(prop)
    logger.info("房源: %s", summary)

    strategy_md = ""
    analyzed_notes: list[dict] = []

    if not skip_strategy:
        # ═══ 阶段 1：内部策略规划（人群/钩子/留白/CTA，不落盘，仅用于指导创作）═══
        logger.info("─" * 40)
        logger.info("【阶段 1/2】内部策略规划（不输出文件）...")
        audience_segments = load_audience_segments()
        analyzed_notes = load_analyzed_notes(run_id=run_id)
        strategy_prompt = build_strategy_prompt(prop, audience_segments, analyzed_notes, persona)
        logger.info("策略 Prompt 构建完成，长度: %d 字", len(strategy_prompt))

        try:
            strategy_md = call_llm_strategy(strategy_prompt)
            logger.info("内部策略规划完成（%d 字，未落盘）", len(strategy_md))
        except Exception as e:
            logger.error("策略规划失败，将继续直接生成: %s", e)
            strategy_md = ""
    else:
        logger.info("【阶段 1/2】策略规划已跳过 (--skip-strategy)")

    # ═══ 阶段 2：笔记创作 ═══
    logger.info("─" * 40)
    logger.info("【阶段 2/2】笔记创作...")
    user_prompt = build_user_prompt(sop, refs, prop, persona=persona, strategy_md=strategy_md)
    logger.info("创作 Prompt 构建完成，长度: %d 字", len(user_prompt))

    try:
        result = call_llm(user_prompt, persona=persona)
    except Exception as e:
        logger.error("生成失败: %s", e)
        raise

    draft_path = save_draft(result, persona=persona, run_id=run_id, output_dir=output_dir)

    md_path = save_pre_published(result, property_name=prop.get("name", "untitled"),
                                 persona=persona, run_id=run_id, output_dir=output_dir)

    logger.info("─" * 50)
    logger.info("生成完成")
    logger.info("  标题: %s", result.hook_title)
    logger.info("  标签: %s", ", ".join(result.seo_tags))
    logger.info("  互动: %s", result.interactive_question)
    logger.info("  正文预览: %s...", result.main_content[:100].replace("\n", " "))
    logger.info("  草稿: %s", draft_path)
    logger.info("  MD: %s", md_path)

    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent 3 — 小红书爆款图文生成器")
    parser.add_argument(
        "--persona",
        choices=["amateur", "agent", "lean"],
        default="amateur",
        help="写作视角: amateur=素人记录分享, agent=中介推广获客, lean=极简中介(简洁客观)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="输出目录（默认 04_outputs/）",
    )
    parser.add_argument(
        "--property-dir",
        type=Path,
        default=None,
        help="房源目录（默认 01_materials/properties/）",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="管线运行时间戳（YYYYmmdd_HHMM），留空则自动生成",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="生成篇数，随机选 N 套房源 (默认 1)",
    )
    parser.add_argument(
        "--skip-strategy",
        action="store_true",
        help="跳过内部策略规划阶段，直接创作（更快，但创作时缺少人群/钩子的前置规划）",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        args = _parse_args()
        count = args.count

        props = load_properties_from_dir(prop_dir=args.property_dir, shuffle=True)
        if not props:
            logger.warning("无真实房源，使用 mock")
            props = [MOCK_PROPERTY]

        selected = props[:count]
        if len(selected) < count:
            logger.info("真实房源不足，仅生成 %d 篇", len(selected))

        for i, prop in enumerate(selected):
            logger.info("\n▸ 第 %d/%d 篇: %s", i + 1, len(selected), prop.get("name", "?"))
            run(property_data=prop, persona=args.persona, run_id=args.run_id,
                output_dir=args.output_dir, skip_strategy=args.skip_strategy)

    except KeyboardInterrupt:
        logger.info("用户中断")
    except Exception as e:
        logger.error("致命错误: %s", e, exc_info=True)
        sys.exit(1)
