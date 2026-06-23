"""
Agent 5 — 中介引流审稿官 (Traffic Critic)

扮演一个在小红书上几乎没有粉丝、没有流量的香港房产中介本人，
审查 Agent4 产出的"素人众包笔记"，评估这些笔记能不能给中介带来曝光/咨询，
给 Agent4 提具体修改建议，并头脑风暴新的引流众包笔记点子。

输入: Agent4 产出的 pre-published markdown 笔记
      (默认读取 06_output(multiangle)/<run_id>/pre-published/*.md)
输出: agent5_review/review_<run_id>.json + agent5_review/review_<run_id>.md
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pydantic import BaseModel, Field
from openai import OpenAI
from shared import API_KEY, BASE_URL, HEAVY_MODEL, PROJECT_ROOT

# ═══════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════

MODEL = HEAVY_MODEL
FALLBACK_MODEL = "gemini-3.1-flash-lite"
MAX_RETRIES = 3

SCRIPT_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT_PATH = SCRIPT_DIR / "system_prompt.txt"

# Agent4 多角度笔记的输出目录
MULTIANGLE_OUTPUT_DIR = PROJECT_ROOT / "06_output(multiangle)"


# ═══════════════════════════════════════════════════════════════
# Pydantic 输出 Schema
# ═══════════════════════════════════════════════════════════════

class NoteReview(BaseModel):
    file_name: str = Field(description="被评审的笔记文件名")
    traffic_score: int = Field(description="引流潜力评分 1-10")
    has_agent_mention: bool = Field(description="是否提到了中介/带看体验")
    mention_quality: str = Field(description="中介曝光方式的评价")
    strengths: list[str] = Field(default_factory=list, description="做得好的地方")
    weaknesses: list[str] = Field(default_factory=list, description="不足之处")
    suggestions: list[str] = Field(default_factory=list, description="针对本篇的修改建议")


class CreativeIdea(BaseModel):
    name: str = Field(description="点子名称")
    core_idea: str = Field(description="核心创意说明")
    example_snippet: str = Field(description="示例文字片段")


class NotesReviewResponse(BaseModel):
    note_reviews: list[NoteReview] = Field(default_factory=list)


class IdeasResponse(BaseModel):
    overall_suggestions_for_agent4: list[str] = Field(default_factory=list)
    creative_ideas: list[CreativeIdea] = Field(default_factory=list)


class BatchReview(BaseModel):
    note_reviews: list[NoteReview] = Field(default_factory=list)
    overall_suggestions_for_agent4: list[str] = Field(default_factory=list)
    creative_ideas: list[CreativeIdea] = Field(default_factory=list)


# ─── 非房源内容简报 ─────────────────────────────────────────────────

class ContentTypeBrief(BaseModel):
    type_name: str = Field(description="内容类型名称，如「避坑指南」「区域测评」等")
    why_it_works: str = Field(description="这类内容为何能帮中介引流（50字以内）")
    key_requirements: list[str] = Field(description="Agent4写这类内容的核心要求，3-5条")
    agent_integration_hint: str = Field(description="如何自然地把中介身份融入这类内容，不露痕迹")
    example_sketch: str = Field(description="60-120字的打样示例：标题+正文开头+中介元素呈现方式")


class ContentBrief(BaseModel):
    overview: str = Field(description="给Agent4的整体写作策略，100字以内")
    content_types: list[ContentTypeBrief] = Field(description="每种内容类型的详细简报")


# ═══════════════════════════════════════════════════════════════
# 日志
# ═══════════════════════════════════════════════════════════════

def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("Agent5.TrafficCritic")
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
    return "你是一名急需流量的香港房产中介，正在审查小红书笔记的引流效果。严格输出 JSON。"


# ═══════════════════════════════════════════════════════════════
# 笔记加载
# ═══════════════════════════════════════════════════════════════

def find_latest_run_dir(base_dir: Path = MULTIANGLE_OUTPUT_DIR) -> Optional[Path]:
    if not base_dir.exists():
        return None
    candidates = [d for d in base_dir.iterdir() if d.is_dir() and (d / "pre-published").exists()]
    if not candidates:
        return None
    return max(candidates, key=lambda d: d.stat().st_mtime)


def load_notes(run_dir: Path, pattern: str = "agent4_*.md") -> list[dict]:
    """加载某次运行目录下 Agent4 产出的 pre-published markdown 笔记。"""
    notes_dir = run_dir / "pre-published"
    notes: list[dict] = []
    if not notes_dir.exists():
        logger.warning("笔记目录不存在: %s", notes_dir)
        return notes

    for f in sorted(notes_dir.glob(pattern)):
        notes.append({
            "file_name": f.name,
            "content": f.read_text(encoding="utf-8"),
        })

    logger.info("加载笔记: %d 篇 (来自 %s)", len(notes), notes_dir)
    return notes


# ═══════════════════════════════════════════════════════════════
# User Prompt 构建
# ═══════════════════════════════════════════════════════════════

def build_notes_review_prompt(notes: list[dict]) -> str:
    parts: list[str] = [
        f"【本批待审笔记，共 {len(notes)} 篇】",
        "这些笔记均由 Agent4 生成，是给你（中介本人）做引流用的素人众包笔记。",
        "请逐篇审稿打分。",
    ]

    for i, note in enumerate(notes, 1):
        parts.append(f"\n--- 笔记 {i} (file_name: {note['file_name']}) ---\n{note['content']}")

    parts.append(
        "\n【本次任务】仅完成任务一（逐条审稿），"
        '严格按照 {"note_reviews": [...]} 的格式输出 JSON，不要输出其他字段。'
    )
    return "\n".join(parts)


NON_PROPERTY_CONTENT_TYPES = [
    "避坑指南",
    "区域生活测评",
    "买房全流程科普",
    "看房复盘日记",
    "CitywalkHK探区",
    "香港楼市行情评论",
]


def build_brief_prompt() -> str:
    types_list = "\n".join(f"- {t}" for t in NON_PROPERTY_CONTENT_TYPES)
    return f"""你是一个在香港从业多年、急需在小红书上涨粉引流的房产中介。
