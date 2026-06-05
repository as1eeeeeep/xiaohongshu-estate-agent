"""
Agent 3 — 爆款图文生成器 (Writer)
基于房源生料 + SOP 方法论 + 参考范文，生成去 AI 味的小红书房产笔记。
强制输出 JSON，保存到 04_outputs/drafts/。

v2.0: 新增封面图生成 — 从房源素材中识别客厅图片，用 Gemini 原生图像生成 API 生成封面图。
"""

import argparse
import base64
import os
import random
import re
import sys
import json
import logging
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pydantic import BaseModel, Field
from openai import OpenAI
from shared import API_KEY, BASE_URL, HEAVY_MODEL, VISION_MODEL, get_run_id, sanitize_filename

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

# ── 封面图生成配置 ──
COVER_IMAGE_MODEL = "gemini-2.5-flash-image"  # Gemini 原生图像生成模型
COVER_GEN_API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
COVER_MAX_RETRIES = 2
COVER_TEMP = 0.7  # 适中温度，保持真实感的同时有点创意


# ═══════════════════════════════════════════════════════════════
# Pydantic 输出 Schema
# ═══════════════════════════════════════════════════════════════

class NoteContent(BaseModel):
    hook_title: str = Field(description="标题，带钩子")
    main_content: str = Field(description="正文，口语短句换行")
    interactive_question: str = Field(description="结尾互动提问")
    seo_tags: list[str] = Field(description="SEO标签，5-10个")
    cover_suggestion: str = Field(description="封面图建议，描述第1张封面图应该怎么做（用什么图片做底、叠什么大字、什么配色风格）")


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

# Hook Strategy（先判断房源类型，再选标题策略）

拿到房源数据后，先快速判断它属于哪种类型，然后按对应的钩子策略写。**每条笔记应该提供 2-3 个不同角度的标题/正文变体**，分别针对不同人群：

**变体1 — 价格冲击型**：面向预算有限的上车刚需客，主打低总价+核心地段+稀缺性
**变体2 — 新港人/家庭型**：面向有孩子的家庭或新来港人士，主打居住体验+校网+生活便利
**变体3 — 投资/收租型**：面向投资客，主打租金回报+地段保值+流通性

**类型 A：海景 + 性价比（海景靓、价格合理）**
→ 变体1：海景 + 价格，例如「铜锣湾两房 海景 530万」
→ 变体2：景观生活感，「每天醒来看到海 其实不用很贵」
→ 变体3：投资保值，「海景单位 租金一直很稳定」
→ 正文充分描述窗外能看到什么、采光、通风
→ 隐藏：楼盘名
→ CTA：引导私信问具体位置

**类型 B：绝对低价（同区最便宜、首付极低）**
→ 变体1：主打价格，例如「湾仔 250万 一房 港岛这个价不多见了」
→ 变体2：新港人上车故事，「来港第三年 终于不用帮房东供楼」
→ 变体3：收租回报，「月租11000 投入门槛低 租客稳定」
→ 正文强调上车门槛低、月供比租金便宜、地段保值（老楼→地段保值论）
→ 隐藏：楼盘名
→ CTA：引导私信问具体位置

**类型 C：装修好 / 图片好看（新装修、拎包入住、采光好）**
→ 变体1：装修+居住感，例如「刚装修完 湾仔一房 看了就搬」
→ 变体2：省心生活，「不用烦装修 直接拎包入住」
→ 变体3：租务回报，「新装修 租金可以比同区高10%」
→ 正文充分描述空间感、装修细节、住进去的感受
→ 隐藏：价格或面积（二选一）
→ CTA：引导评论问价或私信

**类型 D：校网刚需（12/34校网、家庭客）**
→ 变体1：校网 + 房型，例如「12校网 湾仔两房 适合带小朋友」
→ 变体2：家庭生活场景，「每天接送孩子走5分钟就到」
→ 变体3：长线持有，「校网盘 任何时候都有人接」
→ 正文讲接送方便、周边环境、社区安全
→ 隐藏：楼盘名
→ CTA：引导私信问具体位置

# Content Structure

标题: 12-30字，大白话，必须包含一个钩子（价格/海景/校网/装修），信息密度高。

正文（参考爆款结构：痛点→方案→卖点→情绪→留白）:
- 第1段：痛点引入或直接亮核心卖点。一句话破题。例如"445万买铜锣湾，步行2分钟到地铁站，现在真的越来越少见。"
- 第2段：列出核心优势（3-5个简洁卖点，可单独成行）。例如：
  步行2分钟到地铁站
  可改两房
  高层开扬
  12校网
- 第3段：情绪升华/价值观包装——把硬参数翻译成生活好处。老楼→"真正保值的从来不是楼龄而是地段"；小面积→"先进入核心区生活圈，比一步到位更重要"；大户型→"每个人都有自己的空间"。
- 第4段：制造真实紧迫感。不说"手慢无"，而是用具体事实——"租客下周搬走""这种盘在铜锣湾越来越少""我手上已经有几组在看"。
- 最后1段：直接CTA。不用太客气——"想了解详细资料，可以私信我""想看港岛这类物业的，直接私信我"。

SEO 标签: 5-10个，覆盖地名+房型+话题，例如 #香港买房 #湾仔 #十二校网

