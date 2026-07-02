"""
Agent 4 — 素人账号爆款笔记生成器 (Amateur Viral Writer)

学习 Agent 2 拆解出的真实素人买房/租房/看房笔记结构，
生成新的"素人账号"风格图文笔记文案（仅文本，暂不生成封面图/配图）。

输入: Agent 2 对真实爆款素人笔记的拆解 JSON (04_outputs/agent4_training/analyzed/*.json)
输出: NoteContent JSON 草稿 + Markdown 发布稿
"""

import argparse
import json
import logging
import random
import re
import sys
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
FALLBACK_MODEL = "gemini-3.1-flash-lite"
MAX_RETRIES = 3
MAX_TITLE_LEN = 25  # 小红书标题上限（字符数）

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUTS_DIR = PROJECT_ROOT.parent / "04_outputs"
SYSTEM_PROMPT_PATH = SCRIPT_DIR / "system_prompt.txt"

# Agent 2 对真实素人爆款笔记的拆解结果（教学素材）
# 扫描 04_outputs 下所有 analyzed 子目录，自动聚合
TRAINING_ANALYZED_DIR = OUTPUTS_DIR  # 兜底；实际由 load_reference_notes 扫描


# ═══════════════════════════════════════════════════════════════
# Pydantic 输出 Schema
# ═══════════════════════════════════════════════════════════════

class NoteContent(BaseModel):
    hook_title: str = Field(description="标题，带钩子，12-24字，绝不超过25字（小红书标题上限）")
    main_content: str = Field(description="正文，口语短句换行")
    interactive_question: str = Field(description="结尾互动提问，引发评论而非引导私信")
    seo_tags: list[str] = Field(description="SEO标签，5-10个")
    image_suggestions: list[str] = Field(
        default_factory=list,
        description="配图建议，3-6条，每条描述一张真实生活实拍该拍什么内容（不生成图片）",
    )
    persona_note: str = Field(default="", description="本篇采用的素人子人设/场景，一句话说明")


# ═══════════════════════════════════════════════════════════════
# 四类素人笔记母题
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# 房源多角度模式：针对同一套具体房源，用 4 种角度写作
# ═══════════════════════════════════════════════════════════════

PROPERTY_ANGLES: dict[str, str] = {
    # 大类1 忍痛放弃类
    "放弃叙事":    "A1：忍痛放弃叙事版",
    "意外种草":    "A2：意外种草版",
    "纠结对比":    "A3：纠结对比/求建议版",
    "决赛圈对比":  "A4：多盘决赛圈横向对比版",
    "住得下吗":    "A5：家庭住得下求助版",
    "召唤过来人":  "A6：召唤过来人现身说法版",
    # 大类2 长什么样类
    "优缺点总结":  "B1：优缺点直白总结版",
    "看房日记":    "B2：看楼日记+互动提问版",
    "看房踩坑":    "B3：区域踩坑横扫版",
    "长啥样开箱":  "B4：地名+价格开箱（短文案）版",
    "单价你会买吗": "B5：单价换算·你会买吗版",
    # 大类3 询问类（仅此一个角度）
    "预算现实吗":  "C1：预算够不够·现实吗版",
}

# 对比类角度：必须拿多套【真实房源】横向对比，禁止 LLM 虚构对照盘。
# value = 参与对比的真实房源总数（含主房源）。脚本会自动从主房源的同级目录补齐其余真实房源。
COMPARISON_ANGLES: dict[str, int] = {
    "纠结对比":   2,   # A3 两套二选一
    "决赛圈对比": 3,   # A4 决赛圈 2-3 套
}

ANGLE_CATEGORY_FOLDER: dict[str, str] = {
    # 大类1 忍痛放弃类
    "放弃叙事":    "1_忍痛放弃",
    "意外种草":    "1_忍痛放弃",
    "纠结对比":    "1_忍痛放弃",
    "决赛圈对比":  "1_忍痛放弃",
    "住得下吗":    "1_忍痛放弃",
    "召唤过来人":  "1_忍痛放弃",
    # 大类2 长什么样类
    "优缺点总结":  "2_长什么样",
    "看房日记":    "2_长什么样",
    "看房踩坑":    "2_长什么样",
    "长啥样开箱":  "2_长什么样",
    "单价你会买吗": "2_长什么样",
    # 大类3 询问类
    "预算现实吗":  "3_询问",
}


# ═══════════════════════════════════════════════════════════════
# 中介人设库（供 Agent5 反馈后的修改稿使用，制造跨笔记"交叉认证"记忆点）
# ═══════════════════════════════════════════════════════════════

AGENT_PERSONA = """小姐姐人设细节（每篇挑1个细节自然带出，不要堆砌）：
- 会主动指出墙角水痕、外墙维修计划、大厦验楼年限等"内行才会注意"的细节
- 不会一直push，甚至会劝客户"再考虑一下/不要冲动"
- 对预算低的客户也很有耐心，不会因为总价低就敷衍
- 对片区和楼盘情况很熟，但表达方式是闲聊式的，不是背资料
- 称呼统一用「小姐姐」，不需要 @任何账号

绝对禁止：
- 禁止小姐姐拿出任何工具（测距仪/卷尺/Excel/计算器）
- 禁止小姐姐当场算账/拉表/做预算
- 禁止「差点踩坑→小姐姐救场→感恩」三段式
- 禁止用「耐心」「靠谱」「专业」等空泛形容词直接夸小姐姐"""


# ═══════════════════════════════════════════════════════════════
# 非房源引流笔记：六大内容类型（不介绍具体房源，用生活/知识内容吸引潜在客户）
# ═══════════════════════════════════════════════════════════════

NON_PROPERTY_TYPES: dict[str, str] = {
    "避坑指南": "香港置业/租房避坑知识科普",
    "区域生活测评": "香港某区域的生活体验点评",
    "买房全流程科普": "香港买房完整流程教学",
    "看房复盘日记": "看了若干套楼后的复盘总结",
    "CitywalkHK探区": "步行探索香港某区域，带出居住环境感受",
    "香港楼市行情评论": "对近期香港楼市动态的个人点评",
}