你现在要为你的"众包素人笔记助手"（Agent4）写一份创作简报，
告诉 Agent4 应该如何写以下几类「完全不介绍具体房源」的生活/知识类笔记，
来帮你吸引潜在买家/租客的关注，最终引导他们主动来找你咨询。

【需要的非房源内容类型】
{types_list}

【铁律：六种类型必须用六种完全不同的中介融入方式】
以下是被禁用的模板，任何一篇都不能用：
- ❌ "我差点踩坑→中介及时阻止→我感恩戴德"的救场叙事
- ❌ 中介拿出某个专业工具（测噪仪/查册/底价表/iPad表格）展示专业度
- ❌ 中介说某句口头禅（"先别急""别冲动"等）
- ❌ 中介请吃东西或被我请吃东西
- ❌ 中介连夜/加班帮我做某件事
- ❌ 中介全程陪同贯穿全文

允许的中介出现方式（六种类型各选一种，不重复）：
- 一笔带过型：全文只提一句"带我的中介说…"，中介是背景板
- 反向吐槽型：吐槽中介某个小毛病/不专业的地方，反而显得真实
- 事后转述型：看完房回到家，发微信问中介一个问题，他回了一句有用的
- 对比型：提到之前找的别的中介不靠谱，现在这个还行，但不展开夸
- 工具属性型：中介只是提供了某个信息/数据，不描写这个人本身
- 完全隐藏型：通篇不提中介，靠内容本身引流（评论区自然会有人问"求推荐中介"）

每种类型的中介融入方式必须在 agent_integration_hint 里明确标注是以上六种中的哪一种。