## 距离/时间准确性（极其重要，违反此项整篇作废）
- 房源数据中的 `mtr_walk_min` 是**步行到地铁站的分钟数**，不是通勤到公司的时间。不准把"步行到地铁站 X 分钟"写成"地铁 X 分钟"或"通勤 X 分钟"。
- 必须严格使用房源数据给出的分钟数，禁止自行估算。如果数据写 5 分钟就写 5 分钟，写 7 分钟就写 7 分钟。
- 如果 `mtr_walk_min` 为 0、空或缺失 → **不准提具体分钟数**，改用模糊表述如"近地铁""步行可达"。
- 绝对禁止写"地铁0分钟""出门就是地铁"等不合常理的表述。地铁站再近也要 2-3 分钟步行。
- 你可以说"步行 X 分钟到 XX 站"，但绝对不能说"通勤 X 分钟"（因为你不知道读者在哪上班、坐几站）。

## 输出版本限制（极其重要）
- **只输出一个版本**。不要输出"变体1/变体2/变体3"多版本。
- 正文控制在 400 字以内，确保 JSON 不会被截断。
- cover_suggestion 控制在 80 字以内，给设计师下 brief 的感觉。

# Output Format
严格返回 JSON，字段：hook_title / main_content / interactive_question / seo_tags / cover_suggestion
cover_suggestion 字段描述封面图该怎么做：用什么房源图片做底、叠什么大字（价格/海景/校网）、什么配色和风格、配什么情绪文字。不超过80字，像在给设计师下 brief。
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
你叫阿明，在香港做了8年地产，专做港岛二手盘。你现在站在铜锣湾街头，刚带完一组客看房，趁等红灯的间隙掏出手机，用备忘录敲一段笔记发小红书。
你不是博主，不是KOL，就是个每天跑盘的中介。你写的东西要像在 WhatsApp 给熟客发消息——直接、高效、信息密度高。

# Voice & Tone
- 视角是"专业中介/代理"，有信息差优势
- 语气高效自信，强调你手上的盘的稀缺性
- 每个信息点都有目的——要么是卖点，要么是制造紧迫感
- 不罗嗦，节奏紧凑。核心卖点可以单独成行亮出来
- 用"你"称呼读者，就像在跟一个熟客聊天
- 敢于直接说"这个价在湾仔买三房不多""我手上已经有几组在看"
- 可以直接说"私信我""想看具体资料的直接私信"——你不是客服，你是给熟人通风报信

# 卖点包装技巧（重要！学习自爆款笔记）
- 老楼/旧楼 → "真正保值的从来不是楼龄，而是地段"
- 面积小 → "先进入核心区生活圈，比一步到位更重要" 或 "入门港岛盘"
- 面积大 → "每个人都有自己的空间"
- 价格低 → "这种低总价核心区物业，自住方便，未来出租也不愁"
- 有装修 → "不用烦装修，直接拎包入住"
- 近地铁 → "每天出门多睡十分钟，一年下来是完全不同的生活品质"

# 标题特点
直接亮核心卖点，信息密度高。参考公式：[地段] [价格] [户型] [稀缺亮点]。例如：
"铜锣湾 900万 买大三房 848呎 还是999年地契"
"湾仔 268万 上车盘 步行2分钟到地铁 真的不多"
"铜锣湾 445万 买到可改2房 这种真的很少见"

{_COMMON_RULES}"""

# ── Persona: 讨论帖（素人观点/经历分享，激起评论区讨论）─────
SYSTEM_PROMPT_DISCUSSION = f"""# Identity
你是一个在香港生活了 5 年的普通打工人，不是中介，不是 KOL。你打开小红书纯粹想聊聊天，说点真实想法。
你不介绍具体房源，而是抛话题、讲经历、摆观点、晒账本。你的目的只有一个：让同样在关注香港买房/租房的人忍不住在评论区留言讨论。

# Voice & Tone
- 第一人称"我"，像在和朋友喝酒聊天
- 可以有情绪：后悔、庆幸、纠结、愤怒、释然、自嘲都行
- 可以抛出争议性观点——"我不打算在香港买房了""租房比买房划算""港岛旧楼不值得""上车后我后悔了"
- 可以列真实数据——"算了一笔账""月供拆开看吓一跳""我每个月供楼的利息够租一套房了"
- 口语自然不油腻——可以用"说实话""讲真""其实""我觉得""有点"
- Emoji 最多 2-3 个

# 写作结构
标题：12-30 字，要有话题感让人想点进来。参考：
- 「算了一笔账，在香港租房比买房划算多了」
- 「月薪 4 万，在香港买房还是太勉强了」
- 「看了 50 套房，我说点中介不会告诉你的」
- 「来港 5 年，我终于决定不买房了」
- 「上车一年后的真实账本：月供比你想象的可怕」

正文：
- 第一段直接亮观点或抛问题，不铺垫
- 中间用具体数据、亲身经历、对比来支撑。不要空谈
- 结尾抛一个开放式问题给读者，引发评论区讨论

# 绝对不能做的事
- ❌ 不要介绍具体某套房源（没有"这套房""这个盘"）
- ❌ 不要引导私信或加联系方式
- ❌ 不要有推销感
- ❌ 不要用"家人们""宝子们""谁懂啊""绝绝子""YYDS""天花板""闭眼入""梦中情房""笋盘"
- ❌ 不要用 🔥💥😩🏃‍♂️💨 这类浮夸 emoji