# 小红书真实帖子原型文件 — 优先参考
XHS_PROTOTYPES_PATH = SCRIPT_DIR.parent / "scratch" / "xhs_nonproperty_prototypes.md"

# 类型名 → 原型文件中对应 section 的匹配关键词
PROTOTYPE_SECTION_MAP: dict[str, str] = {
    "避坑指南": "类型1：避坑指南",
    "区域生活测评": "类型2：区域生活测评",
    "买房全流程科普": "类型3：买房全流程科普",
    "看房复盘日记": "类型4：看房复盘日记",
    "CitywalkHK探区": "类型5：CitywalkHK探区",
    "香港楼市行情评论": "类型6：香港楼市行情评论",
}


CATEGORIES: dict[str, dict] = {
    "买房经历": {
        "label": "买房经历 — 记录自己买/正在买一套房的过程",
        "prompt": (
            "围绕「我买了/正在买一套房」写一篇真实记录。"
            "可以讲：为什么决定买、看了多久、纠结过什么（预算/区域/楼龄/装修）、"
            "最后选了哪种户型/区域、签约或收楼时的真实感受。"
            "不需要写出具体楼盘名或具体地址，但要有真实的细节（价格区间、面积、楼层、装修状况等）。"
        ),
    },
    "租房体验": {
        "label": "租房体验 — 点评/分享自己现在租的房子",
        "prompt": (
            "围绕「我现在租的这个房子怎么样」写一篇真实点评。"
            "可以讲：租金多少、面积多大、布局如何、采光/隔音/管理怎么样、"
            "性价比值不值、推荐还是劝退、住进去之后的真实感受。"
            "适合港漂/港硕/打工人视角。"
        ),
    },
    "看房日记": {
        "label": "看房日记 — 分享最近看房的经历和细节",
        "prompt": (
            "围绕「我最近看了几套房」写一篇看房日记。"
            "可以讲：看了几套、某一套印象最深的细节（朝向/楼层/装修/中介的话/业主的态度）、"
            "最后选择、错过或还在纠结的原因。可以有具体的吐槽和意外惊喜。"
        ),
    },
    "生活分享": {
        "label": "生活分享 — 不强调买/租决策，纯粹分享当下居住状态",
        "prompt": (
            "围绕「我现在的居住状态/小窝/小区生活」写一篇生活化分享。"
            "不强调买房或租房的决策过程，而是分享当下的居住感受——"
            "空间布置、生活方式的转变、小区或附近环境带来的小确幸或小吐槽。"
        ),
    },
}


# ═══════════════════════════════════════════════════════════════
# 日志
# ═══════════════════════════════════════════════════════════════

def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("Agent4.AmateurViral")
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
# System Prompt
# ═══════════════════════════════════════════════════════════════

def load_system_prompt() -> str:
    if SYSTEM_PROMPT_PATH.exists():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    logger.warning("system_prompt.txt 不存在，使用最小化兜底 prompt")
    return "你是一个在香港生活的普通人，正在小红书上分享自己的居住经历。严格输出 JSON。"


# ═══════════════════════════════════════════════════════════════
# 参考范文加载（来自 Agent 2 对真实素人爆款笔记的拆解）
# ═══════════════════════════════════════════════════════════════