请针对每一种内容类型，告诉 Agent4：
1. 这类内容为什么能帮你引流（50字以内）
2. 核心写作要求（3-5条，必须含：禁止使用AI腔/营销腔，必须模仿真实小红书的语气）
3. 中介融入方式（必须是上述六种之一，写清楚具体怎么操作）
4. 一个60-120字的打样示例——标题+正文开头，展示真实素人的语气

另写整体策略（100字以内）。

严格按照以下 JSON 格式输出，不要输出任何其他内容：
{{
  "overview": "整体策略...",
  "content_types": [
    {{
      "type_name": "避坑指南",
      "why_it_works": "...",
      "key_requirements": ["...", "..."],
      "agent_integration_hint": "...（标注属于六种方式中的哪一种）",
      "example_sketch": "..."
    }}
  ]
}}"""


def generate_brief(save_path: Optional[Path] = None) -> "ContentBrief":
    """Agent5 为非房源内容写创作简报（含打样），供 Agent4 参考写作。"""
    system_prompt = load_system_prompt()
    user_prompt = build_brief_prompt()
    logger.info("Agent5 正在生成非房源内容创作简报...")
    brief = call_llm(user_prompt, system_prompt, ContentBrief, max_tokens=8192)
    if save_path:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(
            json.dumps(brief.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("简报已保存: %s", save_path)
    return brief


def build_ideas_prompt(notes: list[dict], note_reviews: list[NoteReview]) -> str:
    parts: list[str] = [
        f"【本批笔记的逐条审稿已完成，共 {len(notes)} 篇，摘要如下】",
    ]

    for nr in note_reviews:
        parts.append(
            f"- {nr.file_name} | 引流评分: {nr.traffic_score}/10 | "
            f"是否提中介: {nr.has_agent_mention} | 中介曝光评价: {nr.mention_quality}"
        )

    parts.append("\n【这些笔记的标题和正文片段，供你参考整体风格和已用过的角度/钩子】")
    for note in notes:
        first_lines = "\n".join(note["content"].splitlines()[:4])
        parts.append(f"\n--- {note['file_name']} ---\n{first_lines}")

    parts.append(
        "\n【本次任务】基于以上审稿结果和笔记概览，完成任务二（给Agent4的整体建议）"
        "和任务三（创意点子头脑风暴）。"
        '严格按照 {"overall_suggestions_for_agent4": [...], "creative_ideas": [...]} 的格式输出 JSON，'
        "不要输出其他字段。"
    )
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════
# LLM 调用
# ═══════════════════════════════════════════════════════════════

def call_llm(user_prompt: str, system_prompt: str, response_model: type[BaseModel],
              max_tokens: int = 8192) -> BaseModel:
    """调用 LLM，带重试和降级策略，并将结果解析为指定的 pydantic 模型。"""
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info("第 %d/%d 次调用中 (%s)...", attempt, MAX_RETRIES, MODEL)
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.8,
                max_tokens=max_tokens,
                timeout=120,
            )
            raw = resp.choices[0].message.content.strip()
            return _parse_response(raw, response_model)
        except Exception as e:
            logger.warning("调用失败 (attempt %d): %s", attempt, e)
            if attempt >= MAX_RETRIES:
                logger.info("降级模型: %s", FALLBACK_MODEL)
                resp = client.chat.completions.create(
                    model=FALLBACK_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.8,
                    max_tokens=max_tokens,
                    timeout=120,
                )
                raw = resp.choices[0].message.content.strip()
                return _parse_response(raw, response_model)

    raise RuntimeError(f"LLM 调用失败，已重试 {MAX_RETRIES} 次")


def _parse_response(raw: str, response_model: type[BaseModel]) -> BaseModel:
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

    return response_model.model_validate(data)


# ═══════════════════════════════════════════════════════════════
# 结果保存
# ═══════════════════════════════════════════════════════════════

def convert_to_markdown(review: BatchReview, run_dir: Path) -> str:
    lines = [f"# Agent5 引流审稿报告 — {run_dir.name}", ""]

    lines.append("## 逐条审稿")
    for nr in review.note_reviews:
        lines.append(f"\n### {nr.file_name}")
        lines.append(f"- 引流潜力评分: **{nr.traffic_score}/10**")
        lines.append(f"- 是否提到中介: {'是' if nr.has_agent_mention else '否'}")
        lines.append(f"- 中介曝光评价: {nr.mention_quality}")
        if nr.strengths:
            lines.append("- 亮点:")
            for s in nr.strengths:
                lines.append(f"  - {s}")
        if nr.weaknesses:
            lines.append("- 不足:")
            for w in nr.weaknesses:
                lines.append(f"  - {w}")
        if nr.suggestions:
            lines.append("- 修改建议:")
            for s in nr.suggestions:
                lines.append(f"  - {s}")

    lines.append("\n## 给 Agent4 的整体建议")
    for s in review.overall_suggestions_for_agent4:
        lines.append(f"- {s}")

    lines.append("\n## 创意点子头脑风暴")
    for idea in review.creative_ideas:
        lines.append(f"\n### {idea.name}")
        lines.append(f"- 核心创意: {idea.core_idea}")
        lines.append(f"- 示例片段: {idea.example_snippet}")

    return "\n".join(lines) + "\n"


def save_review(review: BatchReview, run_dir: Path) -> tuple[Path, Path]:
    target_dir = run_dir / "agent5_review"
    target_dir.mkdir(parents=True, exist_ok=True)

    json_path = target_dir / f"review_{run_dir.name}.json"
    json_path.write_text(json.dumps(review.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")

    md_path = target_dir / f"review_{run_dir.name}.md"
    md_path.write_text(convert_to_markdown(review, run_dir), encoding="utf-8")

    logger.info("审稿报告已保存: %s", md_path)
    return json_path, md_path


# ═══════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════

def run(run_dir: Optional[Path] = None, pattern: str = "agent4_*.md") -> BatchReview:
    run_dir = run_dir or find_latest_run_dir()
    if run_dir is None:
        raise FileNotFoundError(f"在 {MULTIANGLE_OUTPUT_DIR} 下找不到包含 pre-published 的运行目录")
    run_dir = Path(run_dir)

    system_prompt = load_system_prompt()
    notes = load_notes(run_dir, pattern=pattern)
    if not notes:
        raise FileNotFoundError(f"在 {run_dir / 'pre-published'} 下找不到匹配 '{pattern}' 的笔记")

    logger.info("=" * 50)
    logger.info("  Agent 5 — 中介引流审稿官 启动")
    logger.info("  Model: %s | Run: %s | 待审笔记: %d 篇", MODEL, run_dir.name, len(notes))
    logger.info("=" * 50)

    logger.info("第一步：逐条审稿...")
    notes_prompt = build_notes_review_prompt(notes)
    notes_review = call_llm(notes_prompt, system_prompt, NotesReviewResponse, max_tokens=16384)

    logger.info("第二步：整体建议 + 创意点子头脑风暴...")
    ideas_prompt = build_ideas_prompt(notes, notes_review.note_reviews)
    ideas = call_llm(ideas_prompt, system_prompt, IdeasResponse, max_tokens=4096)

    review = BatchReview(
        note_reviews=notes_review.note_reviews,
        overall_suggestions_for_agent4=ideas.overall_suggestions_for_agent4,
        creative_ideas=ideas.creative_ideas,
    )

    save_review(review, run_dir)

    for nr in review.note_reviews:
        logger.info("【%s】引流评分: %d/10", nr.file_name, nr.traffic_score)

    return review


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent 5 — 中介引流审稿官")
    parser.add_argument("--run-dir", type=str, default=None,
                         help="Agent4 输出的运行目录 (包含 pre-published 子目录)；默认取最新一次")
    parser.add_argument("--pattern", type=str, default="agent4_*.md",
                         help="待审笔记的文件名匹配模式 (默认 agent4_*.md)")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(run_dir=Path(args.run_dir) if args.run_dir else None, pattern=args.pattern)