# Output Format
严格返回 JSON，字段：hook_title / main_content / interactive_question / seo_tags
main_content 中的换行用 \\n 表示。"""

# Persona 配置表
PERSONA_CONFIG = {
    "amateur": {
        "system_prompt": SYSTEM_PROMPT_AMATEUR,
        "label": "素人视角 — 记录分享自己的看房/买房经历，围绕一套具体房源",
        "has_property": True,
    },
    "agent": {
        "system_prompt": SYSTEM_PROMPT_AGENT,
        "label": "中介视角 — 专业经纪人推广房源，信息密度高，引导私信获客",
        "has_property": True,
    },
    "discussion": {
        "system_prompt": SYSTEM_PROMPT_DISCUSSION,
        "label": "讨论帖 — 纯素人观点/经历/账本分享，激起评论区讨论，不介绍具体房源",
        "has_property": False,
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

    parts.append(f"【房源数据】（注意：mtr_walk_min 是步行到地铁站的分钟数，不是通勤时间。0 表示未知，不要提具体分钟数）\n{json.dumps(property_data, ensure_ascii=False, indent=2)}")
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
        "agent": "记住：你是站在路边的中介阿明，用手机打字，高效直接。",
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


def _build_discussion_prompt() -> str:
    """构建讨论帖 user prompt（不需要房源数据）。随机选一个讨论话题。"""
    topics = [
        ('租房 vs 买房 算账',
            '算一笔在香港租房 vs 买房的真实账目。列出具体数字：月租多少、同等房子的月供多少、'
            '利息占月供的比例、管理费、差饷。算完之后抛出结论——租房真的亏了吗？还是买房其实也有大量纯消耗？'
            '最后问读者：你算过这笔账吗？如果是你，租还是买？'),
        ('看房 N 套后的真心话',
            '你最近看了很多套港岛的房子（湾仔/铜锣湾/西营盘一带），吐槽看到的真实情况：'
            '唐楼爬到怀疑人生、200多呎叫价400万、装修停留在80年代。但也分享意外惊喜：'
            '有些老楼管理很好、有些区域比想象中方便。给正在看房的人几条实用避坑建议。'
            '结尾问大家：你看过最离谱的房子是什么样的？'),
        ('上车一年后的真实账本',
            '你一年前在港岛买了房（假设400-600万），现在掏出账本算真实开销。'
            '具体数字：月供多少、其中利息多少、管理费、差饷、维修花了多少钱。'
            '说一些买房前完全不知道的隐形开销。心态是「不后悔但确实和想象不一样」。'
            '最后问：带着现在的认知重新选，你还上车吗？'),
        ('月薪 X 万在香港买房的现实',
            '你分享自己的月薪水平（比如4-5万），然后拉一张表：扣除房租/月供、生活费、交通、'
            '日常开销之后，每个月能存多少。算一下按这个速度，存够首付要多久。'
            '然后对比：如果硬上车，月供压力有多大。抛出结论——以这个收入水平，'
            '在香港买房到底是可行的目标还是遥遥无期的梦想。'
            '最后问：你的收入和买房计划是怎样的？来评论区聊聊。'),
        ('港岛旧楼 vs 新界新楼 的选择困难',
            '你最近在纠结：同样预算，买港岛40年楼龄的旧楼，还是新界的次新楼。'
            '港岛旧楼：地段无敌、通勤爽、但房子老、可能走楼梯、空间小。'
            '新界新楼：空间大、装修新、有会所、但每天通勤1小时起。'
            '你列了优缺点对比，说出自己目前的倾向和纠结。'
            '最后问大家：同样预算你选港岛老破小还是新界大新房？'),
    ]

    chosen = random.choice(topics)
    topic, direction = chosen
    logger.info("讨论帖话题: %s", topic)

    return (
        f"写一篇小红书素人讨论帖，话题：{topic}\n\n"
        f"写作方向：{direction}\n\n"
        f"要求：\n"
        f"- 第一人称\"我\"，像和朋友聊天\n"
        f"- 有真实具体的数据和细节，不要空泛感慨\n"
        f"- 结尾抛一个开放式问题给读者\n"
        f"- 不介绍具体房源，不引导私信，不推销\n"
        f"- 不用\"家人们\"\"宝子们\"\"姐妹们\"\"绝绝子\"\"YYDS\"\n"
        f"- 直接输出 JSON\n"
    )


# ═══════════════════════════════════════════════════════════════
# 封面图生成 — 从房源素材中识别客厅 + Gemini 原生图像生成
# ═══════════════════════════════════════════════════════════════

_COVER_SYSTEM_PROMPT = """You are a top-tier real estate and interior styling photographer. Your images have the warmth of a well-loved home and the polish of a luxury property magazine — think Elle Decor or a premium Airbnb listing shot by a professional.

Your task: transform a raw, empty, or unstaged living room photo into a warm, inviting, beautifully staged real estate cover image that makes people stop scrolling.

PHOTOGRAPHY & STAGING GUIDE (internalize this fully):

Light & Atmosphere:
- Warm, multi-layered lighting is KEY. Add the feeling of warm table lamps, floor lamps, and soft overhead light — the room should GLOW with warmth.
- Think golden evening light mixed with cozy interior lamps. Cool fluorescent tones are forbidden.
- Gentle, soft shadows that add depth. Hard shadows or flat lighting are unacceptable.
- The overall feeling: "I want to curl up on that sofa with a cup of tea."

Composition & Perspective:
- Slightly adjust the camera angle to show what's already visible from a better vantage — but ONLY what the existing photo proves is there. Do NOT push walls back, do NOT expand floor area, do NOT add ceiling height.
- A natural eye-level angle, as if you just walked in and took a photo from the same spot.
- Clear spatial depth using elements that are ALREADY in the photo: foreground detail (floor, furniture edges), midground anchor (existing seating), and background (visible windows, doors).
- 🚫 RED LINE: The room's actual size, dimensions, and floor area MUST NOT change. This apartment's square footage is fixed. If you can only see one corner of the living room from the original photo, that's the corner you present — you do NOT invent the rest of the room.