def load_reference_notes(analyzed_dir: Optional[Path] = None) -> list[dict]:
    """加载 Agent 2 拆解出的真实素人笔记 JSON，作为参考范文。

    默认扫描 04_outputs 下所有 analyzed 子目录，自动聚合全部真实笔记分析。
    """
    notes: list[dict] = []
    seen_ids: set[str] = set()  # 按 note_id 去重

    sources: list[Path] = []
    if analyzed_dir is not None:
        sources = [analyzed_dir]
    else:
        # 扫描 04_outputs 下所有 analyzed 子目录
        if OUTPUTS_DIR.exists():
            sources = sorted(d for d in OUTPUTS_DIR.rglob("analyzed") if d.is_dir())

    if not sources:
        logger.warning("参考范文目录不存在，将无参考素材生成（质量会明显下降）")
        return notes

    for src_dir in sources:
        for f in sorted(src_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if not data:
                continue
            # 去重
            nid = data.get("note_id", f.stem)
            if nid in seen_ids:
                continue
            seen_ids.add(nid)
            data["_source_file"] = f.name
            notes.append(data)

    logger.info("加载参考范文: %d 篇 (来自 %d 个 analyzed 目录)", len(notes), len(sources))
    return notes


def _pick_reference_notes(reference_notes: list[dict], k: int = 3) -> list[dict]:
    """随机抽取 k 条参考范文，避免每次都用同一批。"""
    if len(reference_notes) <= k:
        return reference_notes
    return random.sample(reference_notes, k)


# ═══════════════════════════════════════════════════════════════
# User Prompt 构建
# ═══════════════════════════════════════════════════════════════

def _summarize_property(prop: dict) -> str:
    """根据房源数据生成简要文字摘要，供 prompt 使用。"""
    parts = []
    district = prop.get("sub_district") or prop.get("district") or ""
    if district:
        parts.append(district)
    rooms = prop.get("rooms")
    if rooms is not None:
        parts.append("开放式" if rooms == 0 else f"{rooms}房")
    if prop.get("area_sqft"):
        parts.append(f"实用{prop['area_sqft']}呎")
    if prop.get("price_wan"):
        parts.append(f"{prop['price_wan']}万")
    if prop.get("floor"):
        parts.append(f"{prop['floor']}楼")
    if prop.get("lift_type"):
        parts.append(prop["lift_type"])
    if prop.get("mtr_station"):
        mtr = f"近{prop['mtr_station']}站"
        if prop.get("mtr_walk_min"):
            mtr += f"（步行约{prop['mtr_walk_min']}分钟）"
        parts.append(mtr)
    if prop.get("school_net_name"):
        parts.append(prop["school_net_name"])
    if prop.get("renovation"):
        parts.append(prop["renovation"])
    return " | ".join(parts)


def _prop_block(prop: dict) -> str:
    """把单套房源渲染成 prompt 里的一段（摘要 + 完整数据）。"""
    summary = _summarize_property(prop)
    data = json.dumps(
        {k: v for k, v in prop.items() if k not in ("images", "info_md_path", "property_dir")},
        ensure_ascii=False, indent=2)
    head = f"{summary}\n" if summary else ""
    return f"{head}{data}"


def build_property_angle_prompt(
    prop: dict,
    angle_key: str,
    reference_notes: list[dict],
    compare_props: Optional[list[dict]] = None,
) -> str:
    """构建"房源多角度模式"的 user prompt：针对具体房源 + 指定角度。

    compare_props: 对比类角度（COMPARISON_ANGLES）的其余【真实房源】，与 prop 一起横向对比。
    """
    summary = _summarize_property(prop)
    angle_label = PROPERTY_ANGLES[angle_key]

    if angle_key in COMPARISON_ANGLES and compare_props:
        all_props = [prop] + list(compare_props)
        blocks = []
        for i, p in enumerate(all_props, 1):
            blocks.append(f"── 房源{i}：{p.get('name', '')} ──\n{_prop_block(p)}")
        parts: list[str] = [f"""【本篇要横向对比的真实房源（共 {len(all_props)} 套，全部是我们的真实在售房源）】
{chr(10).join(blocks)}

【本篇指定角度】
{angle_label}
请严格按 system prompt "房源多角度模式" 中该角度的写法来写，不要混用其他角度的结构，
也不要使用"四类素人笔记母题"的结构。

【对比类铁律——违反即不合格】
- 只能在上面这 {len(all_props)} 套真实房源里做对比/纠结/决赛圈，**严禁虚构任何其它楼盘**（不许编楼盘名、价格、面积、会所、校网等任何数据）。
- 每套的地点、房型、总价、卖点、缺点都必须严格来自上面对应房源的数据，不能张冠李戴、不能夸大编造。
- 可以提到"本来想要太古城/某梦想区但预算够不到"这类**只作背景、不作对比项**的一句话铺垫，但真正拿来纠结/PK 的候选，必须且只能是上面这几套真实房源。"""]
    else:
        parts = [f"""【本次看房的房源信息】
{summary}

【完整数据】
{json.dumps({k: v for k, v in prop.items() if k not in ("images", "info_md_path", "property_dir")}, ensure_ascii=False, indent=2)}

【本篇指定角度】
{angle_label}
请严格按 system prompt "房源多角度模式" 中该角度的写法来写，不要混用其他角度的结构，
也不要使用"四类素人笔记母题"的结构。"""]

    picked = _pick_reference_notes(reference_notes, k=2)
    if picked:
        parts.append("\n【参考范文（真实素人笔记的拆解结果，仅供学习语气/结构/钩子手法，不要照抄措辞或具体细节）】")
        for i, note in enumerate(picked, 1):
            text_analysis = note.get("text_analysis", {})
            parts.append(
                f"\n范文{i}：\n"
                f"发帖视角: {text_analysis.get('persona_perspective', '')}\n"
                f"钩子类型: {text_analysis.get('hook_type', '')}\n"
                f"可复用模板: {note.get('reusable_template', '')[:300]}"
            )

    # 不同角度的字数规则
    angle_extra = ""
    if angle_key == "长啥样开箱":
        word_rule = "素人口吻，60-120字短开箱，就几句话，绝对不要写长"
    elif angle_key == "预算现实吗":
        word_rule = "素人口吻，60-120字，短。全程是『我想买X房』的需求口吻，绝不能写成去看了某套房/某楼盘"
        angle_extra = """
【本篇额外强制（预算现实吗）——违反即不合格】
- 上面的房源数据**只用来提取三样**：地点(区/片区)、房型(几房)、大致总价。其余精确参数（呎数/楼龄/楼层/到地铁几分钟/校网编号/装修状态）一律不要写进笔记。
- 这不是看房笔记！绝对禁止"今天去看了/刚去看了/刚好看到一套/去XX盘看了"这类看房叙述，也不要出现任何具体楼盘名字、不要提带看小姐姐。
- 通篇是"我想在<地点>、用<预算>、买<房型>"的需求口吻，可以再带一两个**笼统生活化**的偏好（如想要电梯、离地铁近一点、楼别太旧、采光好点），但偏好也要笼统，不准报精确数字。
- 然后客观问大家这个预算+地点+房型现不现实。短、自然、不刻意。
- 【结尾反问必须原创、每篇不同】禁止套用"成功上车或者放弃换片区的朋友都可以来评论区说理由"这类固定模板句，换一种真实自然的问法（例：这价现在还够上车吗 / 是我预期太美好了吗 / 蹲一个同区上岸的说说 / 这么点钱在这区是不是想多了）。
- 【全篇只能有一个问句结尾】正文里不要先抛一个问句、结尾又单起一行再问一次；疑问只保留结尾那一句。"""
    elif angle_key == "单价你会买吗":
        word_rule = "素人口吻，120-200字，聚焦一个点讲清楚不啰嗦"
    else:
        word_rule = "素人口吻，180-320字，像朋友圈不像文章"

    parts.append(f"""
【任务】
基于以上房源信息和指定角度，写一篇全新的小红书图文笔记。
{angle_extra}
【写作铁律】
- {word_rule}
- 标题12-24字，绝对不能超过25字（小红书标题上限就是25字，超了会被截断），带具体数字/反差，有搜索流量
- 如果提带看的人，统一用「小姐姐」，不需要 @任何账号
- 小姐姐只能作为背景一笔带过（至多1-2句），不能成为叙事核心
- 禁止写小姐姐拿出任何工具（测距仪/卷尺/Excel）
- 禁止写小姐姐当场算账/拉表
- 禁止「差点踩坑→小姐姐救场→感恩」三段式
- 禁止用「耐心」「靠谱」「专业」「实在」「良心」等空泛形容词夸小姐姐
- 禁止「#靠谱中介」「#诚实中介」「#中介推荐」「#靠谱小姐姐」等标签
- 严禁出现「打PM」「私信我」「发资料」「发这套房子的资料」等任何推销话术或变体
- 严禁出现 system prompt 禁用词清单里的浮夸词（家人们/姐妹们/谁懂/绝绝子/绝了/YYDS/天花板/闭眼入/真香/宝藏 等）
- 笔记必须是纯素人分享，结尾只能是自然互动提问
直接输出 JSON。""")

    return "\n".join(parts)


def load_prototype_section(type_name: str) -> str:
    """从原型文件中提取指定内容类型的真实帖子参考片段。"""
    if not XHS_PROTOTYPES_PATH.exists():
        logger.warning("原型文件不存在: %s", XHS_PROTOTYPES_PATH)
        return ""
    section_key = PROTOTYPE_SECTION_MAP.get(type_name, type_name)
    content = XHS_PROTOTYPES_PATH.read_text(encoding="utf-8")
    # 找到对应 section
    marker = f"## {section_key}"
    idx = content.find(marker)
    if idx == -1:
        # 尝试模糊匹配
        for key, val in PROTOTYPE_SECTION_MAP.items():
            if type_name in key or key in type_name:
                idx = content.find(f"## {val}")
                if idx != -1:
                    break
    if idx == -1:
        logger.warning("原型文件中找不到类型: %s", type_name)
        return ""
    # 提取该 section 到下一个 ## 之前
    next_section = content.find("\n## ", idx + len(marker))
    if next_section == -1:
        next_section = content.find("\n---", idx + len(marker))
    if next_section == -1:
        section = content[idx:]
    else:
        section = content[idx:next_section]
    return section.strip()


def build_non_property_prompt(type_name: str, brief_section: dict, reference_notes: list[dict]) -> str:
    """构建「非房源模式」的 user prompt：按 Agent5 简报写生活/知识类引流笔记。"""
    type_label = NON_PROPERTY_TYPES.get(type_name, type_name)
    why = brief_section.get("why_it_works", "")
    requirements = brief_section.get("key_requirements", [])
    integration_hint = brief_section.get("agent_integration_hint", "")
    example_sketch = brief_section.get("example_sketch", "")
    req_text = "\n".join(f"- {r}" for r in requirements)

    # 判断是否允许出现中介（Citywalk 和 纯生活类不允许）
    forbid_agent = ("完全隐藏" in integration_hint)

    agent_rule = ""
    if forbid_agent:
        agent_rule = ("\n【中介禁令】本篇全文禁止出现「中介」「经纪」「带看」「Agent」「小姐姐」"
                      "等任何房产中介相关字眼，违者不合格。")
    else:
        agent_rule = (f"\n【小姐姐融入-严格限幅】{integration_hint}。"
                      "全文最多提到1次，用「小姐姐」称呼。"
                      "小姐姐不能是救场者或数据提供者角色，不能拿出任何工具或现场算账。")

    # ── 加载真实 XHS 原型作为首要参考 ──
    prototype_section = load_prototype_section(type_name)

    parts: list[str] = [f"""【本次任务】写一篇「{type_name}」类小红书图文笔记。

【类型说明】{type_label}
"""]
    if prototype_section:
        parts.append(f"""
【⚠️ 最重要的参考——小红书真实帖子原型】
以下是该类型在小红书上的真实爆款帖子的结构和写法分析。
你必须严格模仿这些原型的：语气、段落节奏、细节密度、互动方式。
{prototype_section}
""")

    parts.append(f"""
【Agent5 的补充建议（参考但不要照搬）】
引流逻辑：{why}
要求：{req_text}
{agent_rule}
打样片段：{example_sketch}
""")

    # 补充几条分析的拆解范文作为语气参考
    picked = _pick_reference_notes(reference_notes, k=3)
    if picked:
        parts.append("\n【补充拆解范文（学习语气节奏）】")
        for i, note in enumerate(picked, 1):
            text_analysis = note.get("text_analysis", {})
            parts.append(
                f"范文{i}：视角={text_analysis.get('persona_perspective', '')}，"
                f"钩子={text_analysis.get('hook_type', '')}，"
                f"模板摘要={note.get('reusable_template', '')[:200]}"
            )

    parts.append(f"""
【执行指令】
以普通香港居民视角写一篇「{type_name}」类小红书笔记。严格模仿上述真实原型的写法。

硬指标：180-320字，标题带数字/反差/痛点，写碎一点像朋友圈不像文章。
硬禁令：不准"踩坑→救场→感恩"三段式；不准展示专业工具/数据/算账；不准用"耐心/靠谱/专业"等空泛词；
严禁出现「打PM」「私信我」「发资料」「发这套房子的资料」等任何推销话术或变体。
直接输出 JSON。""")

    return "\n".join(parts)


def run_non_property(
    type_name: str,
    brief_section: dict,
    reference_notes: Optional[list[dict]] = None,
    run_id: Optional[str] = None,
    output_dir: Optional[Path] = None,
) -> NoteContent:
    """生成一篇「非房源类型」的引流笔记。"""
    run_id = run_id or get_run_id()
    system_prompt = load_system_prompt()
    refs = reference_notes if reference_notes is not None else load_reference_notes()
    type_label = NON_PROPERTY_TYPES.get(type_name, type_name)
    logger.info("【非房源模式】类型: %s", type_label)

    user_prompt = build_non_property_prompt(type_name, brief_section, refs)
    result = call_llm(user_prompt, system_prompt)

    safe_type = sanitize_filename(type_name)
    prefix = f"agent4_nonprop_{safe_type}"
    save_draft(result, category=type_name, run_id=run_id, output_dir=output_dir,
               file_prefix=f"draft_{prefix}")
    md_path = save_pre_published(result, category=type_name, run_id=run_id, output_dir=output_dir,
                                  file_prefix=prefix)
    logger.info("标题: %s", result.hook_title)
    logger.info("MD: %s", md_path)
    return result


def build_non_property_revision_prompt(
    original: NoteContent,
    type_name: str,
    brief_section: dict,
    note_suggestions: list[str],
    overall_suggestions: list[str],
) -> str:
    """构建「非房源修改稿」的 user prompt。"""
    type_label = NON_PROPERTY_TYPES.get(type_name, type_name)
    original_json = json.dumps(original.model_dump(), ensure_ascii=False, indent=2)
    suggestions_text = "\n".join(f"- {s}" for s in note_suggestions) or "（无针对本篇的具体建议）"
    overall_text = "\n".join(f"- {s}" for s in overall_suggestions) or "（无整体建议）"
    integration_hint = brief_section.get("agent_integration_hint", "")

    return f"""【任务：修改稿】
以下是你之前写的一篇「{type_label}」类引流笔记：

{original_json}

一位"急需流量的中介本人"审稿后，给出了以下修改建议：
针对本篇：
{suggestions_text}

对所有笔记的整体建议（酌情采纳适用于本篇的部分）：
{overall_text}

身份融入参考（Agent5 原始要求）: {integration_hint}

请基于以上建议修改这篇笔记。
修改原则：
- 保持本篇是「{type_label}」类笔记（不介绍具体房源），维持180-320字、素人口吻
- 不要推倒重写，在原有基础上做针对性修改
- 如果原文出现了"救场叙事"（我差点踩坑→小姐姐阻止→我感恩），必须改写掉
- 小姐姐的描述用具体的一个动作/一句话代替，不要在文中展开夸
- 避免"专业""耐心""靠谱"这类空泛形容词

【绝对禁止（出现即为不合格）】
- ❌ 小姐姐拿出专业工具/数据展示专业度
- ❌ 小姐姐说口头禅（"先别急""别冲动"等）
- ❌ 小姐姐请客/被请客/带吃饭
- ❌ 小姐姐连夜/加班/特地帮我做某事
- ❌ "差点踩坑→小姐姐救场→感恩"的三段式结构
直接输出修改后的完整 JSON（字段同上，不要增删字段）。"""


def revise_non_property(
    original: NoteContent,
    type_name: str,
    brief_section: dict,
    note_suggestions: list[str],
    overall_suggestions: list[str],
    system_prompt: Optional[str] = None,
) -> NoteContent:
    """根据 Agent5 的审稿意见修改一篇非房源引流笔记。"""
    system_prompt = system_prompt or load_system_prompt()
    user_prompt = build_non_property_revision_prompt(
        original, type_name, brief_section, note_suggestions, overall_suggestions
    )
    return call_llm(user_prompt, system_prompt)


def build_revision_prompt(original: NoteContent, angle_key: str,
                           note_suggestions: list[str], overall_suggestions: list[str]) -> str:
    """构建"修改稿"模式的 user prompt：基于 Agent5 的审稿意见修改已有笔记。"""
    angle_label = PROPERTY_ANGLES.get(angle_key, angle_key)
    original_json = json.dumps(original.model_dump(), ensure_ascii=False, indent=2)
    suggestions_text = "\n".join(f"- {s}" for s in note_suggestions) or "（无针对本篇的具体建议）"
    overall_text = "\n".join(f"- {s}" for s in overall_suggestions) or "（无整体建议）"

    return f"""【任务：修改稿】
以下是你之前写的一篇"{angle_label}"笔记（房源多角度模式）：

{original_json}

一位"急需流量、迫切想涨粉的中介本人"审稿后，针对本篇给出了以下修改建议：
{suggestions_text}

以及给所有笔记的整体建议（请挑选其中适用于本篇的部分采纳，不要生搬硬套）：
{overall_text}

请基于以上建议修改这篇笔记，重点是让"小姐姐"相关的描述更具体、更有记忆点、
更不像套路化夸奖（禁止用"诚实""耐心""不push"这类空泛词，换成具体动作/细节），
同时保持本篇原有的角度（{angle_label}）、180-320字的篇幅、素人口吻和 system prompt 中的写作规则不变。
不要推倒重写整个故事，在原有基础上做有针对性的修改。直接输出修改后的完整 JSON（字段同上，不要增删字段）。
禁止使用以下模板化人设：大厂数据分析师、Excel算月供、随身带测距仪、强迫症式验楼、拉表算账。"""


def revise_note(original: NoteContent, angle_key: str, note_suggestions: list[str],
                 overall_suggestions: list[str], system_prompt: Optional[str] = None) -> NoteContent:
    """根据 Agent5 的审稿意见修改一篇已有笔记。"""
    system_prompt = system_prompt or load_system_prompt()
    user_prompt = build_revision_prompt(original, angle_key, note_suggestions, overall_suggestions)
    return call_llm(user_prompt, system_prompt)


def build_user_prompt(category: str, reference_notes: list[dict]) -> str:
    cat_cfg = CATEGORIES.get(category, CATEGORIES["生活分享"])
    parts: list[str] = []

    parts.append(f"【本篇母题】{cat_cfg['label']}\n{cat_cfg['prompt']}")

    picked = _pick_reference_notes(reference_notes, k=3)
    if picked:
        parts.append("\n【参考范文（真实爆款素人笔记的拆解结果，学习其结构/钩子/留白手法，不要照抄措辞或具体细节）】")
        for i, note in enumerate(picked, 1):
            text_analysis = note.get("text_analysis", {})
            visual = note.get("visual_analysis", {})
            parts.append(
                f"\n范文{i}（{note.get('note_id', note.get('_source_file', ''))}）：\n"
                f"发帖视角: {text_analysis.get('persona_perspective', '')}\n"
                f"钩子类型: {text_analysis.get('hook_type', '')}\n"
                f"目标客群: {text_analysis.get('target_audience', '')}\n"
                f"封面风格: {visual.get('cover_style', '')}\n"
                f"留白/转化策略: {text_analysis.get('conversion_strategy', '')}\n"
                f"可复用模板: {note.get('reusable_template', '')[:400]}"
            )

    parts.append(f"""
【任务】
基于上面的母题和参考范文的结构/钩子手法（不要照抄具体内容），
写一篇全新的"素人账号"小红书图文笔记。直接输出 JSON。
记住：你是个普通人在记录自己的真实经历，不是中介、不是营销号。""")

    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════
# LLM 调用
# ═══════════════════════════════════════════════════════════════

def _finalize_title(content: NoteContent) -> NoteContent:
    """硬兜底：标题去空白，超过上限就截断，保证发布不被小红书截断。"""
    t = content.hook_title.strip()
    if len(t) > MAX_TITLE_LEN:
        t = t[:MAX_TITLE_LEN].rstrip()
        logger.warning("标题仍超长，已硬截断到 %d 字: %s", MAX_TITLE_LEN, t)
    content.hook_title = t
    return content


def call_llm(user_prompt: str, system_prompt: str) -> NoteContent:
    """调用 LLM 生成笔记，带重试（含标题超长重试）和降级策略。"""
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    def _gen(model: str) -> NoteContent:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
            max_tokens=8192,
            timeout=90,
        )
        return _parse_response(resp.choices[0].message.content.strip())

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info("第 %d/%d 次生成中 (%s)...", attempt, MAX_RETRIES, MODEL)
        try:
            result = _gen(MODEL)
        except Exception as e:
            logger.warning("生成失败 (attempt %d): %s", attempt, e)
            if attempt >= MAX_RETRIES:
                logger.info("降级模型: %s", FALLBACK_MODEL)
                return _finalize_title(_gen(FALLBACK_MODEL))
            continue
        # 内容校验：标题超长（>25字）触发重试
        n = len(result.hook_title.strip())
        if n > MAX_TITLE_LEN and attempt < MAX_RETRIES:
            logger.warning("标题超长(%d字>%d)，重试: %s", n, MAX_TITLE_LEN, result.hook_title.strip())
            continue
        return _finalize_title(result)

    raise RuntimeError(f"LLM 生成失败，已重试 {MAX_RETRIES} 次")


def _parse_response(raw: str) -> NoteContent:
    """解析 LLM 返回的 JSON，自动修复常见的截断/代码块包裹问题。"""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    def _try_fix_truncated_json(s: str) -> str:
        in_string = False
        escape_next = False
        for ch in s:
            if escape_next:
                escape_next = False
                continue
            if ch == '\\':
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
        if in_string:
            s = s + '"'
        open_braces = s.count('{') - s.count('}')
        open_brackets = s.count('[') - s.count(']')
        return s + ']' * open_brackets + '}' * open_braces

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        fixed = _try_fix_truncated_json(cleaned)
        try:
            data = json.loads(fixed)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}", cleaned)
            if not m:
                raise
            data = json.loads(_try_fix_truncated_json(m.group(0)))

    raw_tags = data.get("seo_tags", [])
    if isinstance(raw_tags, str):
        raw_tags = [t.strip("#").strip() for t in raw_tags.split() if t.strip()]
    elif isinstance(raw_tags, list):
        raw_tags = [t.strip("#").strip() if isinstance(t, str) else str(t) for t in raw_tags]
    else:
        raw_tags = []

    raw_imgs = data.get("image_suggestions", [])
    if isinstance(raw_imgs, str):
        raw_imgs = [raw_imgs]
    elif not isinstance(raw_imgs, list):
        raw_imgs = []

    return NoteContent(
        hook_title=data.get("hook_title", ""),
        main_content=data.get("main_content", ""),
        interactive_question=data.get("interactive_question", ""),
        seo_tags=raw_tags,
        image_suggestions=[str(i) for i in raw_imgs],
        persona_note=data.get("persona_note", ""),
    )