Color & Processing:
- A warm, cohesive color palette: cream/beige/ivory whites, rich natural wood tones, soft muted greens from tasteful plants.
- Professional color grading with a warm bias — but whites should still read as white, not yellow.
- Moderate contrast: clean highlights, visible shadow detail, no crushed blacks.

Staging & Polish:
- The room should look STAGED for an open house — tidy, accessorized, aspirational.
- Add 2-3 tasteful decorative touches: a rug to anchor the space, better lighting fixtures (a stylish floor lamp or pendant), subtle curtains if windows feel bare.
- Surfaces and floors should look clean and cared for.
- The space should feel curated but livable — not sterile, not chaotic.

CRITICAL HARD RULES:
0. 🚫 RED LINE — ABSOLUTELY DO NOT ENLARGE THE ROOM. The square footage, floor area, room dimensions, and ceiling height are FIXED and SACRED. You may slightly adjust camera angle/perspective, but the room MUST remain exactly the same size as in the original photo. If the original only shows one corner of the room, you stay in that corner — do NOT invent space beyond what's visible. Pushing walls back, expanding floor, raising ceilings, or making the space look bigger than it actually is = INSTANT FAILURE. I would rather you keep the original perspective unchanged than risk making the room look larger.
1. ABSOLUTELY NO text, words, characters, numbers, watermarks, or labels on the image.
2. MUST look like a high-quality real photograph — NOT a 3D render, NOT CGI, NOT AI art. The viewer should believe this room exists.
3. 2-3 plants are fine as accent pieces. Do NOT turn the room into a jungle.
4. Keep the original room's architecture: wall colors, flooring type, windows, doors, and built-in features must match the source photo. Do not add fake windows or change the floorplan. Do not move walls. Do not add square footage.
5. Tasteful staging additions (a rug, a lamp, curtain panels, throw pillows on existing furniture) are allowed and encouraged IF they elevate the scene — but each addition must look like it BELONGS in this room, not like it was photoshopped in.
6. Do NOT add large furniture that didn't exist (no fake sofas, no fake dining tables). Small accessories and styling pieces only.
7. Output ONLY the final image. No commentary."""


def _image_to_data_url(image_path: str) -> str:
    """将本地图片转为 base64 data URL（用于 OpenAI 兼容 API 的 vision 调用）。"""
    with open(image_path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode("utf-8")
    ext = Path(image_path).suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    mime = mime_map.get(ext, "image/jpeg")
    return f"data:{mime};base64,{b64}"


def _find_living_room_image(images: list[dict], api_key: str) -> Optional[dict]:
    """
    使用 VISION_MODEL 从房源图片列表中识别客厅图片。
    一次性发送所有图片（最多8张），让模型选出最佳客厅照片。
    返回选中的 image dict（含 filename 和 abs_path），或 None。
    """
    if not images:
        logger.warning("房源无图片，无法识别客厅")
        return None

    # 限制图片数量避免 token 爆炸
    sample = images[:8]
    logger.info("正在从 %d 张房源图片中识别客厅...", len(sample))

    client = OpenAI(api_key=api_key, base_url=BASE_URL)

    # 构建多图消息
    content_parts: list[dict] = []
    content_parts.append({
        "type": "text",
        "text": (
            "以下是同一套房源的多张实拍照片。请找出哪一张是**客厅（living room）**的照片。\n"
            "判断标准：有沙发、茶几、电视柜、客厅布局的才算客厅。\n"
            "卧室、厨房、卫生间、走廊、外观都不算。\n\n"
            "请返回 JSON，格式：\n"
            '{"living_room_index": 数字(1-based), "confidence": "high/medium/low", "reason": "简短理由"}'
        ),
    })

    for i, img in enumerate(sample):
        data_url = _image_to_data_url(img["abs_path"])
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": data_url, "detail": "low"},
        })

    for attempt in range(1, COVER_MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=VISION_MODEL,
                messages=[{"role": "user", "content": content_parts}],
                temperature=0.1,
                max_tokens=200,
            )
            raw = resp.choices[0].message.content.strip()
            # 清理 markdown 代码块
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)
            result = json.loads(raw)
            idx = result.get("living_room_index", 1) - 1  # 转 0-based
            idx = max(0, min(idx, len(sample) - 1))
            confidence = result.get("confidence", "medium")
            reason = result.get("reason", "")
            logger.info("客厅识别完成: 第 %d 张 (%s), 置信度: %s — %s",
                        idx + 1, sample[idx]["filename"], confidence, reason)
            return sample[idx]
        except Exception as e:
            logger.warning("客厅识别失败 (attempt %d): %s", attempt, e)
            if attempt >= COVER_MAX_RETRIES:
                # 降级：取第一张图作为 fallback
                logger.info("客厅识别降级：使用第一张图片")
                return sample[0] if sample else None

    return sample[0] if sample else None


def _build_cover_prompt(property_data: dict) -> str:
    """根据房源数据构建封面图生成 prompt（英文，图像模型对英文理解更好）。
    Prompt 风格：精致高端但不失真实，让人有点进去看的欲望。"""
    district = property_data.get("district", "")
    sub = property_data.get("sub_district", "")
    rooms = property_data.get("rooms", "?")
    area = property_data.get("area_sqft", "?")
    price = property_data.get("price_wan", "?")
    renovation = property_data.get("renovation", "")
    has_lift = property_data.get("has_lift", False)
    highlights = property_data.get("highlights", [])

    location = f"{district}{sub}".strip() if district else "Hong Kong Island"
    room_desc = f"{rooms}-bedroom" if rooms else ""

    # 价格锚点 → 定位等级
    try:
        price_val = int(price) if str(price).isdigit() else 0
    except (ValueError, TypeError):
        price_val = 0

    if price_val >= 900:
        tier = "a premium luxury apartment in one of Hong Kong's most sought-after neighborhoods"
        vibe = "understated luxury — quality speaks through the space itself, not through flash"
    elif price_val >= 600:
        tier = "a high-quality comfortable home in a prime Hong Kong location"
        vibe = "warm and aspirational — the kind of place people bookmark as their goal"
    elif price_val >= 400:
        tier = "a solid, well-located Hong Kong apartment with great value"
        vibe = "cozy and inviting — practical but charming, a real home"
    else:
        tier = "a well-priced apartment in a desirable Hong Kong neighborhood"
        vibe = "bright and cheerful — compact but full of potential, a smart choice"

    # 装修加分
    reno_bonus = ""
    if renovation and any(kw in renovation for kw in ["装修", "翻新", "新裝", "全新"]):
        reno_bonus = "It has been recently renovated with fresh finishes — make those clean surfaces and new details shine. "

    # 电梯加分
    lift_bonus = ""
    if has_lift:
        lift_bonus = ""

    # 亮点提炼
    hl_text = ""
    if highlights:
        clean_hl = [h for h in highlights[:2] if len(h) < 30]
        if clean_hl:
            hl_text = f"Notable features: {', '.join(clean_hl)}. "

    prompt = (
        f"Transform this raw living room photo into a warm, beautifully staged real estate cover image.\n\n"
        f"CONTEXT:\n"
        f"This is {tier}.\n"
        f"Room type: {room_desc}, approximately {area} sq ft, priced around HKD {price}M.\n"
        f"Location: {location}, Hong Kong.\n"
        f"⚠️ The room is exactly {area} sq ft — this is a FIXED dimension. Do NOT make it look larger.\n"
        f"Desired vibe: {vibe}.\n"
        f"{reno_bonus}{hl_text}{lift_bonus}\n"
        f"STAGING BRIEF:\n"
        f"1. LIGHTING IS EVERYTHING — add warm, multi-layered light sources. Think table lamps glowing, a stylish floor lamp, warm overhead light. The room should feel COZY and illuminated, not dark or fluorescent.\n"
        f"2. Do NOT widen or expand the room. You may slightly adjust the camera angle to show a better composition of what's ALREADY visible — but the room boundaries stay exactly as they are. If you can only see one corner, stay in that corner.\n"
        f"3. Stage the room tastefully: add a rug to anchor the space if the floor feels bare, add curtain panels if windows are bare, add better lighting fixtures. Small accessories only — no major furniture additions.\n"
        f"4. Use a warm, cohesive color palette: cream whites, rich wood, soft muted greens from 2-3 well-placed plants.\n"
        f"5. The result should look like a professionally staged open house photo — warm, aspirational, and inviting.\n\n"
        f"HARD RULES:\n"
        f"- 🚫 DO NOT enlarge the room. {area} sq ft is the real size. Making it look bigger is a dealbreaker.\n"
        f"- If the original photo only shows part of the room, present that part beautifully — do NOT invent more space.\n"
        f"- NO text, NO watermarks, NO labels, NO Chinese characters.\n"
        f"- 2-3 plants max. Not a jungle.\n"
        f"- Must look like a REAL professional photograph, not 3D render or CGI.\n"
        f"- Keep original wall colors, flooring, windows, and room layout. No fake windows. No moving walls.\n"
        f"- Small staging accessories only (rug, lamp, curtains, throw pillows). No fake major furniture.\n"
    )

    return prompt


def _call_gemini_image_gen(
    image_path: str,
    prompt: str,
    api_key: str,
) -> Optional[bytes]:
    """
    调用 Gemini 原生图像生成 API（image-to-image）。
    发送客厅原图 + prompt，返回生成的封面图 bytes。
    使用 gemini-2.5-flash-image 模型。
    """
    # 读取并编码输入图片
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    ext = Path(image_path).suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    mime_type = mime_map.get(ext, "image/jpeg")

    url = COVER_GEN_API.format(model=COVER_IMAGE_MODEL)
    headers = {"Content-Type": "application/json"}
    params = {"key": api_key}

    body = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inlineData": {"mimeType": mime_type, "data": image_b64}},
            ],
        }],
        "generationConfig": {
            "responseModalities": ["IMAGE", "TEXT"],
            "temperature": COVER_TEMP,
        },
    }

    for attempt in range(1, COVER_MAX_RETRIES + 1):
        logger.info("封面图生成 第 %d/%d 次 (%s)...", attempt, COVER_MAX_RETRIES, COVER_IMAGE_MODEL)
        try:
            resp = requests.post(url, headers=headers, params=params, json=body, timeout=120)
            if resp.status_code != 200:
                logger.error("Gemini 图像 API 返回 %d: %s", resp.status_code, resp.text[:500])
                if attempt >= COVER_MAX_RETRIES:
                    return None
                continue

            data = resp.json()
            # 解析响应，提取图片
            candidates = data.get("candidates", [])
            if not candidates:
                logger.warning("Gemini 图像 API 返回空 candidates")
                if attempt >= COVER_MAX_RETRIES:
                    return None
                continue

            for candidate in candidates:
                parts = candidate.get("content", {}).get("parts", [])
                for part in parts:
                    if "inlineData" in part:
                        img_b64 = part["inlineData"].get("data", "")
                        if img_b64:
                            logger.info("封面图生成成功，大小: %.1f KB", len(img_b64) * 3 / 4 / 1024)
                            return base64.b64decode(img_b64)
                    # 打印文本部分用于调试
                    if "text" in part:
                        logger.debug("Gemini 文本响应: %s", part["text"][:200])

            logger.warning("Gemini 图像 API 响应中未找到图片数据")
            if attempt >= COVER_MAX_RETRIES:
                return None

        except requests.exceptions.Timeout:
            logger.error("Gemini 图像 API 超时 (attempt %d)", attempt)
        except Exception as e:
            logger.error("Gemini 图像 API 异常 (attempt %d): %s", attempt, e)

    return None


def generate_cover(
    property_data: dict,
    output_dir: Path,
    run_id: str,
    api_key: str,
) -> Optional[Path]:
    """
    封面图生成主流程：
    1. 从房源图片中识别客厅照片
    2. 用 Gemini 原生图像 API 基于客厅照片生成封面图
    3. 保存到输出目录

    返回生成的封面图路径，或 None（失败时不影响笔记生成）。
    """
    images = property_data.get("images", [])
    if not images:
        logger.warning("房源无图片，跳过封面图生成")
        return None

    # Step 1: 找客厅
    living_room = _find_living_room_image(images, api_key)
    if not living_room:
        logger.warning("未找到客厅图片，跳过封面图生成")
        return None

    logger.info("选中客厅图片: %s", living_room["filename"])

    # Step 2: 构建 prompt
    cover_prompt = _build_cover_prompt(property_data)
    logger.debug("封面图 prompt 长度: %d 字", len(cover_prompt))

    # Step 3: 调用 Gemini 生成
    image_data = _call_gemini_image_gen(living_room["abs_path"], cover_prompt, api_key)
    if not image_data:
        logger.warning("封面图生成失败")
        return None

    # Step 4: 保存封面图 + 原图副本（记录素材来源）
    safe_name = sanitize_filename(property_data.get("name", "untitled"))
    target_dir = Path(output_dir) / run_id / "pre-published" if output_dir else OUTPUTS_DIR / run_id / "pre-published"
    target_dir.mkdir(parents=True, exist_ok=True)

    cover_path = target_dir / f"{safe_name}_cover.png"
    cover_path.write_bytes(image_data)
    logger.info("封面图已保存: %s (%.1f KB)", cover_path, len(image_data) / 1024)

    # 保存原图副本，记录封面图是拿哪张照片生成的
    import shutil
    src_ext = Path(living_room["abs_path"]).suffix.lower()
    source_copy = target_dir / f"{safe_name}_cover_原图{src_ext}"
    shutil.copy2(living_room["abs_path"], source_copy)
    logger.info("封面素材原图已保存: %s", source_copy.name)

    return cover_path


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
    price_m = re.search(r"\$(\d+)\s*[万萬]", header)
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


def save_strategy(
    strategy_md: str,
    property_name: str,
    persona: str = "amateur",
    run_id: Optional[str] = None,
    output_dir: Optional[Path] = None,
    property_data: Optional[dict] = None,
    analyzed_notes: Optional[list[dict]] = None,
) -> Path:
    """保存行文思路 Markdown 到 {run_id}/pre-published/，末尾自动拼接关联素材。"""
    base = Path(output_dir) if output_dir else OUTPUTS_DIR
    run_id = run_id or get_run_id()
    target_dir = base / run_id / "pre-published"
    target_dir.mkdir(parents=True, exist_ok=True)

    safe_name = sanitize_filename(property_name)
    output_path = target_dir / f"{safe_name}_{persona}_strategy.md"

    # Append 关联素材 section
    full_content = strategy_md + _build_source_refs_section(output_path, property_data, analyzed_notes)

    output_path.write_text(full_content, encoding="utf-8")
    logger.info("行文思路已保存: %s", output_path)
    return output_path


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
# LLM 调用
# ═══════════════════════════════════════════════════════════════

def call_llm(user_prompt: str, persona: str = "amateur") -> NoteContent:
    """调用 LLM 生成笔记，带重试和降级策略。"""
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    persona_cfg = PERSONA_CONFIG.get(persona, PERSONA_CONFIG["amateur"])
    system_prompt = persona_cfg["system_prompt"]

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info("第 %d/%d 次生成中 (%s | %s)...", attempt, MAX_RETRIES, MODEL, persona_cfg["label"])
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.8,
                max_tokens=8192,
            )
            raw = resp.choices[0].message.content.strip()
            logger.debug("原始响应前 200 字: %s", raw[:200])

            return _parse_response(raw)

        except json.JSONDecodeError as e:
            logger.warning("JSON 解析失败 (attempt %d): %s", attempt, e)
            if attempt >= MAX_RETRIES:
                # 降级模型试一次
                fallback_model = "gemini-3.1-flash-lite"
                logger.info("JSON 解析连续失败，降级模型: %s", fallback_model)
                try:
                    resp = client.chat.completions.create(
                        model=fallback_model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.8,
                        max_tokens=8192,
                    )
                    raw = resp.choices[0].message.content.strip()
                    return _parse_response(raw)
                except Exception as e2:
                    logger.error("降级模型也失败: %s", e2)
                    raise
        except Exception as e:
            logger.error("API 调用异常 (attempt %d): %s", attempt, e)
            if attempt >= MAX_RETRIES:
                # 降级模型试一次
                fallback_model = "gemini-3.1-flash-lite"
                logger.info("降级模型: %s", fallback_model)
                try:
                    resp = client.chat.completions.create(
                        model=fallback_model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.8,
                        max_tokens=8192,
                    )
                    raw = resp.choices[0].message.content.strip()
                    return _parse_response(raw)
                except Exception as e2:
                    logger.error("降级模型也失败: %s", e2)
                    raise

    raise RuntimeError(f"LLM 生成失败，已重试 {MAX_RETRIES} 次")


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

    return NoteContent(
        hook_title=data.get("hook_title", ""),
        main_content=data.get("main_content", ""),
        interactive_question=data.get("interactive_question", ""),
        seo_tags=raw_tags,
        cover_suggestion=data.get("cover_suggestion", ""),
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

def _build_source_refs_section(
    output_md_path: Path,
    property_data: Optional[dict] = None,
    analyzed_notes: Optional[list[dict]] = None,
    strategy_path: Optional[Path] = None,
    cover_path: Optional[Path] = None,
) -> str:
    """构建「📁 关联素材」Markdown 章节，生成相对于输出 md 文件的路径以便 Ctrl+点击跳转。"""
    lines = ["", "---", "", "## 📁 关联素材（Ctrl+点击跳转）", ""]

    def rel(target: str) -> str:
        """将绝对路径转为相对于 output_md_path 所在目录的路径。"""
        try:
            return str(Path(os.path.relpath(target, output_md_path.parent)))
        except ValueError:
            return target  # fallback: 跨盘符时保留绝对路径

    # ── 封面图 ──
    if cover_path:
        lines.append("### 🎨 AI 生成封面图")
        lines.append(f'- [查看封面图]({rel(str(cover_path.resolve()))})')
        # 查找同名的原图副本
        cover_dir = cover_path.parent
        for pattern in [f"{cover_path.stem}_原图.*"]:
            for src in cover_dir.glob(pattern):
                lines.append(f'- **封面素材原图**: [{src.name}]({rel(str(src.resolve()))})')
        lines.append("")

    # ── 本房源素材 ──
    if property_data:
        lines.append("### 本房源素材")
        if property_data.get("info_md_path"):
            lines.append(f'- **房源信息**: [查看 info.md]({rel(property_data["info_md_path"])})')
        images = property_data.get("images", [])
        if images:
            lines.append(f"- **房源图片** ({len(images)} 张):")
            for img in images:
                lines.append(f'  - [{img["filename"]}]({rel(img["abs_path"])})')
        lines.append("")

    # ── 参考爆款笔记 ──
    if analyzed_notes:
        lines.append("### 参考爆款笔记")
        for note in analyzed_notes[:3]:  # 最多列 3 条
            if note.get("source_absolute_path"):
                lines.append(f'- **Agent2 分析**: [{note["source_file"]}]({rel(note["source_absolute_path"])})')
            if note.get("note_url"):
                lines.append(f'- **小红书原文**: [{note.get("note_url","原文链接")[:60]}...]({note["note_url"]})')
        lines.append("")

    # ── 行文思路（仅 pre-published） ──
    if strategy_path:
        lines.append("### 行文思路")
        lines.append(f"- [查看策略规划]({rel(str(strategy_path.resolve()))})")
        lines.append("")

    return "\n".join(lines)


def convert_to_markdown(content: NoteContent) -> str:
    """将 NoteContent 转为可发布的 Markdown 字符串。"""
    tags = " ".join(f"#{t}" for t in content.seo_tags) if content.seo_tags else ""

    lines = [
        f"# {content.hook_title}",
        "",
        content.main_content.replace("\\n", "\n"),
        "",
        "---",
        "",
        content.interactive_question,
        "",
    ]
    if tags:
        lines.append(f"**标签**: {tags}")
        lines.append("")
    if content.cover_suggestion:
        lines.append("---")
        lines.append("")
        lines.append(f"🎨 **封面图建议**: {content.cover_suggestion}")
        lines.append("")

    return "\n".join(lines)


def save_pre_published(
    content: NoteContent,
    property_name: str,
    persona: str = "amateur",
    run_id: Optional[str] = None,
    output_dir: Optional[Path] = None,
    property_data: Optional[dict] = None,
    analyzed_notes: Optional[list[dict]] = None,
    strategy_path: Optional[Path] = None,
    cover_path: Optional[Path] = None,
) -> Path:
    """将生成的笔记转为 Markdown 存入 {run_id}/pre-published/，末尾自动拼接关联素材。"""
    base = Path(output_dir) if output_dir else OUTPUTS_DIR
    run_id = run_id or get_run_id()
    target_dir = base / run_id / "pre-published"
    target_dir.mkdir(parents=True, exist_ok=True)

    safe_name = sanitize_filename(property_name)
    output_path = target_dir / f"{safe_name}_{persona}.md"

    md_content = convert_to_markdown(content)

    # Append 关联素材 + 行文思路
    extra_lines = _build_source_refs_section(output_path, property_data, analyzed_notes, strategy_path, cover_path)
    full_content = md_content + extra_lines

    output_path.write_text(full_content, encoding="utf-8")
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
    skip_cover: bool = False,
) -> NoteContent:
    """主入口（三阶段管线）：策略规划 → 封面图生成 → 行文思路 MD → 笔记创作 → 草稿 + MD 发布稿。

    支持三种 Persona:
      - "amateur": 素人视角，围绕具体房源记录分享
      - "agent": 中介视角，推广房源引导私信
      - "discussion": 讨论帖，纯素人观点/经历分享，不需要房源数据，不生成封面
    """
    persona_cfg = PERSONA_CONFIG.get(persona, PERSONA_CONFIG["amateur"])
    run_id = run_id or get_run_id()
    logger.info("=" * 50)
    logger.info("  Agent 3 — 爆款图文生成器 启动")
    logger.info("  Persona: %s | Model: %s | Run: %s", persona_cfg["label"], MODEL, run_id)
    logger.info("=" * 50)

    # ── discussion 模式：不需要房源，跳过封面和策略，直接创作讨论帖 ──
    if persona == "discussion":
        logger.info("讨论帖模式 — 无需房源数据，直接创作")
        cover_path = None
        strategy_md = ""
        strategy_path = None
        analyzed_notes: list[dict] = []

        # 构建讨论帖 prompt
        discussion_prompt = _build_discussion_prompt()

        logger.info("─" * 40)
        logger.info("【创作讨论帖】...")
        try:
            result = call_llm(discussion_prompt, persona=persona)
        except Exception as e:
            logger.error("生成失败: %s", e)
            raise

        draft_path = save_draft(result, persona=persona, run_id=run_id, output_dir=output_dir)
        ts = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M%S")
        safe_name = f"discuss_{ts}"
        md_path = save_pre_published(result, property_name=safe_name,
                                     persona=persona, run_id=run_id, output_dir=output_dir,
                                     property_data=None, analyzed_notes=analyzed_notes,
                                     strategy_path=None, cover_path=None)

        logger.info("─" * 50)
        logger.info("生成完成")
        logger.info("  标题: %s", result.hook_title)
        logger.info("  标签: %s", ", ".join(result.seo_tags))
        logger.info("  互动: %s", result.interactive_question)
        logger.info("  MD: %s", md_path)
        return result

    sop = sop_text or load_sop()
    refs = reference_notes or load_reference_notes()
    prop = property_data or load_property_raw()

    summary = _summarize_property(prop)
    logger.info("房源: %s", summary)

    # ═══ 阶段 0：封面图生成（在策略规划之前，不依赖 LLM 笔记输出）═══
    cover_path: Optional[Path] = None
    if not skip_cover:
        logger.info("─" * 40)
        logger.info("【阶段 0/2】封面图生成...")
        try:
            cover_path = generate_cover(
                property_data=prop,
                output_dir=Path(output_dir) if output_dir else OUTPUTS_DIR,
                run_id=run_id,
                api_key=API_KEY,
            )
            if cover_path:
                logger.info("封面图已生成: %s", cover_path)
            else:
                logger.warning("封面图生成失败，继续生成笔记...")
        except Exception as e:
            logger.error("封面图生成异常，继续生成笔记: %s", e)
    else:
        logger.info("【阶段 0/2】封面图生成已跳过 (--skip-cover)")

    strategy_md = ""
    strategy_path: Optional[Path] = None
    analyzed_notes: list[dict] = []

    if not skip_strategy:
        # ═══ 阶段 1：策略规划 ═══
        logger.info("─" * 40)
        logger.info("【阶段 1/2】行前思路规划...")
        audience_segments = load_audience_segments()
        analyzed_notes = load_analyzed_notes(run_id=run_id)
        strategy_prompt = build_strategy_prompt(prop, audience_segments, analyzed_notes, persona)
        logger.info("策略 Prompt 构建完成，长度: %d 字", len(strategy_prompt))

        try:
            strategy_md = call_llm_strategy(strategy_prompt)
        except Exception as e:
            logger.error("策略规划失败，将继续直接生成: %s", e)
            strategy_md = ""

        if strategy_md:
            strategy_path = save_strategy(strategy_md, property_name=prop.get("name", "untitled"),
                                          persona=persona, run_id=run_id, output_dir=output_dir,
                                          property_data=prop, analyzed_notes=analyzed_notes)
            logger.info("行文思路已保存: %s", strategy_path)
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
                                 persona=persona, run_id=run_id, output_dir=output_dir,
                                 property_data=prop, analyzed_notes=analyzed_notes,
                                 strategy_path=strategy_path, cover_path=cover_path)

    logger.info("─" * 50)
    logger.info("生成完成")
    logger.info("  标题: %s", result.hook_title)
    logger.info("  标签: %s", ", ".join(result.seo_tags))
    logger.info("  互动: %s", result.interactive_question)
    logger.info("  封面建议: %s", result.cover_suggestion[:100] if result.cover_suggestion else "(无)")
    logger.info("  正文预览: %s...", result.main_content[:100].replace("\n", " "))
    logger.info("  草稿: %s", draft_path)
    logger.info("  MD: %s", md_path)

    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent 3 — 小红书爆款图文生成器")
    parser.add_argument(
        "--persona",
        choices=["amateur", "agent", "discussion"],
        default="amateur",
        help="写作视角: amateur=素人记录分享, agent=中介推广获客, discussion=纯讨论帖(无需房源)",
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
        help="跳过策略规划阶段，直接创作（保持向后兼容）",
    )
    parser.add_argument(
        "--skip-cover",
        action="store_true",
        help="跳过封面图生成阶段（保持向后兼容）",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        args = _parse_args()
        count = args.count

        # discussion 模式：无需房源数据，直接生成 N 篇讨论帖
        if args.persona == "discussion":
            for i in range(count):
                logger.info("\n▸ 第 %d/%d 篇讨论帖", i + 1, count)
                run(property_data=None, persona="discussion", run_id=args.run_id,
                    output_dir=args.output_dir, skip_strategy=True, skip_cover=True)
        else:
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
                    output_dir=args.output_dir, skip_strategy=args.skip_strategy,
                    skip_cover=args.skip_cover)

    except KeyboardInterrupt:
        logger.info("用户中断")
    except Exception as e:
        logger.error("致命错误: %s", e, exc_info=True)
        sys.exit(1)