# ═══════════════════════════════════════════════════════════════
# 结果保存
# ═══════════════════════════════════════════════════════════════

def _iq_in_body(iq: str, body: str) -> bool:
    """判断互动提问是否已在正文里（忽略 emoji/标点/空白差异，避免重复拼接）。"""
    norm = lambda s: re.sub(r'[^\w一-鿿]', '', s)
    niq = norm(iq)
    return bool(niq) and niq in norm(body)


def _format_tags(seo_tags) -> str:
    """规范成 '#t1 #t2 ...'：拆开被逗号/顿号/空格/# 粘在一起的标签，去重去空。"""
    out, seen = [], set()
    for raw in seo_tags or []:
        for t in re.split(r'[,，、\s#]+', str(raw)):
            t = t.strip()
            if t and t not in seen:
                seen.add(t)
                out.append(t)
    return " ".join(f"#{t}" for t in out)


def convert_to_markdown(content: NoteContent, category: str) -> str:
    tags = _format_tags(content.seo_tags)
    angle_label = PROPERTY_ANGLES.get(category, category)

    body = content.main_content.replace("\\n", "\n").strip()
    iq = content.interactive_question.strip()
    if iq and not _iq_in_body(iq, body) and not body.rstrip().endswith(("？", "?")):
        body = f"{body}\n\n{iq}"

    lines = [f"# {content.hook_title}", "", body, ""]
    if tags:
        lines += [tags, ""]
    lines += ["---", angle_label]

    return "\n".join(lines) + "\n"


def save_draft(content: NoteContent, category: str, run_id: Optional[str] = None,
                output_dir: Optional[Path] = None, file_prefix: Optional[str] = None) -> Path:
    base = Path(output_dir) if output_dir else OUTPUTS_DIR
    run_id = run_id or get_run_id()
    target_dir = base / run_id / "drafts"
    target_dir.mkdir(parents=True, exist_ok=True)

    hk_tz = timezone(timedelta(hours=8))
    ts = datetime.now(hk_tz).strftime("%Y%m%d_%H%M%S")
    prefix = file_prefix or f"draft_agent4_{category}"
    output_path = target_dir / f"{prefix}_{ts}.json"

    payload = content.model_dump()
    payload["_category"] = category
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("草稿已保存: %s", output_path)
    return output_path


def save_pre_published(content: NoteContent, category: str, run_id: Optional[str] = None,
                        output_dir: Optional[Path] = None, file_prefix: Optional[str] = None) -> Path:
    base = Path(output_dir) if output_dir else OUTPUTS_DIR
    run_id = run_id or get_run_id()
    subfolder = ANGLE_CATEGORY_FOLDER.get(category, "")
    target_dir = base / run_id / "pre-published" / subfolder if subfolder else base / run_id / "pre-published"
    target_dir.mkdir(parents=True, exist_ok=True)

    safe_title = sanitize_filename(content.hook_title) or get_run_id()
    output_path = target_dir / f"{safe_title}.md"

    output_path.write_text(convert_to_markdown(content, category), encoding="utf-8")
    logger.info("Markdown 已发布: %s", output_path)
    return output_path


def save_assembled(
    content: NoteContent,
    property_data: Optional[dict] = None,
    run_id: Optional[str] = None,
    output_dir: Optional[Path] = None,
    angle_key: str = "",
    compare_props: Optional[list[dict]] = None,
) -> Path:
    """主输出：每篇笔记一个独立文件夹，含 note.txt + 房源实拍图。

    文件夹结构：
        output_dir/{序号}_{安全标题}/
            note.txt         # 纯文本笔记
            photo_2.jpg      # 随机房源实拍图（如有 property_data）
            photo_3.jpg      # 额外实拍图（如有，随机2张）
    注意：photo_1.jpg 留给后续的小红书大字报封面（需单独生成）。

    返回：文件夹路径。
    """
    base = Path(output_dir) if output_dir else OUTPUTS_DIR
    run_id = run_id or get_run_id()
    target_root = base / run_id / "notes"
    target_root.mkdir(parents=True, exist_ok=True)

    # 安全文件夹名
    safe_title = sanitize_filename(content.hook_title) or "untitled"
    safe_title = safe_title.rstrip('.')[:40].strip()
    folder = target_root / safe_title
    folder.mkdir(parents=True, exist_ok=True)

    # ── note.txt（无字段标签，纯内容）──
    tags = _format_tags(content.seo_tags)
    body = content.main_content.replace("\\n", "\n")
    note_text = f"{content.hook_title}\n\n{body}\n"
    iq = content.interactive_question.strip()
    if iq and not _iq_in_body(iq, body) and not body.rstrip().endswith(("？", "?")):
        note_text += f"\n{iq}\n"
    if tags:
        note_text += f"\n{tags}\n"
    txt_path = folder / "note.txt"
    txt_path.write_text(note_text.strip() + "\n", encoding="utf-8")
    logger.info("Assembled TXT: %s", txt_path)

    # ── 记录本篇角度（供发布版导出可靠识别编号，无需靠标题猜）──
    if angle_key:
        (folder / "_angle.txt").write_text(angle_key, encoding="utf-8")

    # ── 记录源房源目录（供发布版按需从原图库补实拍图；C 询问篇不指向具体房源，不记）──
    if ANGLE_CATEGORY_FOLDER.get(angle_key) != "3_询问":
        src_dirs = []
        for p in [property_data] + list(compare_props or []):
            pd = (p or {}).get("property_dir", "")
            if pd and pd not in src_dirs:
                src_dirs.append(pd)
        if src_dirs:
            (folder / "_property.txt").write_text("\n".join(src_dirs), encoding="utf-8")

    # ── 房源实拍图（C 询问篇是需求口吻、不指向具体房源，不放实拍图）──
    is_inquiry = ANGLE_CATEGORY_FOLDER.get(angle_key) == "3_询问"
    if property_data and not is_inquiry:
        prop_dir = property_data.get("property_dir", "")
        if prop_dir:
            prop_dir = Path(prop_dir)
            if prop_dir.is_dir():
                import random as _rand
                photos = sorted([
                    f for f in prop_dir.iterdir()
                    if f.suffix.lower() in ('.jpg', '.jpeg', '.png')
                    and 'cover' not in f.name.lower()
                ])
                if photos:
                    n_photos = min(_rand.randint(1, 2), len(photos))
                    chosen = _rand.sample(photos, n_photos)
                    for i, ph in enumerate(chosen, start=2):
                        dst = folder / f"photo_{i}{ph.suffix}"
                        shutil = __import__("shutil")
                        shutil.copy2(ph, dst)
                        logger.info("Copied photo_%d: %s", i, ph.name)

    logger.info("Assembled folder: %s", folder)
    return folder


def save_assembled_simple(
    content: NoteContent,
    run_id: Optional[str] = None,
    output_dir: Optional[Path] = None,
) -> Path:
    """简化版组装：仅 note.txt，无房源照片（用于非房源笔记类型）。"""
    return save_assembled(content, property_data=None, run_id=run_id,
                         output_dir=output_dir, angle_key="")


# ═══════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════

def run(
    category: Optional[str] = None,
    n: int = 1,
    reference_notes: Optional[list[dict]] = None,
    run_id: Optional[str] = None,
    output_dir: Optional[Path] = None,
    property_data: Optional[dict] = None,
    angle_key: Optional[str] = None,
    compare_props: Optional[list[dict]] = None,
) -> list[NoteContent]:
    """生成 n 篇素人账号爆款笔记。

    category: 母题，从 CATEGORIES 中选择；None 则每篇随机选择
    n: 生成篇数
    property_data + angle_key: 房源多角度模式。指定后忽略 category/n，
        针对该房源 + 该角度（PROPERTY_ANGLES 中的 key）生成单篇笔记。
    compare_props: 对比类角度的其余真实房源（横向对比用）。
    """
    run_id = run_id or get_run_id()
    system_prompt = load_system_prompt()
    refs = reference_notes if reference_notes is not None else load_reference_notes()

    logger.info("=" * 50)
    logger.info("  Agent 4 — 素人账号爆款笔记生成器 启动")
    logger.info("  Model: %s | Run: %s | 参考范文: %d 条", MODEL, run_id, len(refs))
    logger.info("=" * 50)

    # ── 房源多角度模式 ──
    if property_data is not None and angle_key is not None:
        logger.info("【房源多角度模式】%s | %s", _summarize_property(property_data), PROPERTY_ANGLES[angle_key])
        if angle_key in COMPARISON_ANGLES and compare_props:
            logger.info("【对比类角度】横向对比 %d 套真实房源：%s",
                        1 + len(compare_props),
                        " vs ".join([property_data.get("name", "")] + [p.get("name", "") for p in compare_props]))
        user_prompt = build_property_angle_prompt(property_data, angle_key, refs, compare_props=compare_props)
        result = call_llm(user_prompt, system_prompt)

        safe_name = sanitize_filename(property_data.get("name", "untitled"))
        prefix = f"agent4_{safe_name}_{angle_key}"
        # 传统输出（draft + MD，向后兼容）
        save_draft(result, category=angle_key, run_id=run_id, output_dir=output_dir, file_prefix=f"draft_{prefix}")
        md_path = save_pre_published(result, category=angle_key, run_id=run_id, output_dir=output_dir, file_prefix=prefix)
        # ★ 新主输出：文件夹版
        assembled_folder = save_assembled(result, property_data=property_data,
                                          run_id=run_id, output_dir=output_dir, angle_key=angle_key,
                                          compare_props=compare_props)

        logger.info("标题: %s", result.hook_title)
        logger.info("文件夹: %s", assembled_folder)
        return [result]

    results: list[NoteContent] = []
    for i in range(1, n + 1):
        cat = category or random.choice(list(CATEGORIES.keys()))
        logger.info("─" * 40)
        logger.info("【%d/%d】母题: %s", i, n, CATEGORIES.get(cat, {}).get("label", cat))

        user_prompt = build_user_prompt(cat, refs)
        result = call_llm(user_prompt, system_prompt)

        save_draft(result, category=cat, run_id=run_id, output_dir=output_dir)
        md_path = save_pre_published(result, category=cat, run_id=run_id, output_dir=output_dir)

        logger.info("标题: %s", result.hook_title)
        logger.info("人设: %s", result.persona_note)
        logger.info("MD: %s", md_path)
        results.append(result)

    return results


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent 4 — 素人账号爆款笔记生成器")
    parser.add_argument("--category", type=str, default=None,
                         choices=list(CATEGORIES.keys()),
                         help="母题：买房经历 / 租房体验 / 看房日记 / 生活分享（默认随机）")
    parser.add_argument("-n", "--num", type=int, default=1, help="生成篇数")
    parser.add_argument("--run-id", type=str, default=None, help="管线运行时间戳")
    parser.add_argument("--output-dir", type=Path, default=None, help="输出目录（默认 04_outputs/）")
    parser.add_argument("--list-categories", action="store_true", help="列出所有母题后退出")
    parser.add_argument("--property-dir", type=Path, default=None,
                         help="房源目录（启用房源多角度模式，必须同时传 --angle）")
    parser.add_argument("--compare-dir", type=Path, action="append", default=None,
                         help="对比类角度(纠结对比/决赛圈对比)的其余真实房源目录，可多次传；"
                              "不传则自动从主房源同级目录随机补齐")
    parser.add_argument("--angle", type=str, default=None,
                         choices=list(PROPERTY_ANGLES.keys()),
                         help="写作角度（--property-dir 模式下必填）：" +
                              " / ".join(f"{k}={v}" for k, v in PROPERTY_ANGLES.items()))
    parser.add_argument("--list-angles", action="store_true", help="列出所有房源多角度写作角度后退出")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.list_categories:
        for k, v in CATEGORIES.items():
            print(f"{k}: {v['label']}")
        sys.exit(0)

    if args.list_angles:
        for k, v in PROPERTY_ANGLES.items():
            print(f"{k}: {v}")
        sys.exit(0)

    if args.property_dir is not None:
        if args.angle is None:
            print("错误：使用 --property-dir 时必须同时指定 --angle。\n")
            print("可选角度：")
            for k, v in PROPERTY_ANGLES.items():
                print(f"  {k}  {v}")
            print("\n示例：--property-dir <路径> --angle 看房日记")
            sys.exit(1)
        prop_dir = args.property_dir.resolve()

        def _load_prop(d: Path) -> Optional[dict]:
            ip = d / "info.md"
            if not ip.exists():
                return None
            return {"name": d.name, "property_dir": str(d), "raw_info": ip.read_text(encoding="utf-8")}

        prop_data = _load_prop(prop_dir)
        if prop_data is None:
            print(f"错误：找不到 {prop_dir / 'info.md'}")
            sys.exit(1)

        # ── 对比类角度：备齐其余真实房源，绝不让 LLM 虚构对照盘 ──
        compare_props: Optional[list[dict]] = None
        if args.angle in COMPARISON_ANGLES:
            need = COMPARISON_ANGLES[args.angle] - 1
            compare_props = []
            # 1) 显式 --compare-dir
            for cd in (args.compare_dir or []):
                cp = _load_prop(cd.resolve())
                if cp:
                    compare_props.append(cp)
            # 2) 不足则从主房源同级目录随机补齐真实房源
            if len(compare_props) < need:
                used = {prop_dir.name} | {Path(p["property_dir"]).name for p in compare_props}
                siblings = [d for d in sorted(prop_dir.parent.iterdir())
                            if d.is_dir() and d.name not in used and (d / "info.md").exists()]
                random.shuffle(siblings)
                for d in siblings[: need - len(compare_props)]:
                    cp = _load_prop(d)
                    if cp:
                        compare_props.append(cp)
            if len(compare_props) < need:
                print(f"错误：对比角度「{args.angle}」需要 {need + 1} 套真实房源，"
                      f"但同级目录只凑到 {len(compare_props) + 1} 套。请补 --compare-dir。")
                sys.exit(1)

        run(property_data=prop_data, angle_key=args.angle,
            run_id=args.run_id, output_dir=args.output_dir, compare_props=compare_props)
    else:
        run(category=args.category, n=args.num, run_id=args.run_id, output_dir=args.output_dir)
