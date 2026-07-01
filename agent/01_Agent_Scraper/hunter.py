"""
Agent 1 — 爆款笔记猎人 (Hunter)
自动化筛选高潜力的香港买房小红书笔记并下载。

工作流：
  1. xhs search 搜索香港买房关键词，从搜索结果中同时提取 id + xsec_token
  2. 拼装 discovery/item 分享链接（免登录桌面端可打开）
  3. 调用 xhs CLI 获取评论区 JSON 数据
  4. LLM 轻量级意图分析，统计询盘率
  5. 满足阈值则记录到 qualified_urls.txt
  * 若搜索不可用，降级读取 seed_urls.txt（explore 短链接）
"""

import os
import sys
import json
import re
import subprocess
import logging
import time
import ast
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from openai import OpenAI
from shared import API_KEY, BASE_URL, LIGHT_MODEL

# ═══════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════

MODEL = LIGHT_MODEL  # 评论二分类，非思考型省 token

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MATERIALS_DIR = PROJECT_ROOT.parent / "01_materials"
OUTPUTS_DIR = PROJECT_ROOT.parent / "04_outputs"
STAGE1_DIR = PROJECT_ROOT / "data_pipeline" / "stage1_raw"
VIRAL_DIR = MATERIALS_DIR / "viral_examples"  # 爬取结果存放根目录
SEED_URLS_PATH = MATERIALS_DIR / "seed_urls.txt"
QUALIFIED_LEADS_PATH = OUTPUTS_DIR / "qualified_leads.json"
DOWNLOADS_DIR = OUTPUTS_DIR / "downloads"

XHS_CLI_CMD = "xhs"

# 搜索关键词（用于发现笔记并获取 xsec_token）
SEARCH_KEYWORDS = [
    "香港放售",
    "香港楼盘介绍",
    "香港二手笋盘",
    "香港上车楼盘",
    "港岛放盘",
    "九龙新盘",
    "香港业主急放",
    "铜锣湾放盘",
    "湾仔楼盘",
    "西营盘楼盘",
    "香港细价楼",
]
SEARCH_PAGES_PER_KEYWORD = 3  # 每个关键词搜3页
SEARCH_TYPE = "image"          # 只要图文笔记
SEARCH_SORT = "latest"         # 按最新排序

# ── 时效性过滤 ──
PUBLISHED_WITHIN_DAYS = 14  # 只要最近 14 天内的笔记

MIN_INQUIRY_COUNT = 2
MIN_INQUIRY_RATIO = 0.20
COMMENTS_TIMEOUT = 120
DOWNLOAD_NOTE_TIMEOUT = 120  # xhs read 获取笔记详情超时
SLEEP_BETWEEN_NOTES = 3  # 配合 xhs CLI 内置节流，避免风控
SLEEP_BETWEEN_SEARCHES = 2  # 搜索间隔，避免风控

# 验证码风控处理
CAPTCHA_COOLDOWN_BASE = 30      # 首次触发验证码冷却秒数
CAPTCHA_COOLDOWN_MAX = 300      # 最大冷却 5 分钟
MAX_CONSECUTIVE_CAPTCHAS = 5    # 连续触发此数后中止运行

# ═══════════════════════════════════════════════════════════════
# 日志
# ═══════════════════════════════════════════════════════════════

def _setup_logger() -> logging.Logger:
    _logger = logging.getLogger("Agent1.Hunter")
    _logger.setLevel(logging.DEBUG)
    if not _logger.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter(
            "[%(asctime)s] %(levelname)-7s | %(message)s",
            datefmt="%H:%M:%S",
        ))
        _logger.addHandler(h)
    return _logger

logger = _setup_logger()

# ═══════════════════════════════════════════════════════════════
# 底层：xhs CLI 子进程调用
# ═══════════════════════════════════════════════════════════════

def _xhs_subprocess(args: list[str], timeout: int = 120) -> dict:
    """调用 xhs CLI --json，返回解析后的 dict。统一处理编码和错误。"""
    proc = subprocess.run(
        [XHS_CLI_CMD] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
        env={
            **os.environ,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONLEGACYWINDOWSSTDIO": "utf-8",
        },
    )

    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()

    if proc.returncode != 0:
        logger.error("xhs CLI 退出码 %d | cmd: %s", proc.returncode, " ".join(args))
        if stderr:
            logger.error("stderr: %s", stderr[:300])
        raise RuntimeError(f"xhs CLI 执行失败 (exit={proc.returncode}): {stderr[:200]}")

    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        logger.error("xhs CLI 返回非法 JSON，前 300 字: %s", stdout[:300])
        raise

    if not envelope.get("ok"):
        err = envelope.get("error", {})
        code = err.get("code", "unknown")
        msg = err.get("message", str(err))
        logger.error("xhs API 错误 [%s]: %s", code, msg)
        raise RuntimeError(f"xhs API 错误 [{code}]: {msg}")

    return envelope


# ═══════════════════════════════════════════════════════════════
# 步骤 0：搜索发现笔记 → 提取 id + xsec_token → 拼装分享链接
# ═══════════════════════════════════════════════════════════════

def search_notes(keyword: str, page: int = 1, sort: str = SEARCH_SORT,
                 note_type: str = SEARCH_TYPE) -> list[dict]:
    """调用 xhs search，返回笔记列表，每条包含 id, xsec_token, title。

    xhs search 返回的 JSON 中，每个 item 的 xsec_token 和 id 在同一层级：
      {"id": "xxx", "xsec_token": "yyy", "model_type": "note", "note_card": {...}}
    """
    logger.info("搜索: \"%s\" page=%d sort=%s type=%s", keyword, page, sort, note_type)
    envelope = _xhs_subprocess(
        ["search", keyword, "--type", note_type, "--sort", sort, "--page", str(page), "--json"],
        timeout=60,
    )
    items = envelope.get("data", {}).get("items", [])
    notes = []
    for item in items:
        note_id = item.get("id", "")
        xsec = item.get("xsec_token", "")
        note_card = item.get("note_card", {})
        title = note_card.get("display_title", note_card.get("title", ""))
        user_info = note_card.get("user", {})
        if isinstance(user_info, str):
            try:
                user_info = ast.literal_eval(user_info)
            except (ValueError, SyntaxError):
                user_info = {}
        # 发布时间：从 corner_tag_info 中提取（可能是 Python repr 字符串）
        publish_ts = None
        corner_tags = note_card.get("corner_tag_info", [])
        if isinstance(corner_tags, str):
            try:
                corner_tags = ast.literal_eval(corner_tags)
            except (ValueError, SyntaxError):
                # fallback: regex extract date
                m = re.search(r"'text':\s*'(\d{4}-\d{2}-\d{2})'", corner_tags)
                if m:
                    try:
                        publish_ts = datetime.strptime(m.group(1), "%Y-%m-%d").timestamp()
                    except ValueError:
                        pass
                corner_tags = []
        if isinstance(corner_tags, list):
            for tag in corner_tags:
                if isinstance(tag, dict) and tag.get("type") == "publish_time":
                    ts_text = tag.get("text", "").strip()
                    try:
                        if re.match(r'\d{4}-\d{2}-\d{2}', ts_text):
                            publish_ts = datetime.strptime(ts_text[:10], "%Y-%m-%d").timestamp()
                        elif re.match(r'\d{2}-\d{2}$', ts_text):
                            publish_ts = datetime.strptime(f"{datetime.now().year}-{ts_text}", "%Y-%m-%d").timestamp()
                        elif '小时前' in ts_text:
                            publish_ts = datetime.now().timestamp()  # today
                        elif '昨天' in ts_text:
                            publish_ts = datetime.now().timestamp() - 86400
                        elif '前天' in ts_text:
                            publish_ts = datetime.now().timestamp() - 2 * 86400
                        elif '天前' in ts_text:
                            m = re.search(r'(\d+)', ts_text)
                            days = int(m.group(1)) if m else 3
                            publish_ts = datetime.now().timestamp() - days * 86400
                    except ValueError:
                        pass
                    break
        interact = note_card.get("interact_info", {})
        try:
            liked_count = int(interact.get("liked_count", "0"))
        except ValueError:
            liked_count = 0
        try:
            comment_count = int(interact.get("comment_count", "0"))
        except ValueError:
            comment_count = 0

        notes.append({
            "id": note_id,
            "xsec_token": xsec,
            "title": title,
            "note_url": build_share_url(note_id, xsec),
            "user_id": user_info.get("user_id", ""),
            "user_nickname": user_info.get("nickname", user_info.get("nick_name", "")),
            "desc": note_card.get("desc", ""),
            "publish_ts": publish_ts,
            "liked_count": liked_count,
            "comment_count": comment_count,
        })
    logger.info("搜索结果: %d 条笔记 (keyword=\"%s\" page=%d)", len(notes), keyword, page)
    return notes


def build_share_url(note_id: str, xsec_token: Optional[str] = None) -> str:
    """用 note_id + xsec_token 拼装桌面端免登录分享链接。

    有 xsec_token 时返回完整分享链接；
    无 xsec_token 时降级为 explore/{note_id} 短链接。
    """
    if not note_id:
        return ""
    if xsec_token:
        return (
            f"https://www.xiaohongshu.com/discovery/item/{note_id}"
            f"?source=webshare&xhsshare=pc_web"
            f"&xsec_token={xsec_token}&xsec_source=pc_share"
        )
    # 降级：explore 短链接
    return f"https://www.xiaohongshu.com/explore/{note_id}"


def discover_notes(keywords: list[str] = None,
                   pages_per_keyword: int = SEARCH_PAGES_PER_KEYWORD,
                   target_count: int = 25,
                   published_within_days: int = PUBLISHED_WITHIN_DAYS) -> list[dict]:
    """遍历关键词搜索，收集足够的笔记（去重），返回带 xsec_token 的笔记列表。"""
    keywords = keywords or SEARCH_KEYWORDS
    seen_ids: set[str] = set()
    all_notes: list[dict] = []
    search_captcha_count = 0

    for kw in keywords:
        if len(all_notes) >= target_count:
            break
        for page in range(1, pages_per_keyword + 1):
            if len(all_notes) >= target_count:
                break
            try:
                notes = search_notes(kw, page=page)
                search_captcha_count = 0
            except (RuntimeError, FileNotFoundError,
                     subprocess.TimeoutExpired, json.JSONDecodeError) as e:
                if "captcha" in str(e).lower():
                    search_captcha_count += 1
                    if search_captcha_count >= MAX_CONSECUTIVE_CAPTCHAS:
                        logger.error(
                            "搜索连续触发 %d 次验证码，疑似被风控限流，提前结束发现阶段，"
                            "已收集 %d 条笔记。建议冷却一段时间或降低 --target-count 后重试。",
                            search_captcha_count, len(all_notes),
                        )
                        return all_notes
                    cooldown = min(CAPTCHA_COOLDOWN_MAX,
                                    CAPTCHA_COOLDOWN_BASE * (2 ** (search_captcha_count - 1)))
                    logger.warning(
                        "搜索触发验证码 \"%s\" page=%d (#%d)，冷却 %d 秒后重试...",
                        kw, page, search_captcha_count, cooldown,
                    )
                    time.sleep(cooldown)
                    try:
                        notes = search_notes(kw, page=page)
                        search_captcha_count = 0
                    except Exception as retry_e:
                        logger.warning("搜索重试仍失败 \"%s\" page=%d: %s，跳过", kw, page, retry_e)
                        continue
                else:
                    logger.warning("搜索失败 \"%s\" page=%d: %s，跳过", kw, page, e)
                    continue

            for note in notes:
                nid = note["id"]
                if nid and nid not in seen_ids:
                    seen_ids.add(nid)
                    all_notes.append(note)

            if page < pages_per_keyword:
                time.sleep(SLEEP_BETWEEN_SEARCHES)

    logger.info("发现 %d 条去重笔记（目标 %d），其中 %d 条有 xsec_token",
                len(all_notes), target_count,
                sum(1 for n in all_notes if n.get("xsec_token")))

    # ── 时效性过滤 ──
    if published_within_days > 0:
        cutoff_ts = datetime.now().timestamp() - published_within_days * 86400
        fresh = [n for n in all_notes if n.get("publish_ts") and n["publish_ts"] >= cutoff_ts]
        dropped = len(all_notes) - len(fresh)
        if dropped > 0:
            logger.info("时效过滤: 丢弃 %d 条旧笔记（超过 %d 天），保留 %d 条",
                        dropped, published_within_days, len(fresh))
        all_notes = fresh

    return all_notes


# ═══════════════════════════════════════════════════════════════
# 步骤 0b：按博主抓取 → 搜索博主 → 获取其笔记列表
# ═══════════════════════════════════════════════════════════════

def search_user(keyword: str) -> dict | None:
    """用 xhs search-user 搜索博主，返回第一个匹配用户的 info dict。"""
    logger.info("搜索博主: \"%s\"", keyword)
    try:
        envelope = _xhs_subprocess(
            ["search-user", keyword, "--json"],
            timeout=30,
        )
    except (RuntimeError, subprocess.TimeoutExpired) as e:
        logger.warning("搜索博主失败: %s", e)
        return None
    users = envelope.get("data", {}).get("user_info_dtos", [])
    if not users:
        logger.warning("未找到博主: %s", keyword)
        return None
    base = users[0].get("user_base_dto", {})
    info = {
        "user_id": base.get("user_id", ""),
        "nickname": base.get("user_nickname", ""),
        "red_id": base.get("red_id", ""),
        "desc": base.get("desc", ""),
    }
    logger.info("找到博主: %s (user_id=%s)", info["nickname"], info["user_id"][:24])
    return info


def discover_notes_from_user(red_id: str,
                               pages: int = 3,
                               target_count: int = 25) -> list[dict]:
    """通过博主小红书号搜索其笔记，过滤出该博主的笔记列表。

    策略: 用 red_id 作为搜索关键词 → xhs search → 按 user_id 过滤。
    这是 user-posts API 不可用时的替代方案。
    """
    user_info = search_user(red_id)
    if not user_info:
        logger.error("无法找到博主: %s", red_id)
        return []

    user_id = user_info["user_id"]
    seen_ids: set[str] = set()
    all_notes: list[dict] = []

    for page in range(1, pages + 1):
        if len(all_notes) >= target_count:
            break
        try:
            notes = search_notes(red_id, page=page)
        except (RuntimeError, FileNotFoundError,
                 subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            logger.warning("搜索博主笔记失败 page=%d: %s，跳过", page, e)
            continue

        for note in notes:
            nid = note["id"]
            if nid and nid not in seen_ids:
                seen_ids.add(nid)
                all_notes.append(note)

        if page < pages:
            time.sleep(SLEEP_BETWEEN_SEARCHES)

    # 按 user_id 过滤（搜索结果可能包含提到该博主名的其他笔记）
    user_notes = [n for n in all_notes
                  if _extract_note_user_id(n) == user_id]

    logger.info("博主 %s: %d 条去重笔记 → 过滤后 %d 条（目标 %d），%d 条有 xsec_token",
                user_info["nickname"], len(all_notes), len(user_notes), target_count,
                sum(1 for n in user_notes if n.get("xsec_token")))
    return user_notes


def _extract_note_user_id(note: dict) -> str:
    """从搜索结果 note dict 中提取 user_id。需要在 search_notes 返回时保留。

    xhs search 返回的 item 结构:
      item.note_card.user.user_id
    """
    return note.get("user_id", "")


def parse_note_id_from_url(url: str) -> str:
    """从 explore/{id} 或 discovery/item/{id}?... 中提取 note_id。"""
    if not url:
        return ""
    # discovery/item/{id}?...
    m = re.search(r"/discovery/item/([a-fA-F0-9]+)", url)
    if m:
        return m.group(1)
    # explore/{id}
    m = re.search(r"/explore/([a-fA-F0-9]+)", url)
    if m:
        return m.group(1)
    # 可能直接就是一个 24 位 hex id
    m = re.match(r"^([a-fA-F0-9]{24})$", url.strip())
    if m:
        return m.group(1)
    return ""


def extract_xsec_from_url(url: str) -> Optional[str]:
    """从完整的 share URL 中提取 xsec_token 参数值。"""
    m = re.search(r"xsec_token=([^&]+)", url)
    return m.group(1) if m else None


# ═══════════════════════════════════════════════════════════════
# 步骤 1：获取待处理笔记列表（搜索优先，种子文件降级）
# ═══════════════════════════════════════════════════════════════

def load_target_notes(use_search: bool = True,
                      keywords: list[str] = None,
                      fallback_path: Optional[Path] = None,
                      target_count: int = 25,
                      published_within_days: int = PUBLISHED_WITHIN_DAYS) -> list[dict]:
    """获取待处理的笔记列表。

    主路径：通过 xhs search 发现笔记，提取 id + xsec_token → 拼装分享链接。
    降级路径：读取 seed_urls.txt（explore 短链接，无 xsec_token）。

    Returns:
        list[dict]: 每条包含 id, xsec_token, title, note_url
    """
    if use_search:
        try:
            notes = discover_notes(keywords=keywords, target_count=target_count,
                                    published_within_days=published_within_days)
            if notes:
                logger.info("搜索发现 %d 条笔记，使用分享链接格式", len(notes))
                return notes
            logger.warning("搜索未发现笔记，降级读取种子链接文件")
        except (FileNotFoundError, RuntimeError) as e:
            logger.warning("搜索不可用 (%s)，降级读取种子链接文件", e)

    # 降级：读取种子文件
    fallback_path = fallback_path or SEED_URLS_PATH
    notes: list[dict] = []
    if not fallback_path.exists():
        logger.warning("种子链接文件不存在: %s", fallback_path)
        return notes

    for line in fallback_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not stripped.startswith("http"):
            continue
        note_id = parse_note_id_from_url(stripped)
        xsec = extract_xsec_from_url(stripped)
        notes.append({
            "id": note_id,
            "xsec_token": xsec,
            "title": "",
            "note_url": build_share_url(note_id, xsec),
        })

    with_xsec = sum(1 for n in notes if n["xsec_token"])
    logger.info("从种子文件加载了 %d 条链接（其中 %d 条有 xsec_token）",
                len(notes), with_xsec)
    return notes


# ═══════════════════════════════════════════════════════════════
# 步骤 2：获取评论区数据
# ═══════════════════════════════════════════════════════════════

def fetch_comments(note_id_or_url: str, xsec_token: Optional[str] = None,
                   timeout: int = COMMENTS_TIMEOUT,
                   captcha_count: int = 0) -> tuple[dict, int]:
    """调用 xhs CLI 获取笔记的全部评论。

    Args:
        note_id_or_url: note_id (24 位 hex) 或 explore/discovery URL
        xsec_token: 可选的 xsec_token，用于 CLI 鉴权
        captcha_count: 当前连续验证码计数，用于计算冷却时间

    Returns:
        (comments_dict, new_captcha_count)

    Raises:
        RuntimeError: 非验证码类的 xhs CLI 错误
        FileNotFoundError: xhs CLI 未安装
    """
    note_id = parse_note_id_from_url(note_id_or_url) or note_id_or_url
    logger.info("正在获取评论: %s ...", note_id[:24])

    args = ["comments", note_id, "--all", "--json"]
    if xsec_token:
        args += ["--xsec-token", xsec_token]

    try:
        envelope = _xhs_subprocess(args, timeout=timeout)
    except FileNotFoundError:
        raise
    except (RuntimeError, subprocess.TimeoutExpired) as e:
        stderr_str = ""
        if isinstance(e, RuntimeError):
            stderr_str = str(e)
        elif hasattr(e, "stderr"):
            stderr_str = (e.stderr or "") if isinstance(e.stderr, str) else ""

        # 检测验证码触发
        if "Captcha triggered" in stderr_str or "captcha" in stderr_str.lower():
            new_count = captcha_count + 1
            cooldown = min(CAPTCHA_COOLDOWN_MAX, CAPTCHA_COOLDOWN_BASE * (2 ** (new_count - 1)))
            logger.warning(
                "触发验证码 (#%d)，冷却 %d 秒后重试...",
                new_count, cooldown,
            )
            time.sleep(cooldown)
            # 重试一次
            if new_count < MAX_CONSECUTIVE_CAPTCHAS:
                try:
                    envelope = _xhs_subprocess(args, timeout=timeout)
                except Exception:
                    return {}, new_count
            else:
                logger.error("连续触发 %d 次验证码，中止后续评论获取", new_count)
                raise RuntimeError(f"连续 {new_count} 次验证码，请手动在浏览器完成验证后重试")
        else:
            # 非验证码错误（如缺少 xsec_token），直接抛出
            raise
            # 重试成功后重置计数
            new_count = 0

    data = envelope.get("data", {})
    comments_data = data.get("comments", [])
    returned_note_id = ""
    if comments_data:
        returned_note_id = comments_data[0].get("note_id", "")
    logger.info("获取到 %d 条评论 | note_id: %s", len(comments_data), returned_note_id[:20])
    return {"comments": comments_data, "note_id": returned_note_id or note_id}, captcha_count


# ═══════════════════════════════════════════════════════════════
# 步骤 3：LLM 意图分析
# ═══════════════════════════════════════════════════════════════

INTENT_SYSTEM_PROMPT = """你是一个意图分类器。判断小红书评论区中，每条评论是否来自"有买房/租房意图的潜在客户"。

核心判断标准：这条评论是否暗示评论者本人可能在香港找房、看房、买房或租房？
如果评论者只是在闲聊、感叹、发表观点、或单纯赞美，不算。

【判定为"有意图"的情形】（符合任一条即可，包括但不限于）：
1. 求推荐：主动求推荐楼盘/小区/区域/房源，问"有什么推荐""哪个盘好""XX区怎么样"
2. 求建议：需要买房/租房决策建议，问"该不该买""现在上车合适吗""买还是租""XX盘值得入手吗"
3. 问具体信息：针对特定房源或楼盘询问具体细节，如价格、户型、面积、首付、月供、租金、学区、看房方式，暗示自己可能在考虑
4. 表达购买/租房打算：明确说"想买""打算买""准备上车""在找房""求中介/代理联系""求私信""滴滴我"
5. 对比选筹：在多个选项之间比较，如"A和B怎么选""这个盘和那个盘对比"
6. 投资评估：询问租金回报、升值潜力、税费成本等投资相关细节，暗示有投资意向

【不计入的】（即使涉及房产话题）：
- 纯感叹/闲聊："好贵啊""买不起""羡慕""好看""不错""加油""马克"
- 纯观点讨论：对房价走势、政策、市场的分析或争论，但未暗示自己有购买/租房打算
- 对博主本人而非房源的评论："你好厉害""博主好美"
- 跑题讨论：讨论与买房租房无关的话题
- 已购房者的回顾性分享（非当前在找房）："我当年买的时候才XX万"

输出要求：返回一个 JSON 对象，格式为 {"results": [true/false, ...]}，
数组长度必须等于输入的评论数，每个元素对应一条评论是否有买房/租房意图。"""


def classify_comments(comments: list[dict]) -> list[bool]:
    """用 LLM 批量判断评论是否为询盘，返回与输入等长的 bool 列表。"""
    if not comments:
        return []

    # 提取评论文本
    texts = [c.get("content", "") for c in comments]
    # 过滤完全空的
    non_empty_indices = [i for i, t in enumerate(texts) if t.strip()]

    if not non_empty_indices:
        return [False] * len(texts)

    # 构建带编号的用户 prompt
    lines = []
    for idx in non_empty_indices:
        lines.append(f"[{idx}] {texts[idx][:200]}")
    user_prompt = "请对以下评论逐一判断是否为询盘（香港买房相关）：\n" + "\n".join(lines)

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=4096,
            # 注意：Gemini Flash 的 response_format=json_object 在长 prompt 下会返回空内容，故不加
        )
        raw = resp.choices[0].message.content.strip()
        data = _parse_llm_json(raw)
        results = data.get("results", [])
    except Exception as e:
        logger.error("意图分类 LLM 调用失败: %s", e)
        # 降级：关键词规则
        logger.warning("降级为关键词规则分类")
        return [_keyword_fallback(t) for t in texts]

    # 补齐长度
    classifications = [False] * len(texts)
    for i, idx in enumerate(non_empty_indices):
        if i < len(results):
            classifications[idx] = bool(results[i])

    return classifications


def _keyword_fallback(text: str) -> bool:
    """关键词规则降级方案。"""
    keywords = [
        "多少", "价格", "总价", "首付", "月供", "怎么买", "想买",
        "楼盘", "小区", "地址", "位置", "在哪", "哪里",
        "户型", "面积", "几房", "呎", "尺", "平米",
        "看房", "联系", "滴滴", "私", "私信", "推荐",
        "学区", "校网", "学校", "收租", "回报", "投资",
        "上车", "上车盘", "笋盘", "还有吗", "有吗",
    ]
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def _parse_llm_json(raw: str) -> dict:
    """解析 LLM 返回的 JSON，容错 Markdown 代码块包裹和尾部逗号等问题。"""
    import re

    # 去除 markdown 代码块包裹
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    # 尝试直接解析
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 尝试提取第一个 { 到最后一个 } 之间的内容
    m = re.search(r"\{[\s\S]*\}", cleaned)
    if m:
        return json.loads(m.group(0))

    raise json.JSONDecodeError("无法从 LLM 响应中提取 JSON", cleaned, 0)


# ═══════════════════════════════════════════════════════════════
# 步骤 3.5：笔记视角分类（在获取评论之前过滤）
# ═══════════════════════════════════════════════════════════════

PERSPECTIVE_SYSTEM_PROMPT = """你是一个笔记视角分类器。判断小红书房产笔记的写作视角——即"谁在写、从什么角度写"。

常见视角类型：
- 素人视角：普通个人分享自己的买房/看房/装修/租房经历，第一人称叙事，真实体验
- 中介视角：房产经纪/代理发布的房源推广、带看记录，含推销语气或联系方式
- 教学向：教别人怎么买房、攻略、避坑指南、知识科普，"教你""攻略""建议"风格
- 投资客视角：从投资回报、租金收益、升值潜力、税费成本角度分析房产
- 开发商/销售视角：楼盘官方宣传、开盘信息、一手房源推广
- 媒体资讯：新闻报道、政策解读、市场数据汇总
- 租客视角：租房经历、租房体验、租金讨论

判定原则：
- 根据标题判断视角，昵称作为辅助参考
- 选择最匹配的一个视角
- 无法判断时返回"其他"
- **重要：只看笔记表面的呈现方式，不推断背后真实身份。如果笔记以第一人称"我"讲述个人经历、外表呈现为普通用户分享，就归为素人视角，即使你可能怀疑背后是中介伪装。**

输出 JSON: {"results": ["视角标签", "视角标签", ...]}
数组长度必须等于输入的笔记数，每个元素是一个视角标签字符串。"""


PERSPECTIVE_BATCH_SIZE = 60  # 单次 LLM 调用最多分类的笔记数，避免大候选池时输出被 max_tokens 截断


def _classify_perspectives_batch(notes: list[dict]) -> list[str]:
    """单批笔记视角分类（内部函数，由 classify_perspectives 分批调用）。"""
    if not notes:
        return []

    lines = []
    for i, note in enumerate(notes):
        parts = [f"标题: {note.get('title', '')}"]
        nick = note.get("user_nickname", "")
        if nick:
            parts.append(f"作者: {nick}")
        desc = note.get("desc", "")
        if desc:
            parts.append(f"摘要: {desc[:100]}")
        lines.append(f"[{i}] " + " | ".join(parts))

    user_prompt = "请对以下笔记逐一判断写作视角：\n" + "\n".join(lines)

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": PERSPECTIVE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=4096,
        )
        raw = resp.choices[0].message.content.strip()
        data = _parse_llm_json(raw)
        results = data.get("results", [])
    except Exception as e:
        logger.error("视角分类 LLM 调用失败 (批次 %d 条): %s，全部标记为'未知'", len(notes), e)
        return ["未知"] * len(notes)

    # 补齐长度
    perspectives = ["未知"] * len(notes)
    for i, label in enumerate(results):
        if i < len(perspectives):
            perspectives[i] = str(label) if label else "未知"

    return perspectives


def classify_perspectives(notes: list[dict]) -> list[str]:
    """批量分类笔记写作视角，返回与输入等长的视角标签列表。

    内部按 PERSPECTIVE_BATCH_SIZE 分批调用 LLM，避免候选池过大时单次输出
    超出 max_tokens 被截断（曾在 253 条笔记一次性分类时触发，全部退化为'未知'）。
    """
    if not notes:
        return []

    perspectives: list[str] = []
    for start in range(0, len(notes), PERSPECTIVE_BATCH_SIZE):
        batch = notes[start:start + PERSPECTIVE_BATCH_SIZE]
        perspectives.extend(_classify_perspectives_batch(batch))
        if start + PERSPECTIVE_BATCH_SIZE < len(notes):
            time.sleep(SLEEP_BETWEEN_SEARCHES)

    return perspectives


# ═══════════════════════════════════════════════════════════════
# 步骤 4：下载笔记内容（xhs read + 直接下载图片）
# ═══════════════════════════════════════════════════════════════

import tempfile
import urllib.request


def download_note_content(note_id: str, xsec_token: str = "",
                          note_url: str = "", note_title: str = "") -> Optional[Path]:
    """通过 xhs read 获取笔记详情，下载文本和图片到本地文件夹。

    流程：
      1. xhs read <note_id> --json → stdout 重定向到临时文件（避免 Rich GBK 编码问题）
      2. 解析 JSON 提取 title, desc, image_list, tag_list
      3. 保存 .txt 文本文件
      4. 下载图片到同一文件夹

    Returns:
        下载目录 Path，失败返回 None。
    """
    if not note_id:
        logger.error("下载失败：note_id 为空")
        return None

    # 输出目录
    safe_title = re.sub(r'[\\/:*?"<>|]', "_", note_title)[:40] if note_title else ""
    folder_name = f"{note_id}_{safe_title}" if safe_title else f"{note_id}_"
    out_dir = DOWNLOADS_DIR / folder_name
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── 第 1 步：xhs read → 临时文件 ──
    logger.info("正在获取笔记详情: %s ...", note_id[:24])
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="xhs_read_")
        os.close(tmp_fd)
        read_args = [XHS_CLI_CMD, "read", note_id, "--json"]
        if xsec_token:
            read_args += ["--xsec-token", xsec_token]
        proc = subprocess.run(
            read_args,
            stdout=open(tmp_path, "w", encoding="utf-8"),
            stderr=subprocess.PIPE,
            timeout=DOWNLOAD_NOTE_TIMEOUT,
            env={
                **os.environ,
                "PYTHONIOENCODING": "utf-8",
                "PYTHONLEGACYWINDOWSSTDIO": "utf-8",
            },
        )
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace") if proc.stderr else ""
            logger.error("xhs read 失败 (exit=%d): %s", proc.returncode, stderr[:200])
            return None

        with open(tmp_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error("xhs read 异常: %s", e)
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    # ── 第 2 步：解析笔记内容 ──
    items = data.get("data", {}).get("items", [])
    if not items:
        logger.error("xhs read 返回空数据")
        return None

    card = items[0].get("note_card", {})
    title = card.get("display_title", card.get("title", "")) or note_title
    desc = card.get("desc", "")
    tags = [t.get("name", "") for t in card.get("tag_list", [])]
    images = card.get("image_list", [])

    # ── 第 3 步：保存文本 ──
    txt_path = out_dir / f"{note_id}_.txt"
    txt_path.write_text(f"{title}\n\n{desc}\n\nTags: {' '.join(tags)}", encoding="utf-8")
    logger.info("文本已保存: %s (%d 字)", txt_path.name, len(desc))

    # ── 第 4 步：下载图片 ──
    downloaded_imgs = 0
    for i, img in enumerate(images):
        url = img.get("url_default", "") or img.get("url_pre", "")
        if not url:
            continue
        # 从 URL 推断扩展名
        ext = ".webp" if "webp" in url else ".jpg"
        img_path = out_dir / f"{note_id}_{i + 1}{ext}"
        try:
            urllib.request.urlretrieve(url, str(img_path))
            downloaded_imgs += 1
        except Exception as e:
            logger.warning("图片 %d 下载失败: %s", i + 1, e)

    # ── 保存元信息 ──
    meta_path = out_dir / "meta.json"
    meta_path.write_text(json.dumps({
        "note_id": note_id,
        "note_url": note_url,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(
        "笔记下载完成: %s | 文本 %d 字 | 图片 %d/%d 张",
        out_dir.name, len(desc), downloaded_imgs, len(images),
    )
    return out_dir


# ═══════════════════════════════════════════════════════════════
# 核心判断逻辑
# ═══════════════════════════════════════════════════════════════

def should_download(total_comments: int, inquiry_count: int) -> tuple[bool, str]:
    """判断是否满足触发下载的阈值条件。"""
    if total_comments == 0:
        return False, "0/0=0% 无评论"

    ratio = inquiry_count / total_comments
    cond_count = inquiry_count >= MIN_INQUIRY_COUNT
    cond_ratio = ratio >= MIN_INQUIRY_RATIO

    reason_parts = [f"{inquiry_count}/{total_comments}={ratio:.0%}"]

    if cond_count:
        reason_parts.append(f"询盘数≥{MIN_INQUIRY_COUNT} ✓")
    if cond_ratio:
        reason_parts.append(f"询盘率≥{MIN_INQUIRY_RATIO:.0%} ✓")
    if not (cond_count or cond_ratio):
        reason_parts.append("均未达标 ✗")

    triggered = cond_count or cond_ratio
    return triggered, " | ".join(reason_parts)


# ═══════════════════════════════════════════════════════════════
# 结果记录
# ═══════════════════════════════════════════════════════════════

def load_qualified_leads() -> list[dict]:
    """读取已保存的合格笔记列表。"""
    if QUALIFIED_LEADS_PATH.exists():
        try:
            return json.loads(QUALIFIED_LEADS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("qualified_leads.json 损坏，重置为空列表")
    return []


def save_qualified_lead(entry: dict):
    """追加一条合格笔记到 qualified_leads.json。"""
    leads = load_qualified_leads()
    # 去重：同 note_url 不重复记录
    if any(e.get("note_url") == entry["note_url"] for e in leads):
        logger.info("该笔记已存在于 qualified_leads.json，跳过重复记录")
        return
    leads.append(entry)
    QUALIFIED_LEADS_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUALIFIED_LEADS_PATH.write_text(
        json.dumps(leads, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("已记录到 qualified_leads.json")


# ═══════════════════════════════════════════════════════════════
# 爬取结果存档 → 01_materials/viral_examples/{时间}_爬取结果/
# ═══════════════════════════════════════════════════════════════

def save_crawl_results(results: list[dict], run_start: datetime) -> Path:
    """将本次爬取的合格笔记 URL 存档到 viral_examples 下带时间戳的文件夹。"""
    folder_name = f"{run_start.strftime('%Y-%m-%d_%H时%M分')}_爬取结果"
    crawl_dir = VIRAL_DIR / folder_name
    crawl_dir.mkdir(parents=True, exist_ok=True)

    qualified = [r for r in results if r.get("triggered")]
    if qualified:
        urls_text = "\n".join(r["note_url"] for r in qualified)
        (crawl_dir / "qualified_urls.txt").write_text(urls_text, encoding="utf-8")

    # 保存完整扫描报告
    report = {
        "scan_time": run_start.strftime("%Y-%m-%d %H:%M"),
        "total_scanned": len(results),
        "qualified_count": len(qualified),
        "notes": [
            {
                "note_id": r["note_id"],
                "title": r.get("title", ""),
                "note_url": r["note_url"],
                "perspective": r.get("perspective", ""),
                "total_comments": r.get("total_comments", 0),
                "inquiry_count": r.get("inquiry_count", 0),
                "inquiry_ratio": r.get("inquiry_ratio", 0),
                "triggered": r.get("triggered", False),
            }
            for r in results
        ],
    }
    (crawl_dir / "scan_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info("爬取结果已存档: %s (%d 条合格, %d 条扫描)", crawl_dir, len(qualified), len(results))
    return crawl_dir


# ═══════════════════════════════════════════════════════════════
# 单条笔记处理管线
# ═══════════════════════════════════════════════════════════════

def process_note(note: dict, captcha_count: int = 0) -> tuple[Optional[dict], int]:
    """处理单条笔记的完整管线：获取评论 → 意图分析 → 判断 → 下载。

    Args:
        note: {"id": str, "xsec_token": str|None, "title": str, "note_url": str}
        captcha_count: 当前连续验证码计数

    Returns:
        (entry_dict_or_None, new_captcha_count)
    """
    note_id = note["id"]
    xsec_token = note.get("xsec_token")
    note_url = note["note_url"]  # 已拼装好的分享链接
    title = note.get("title", "")

    logger.info("=" * 55)
    logger.info("处理: %s %s", note_id[:24], title[:40] if title else "")

    # ── 步骤 2: 获取评论 ──
    try:
        comments_data, captcha_count = fetch_comments(note_id, xsec_token=xsec_token, captcha_count=captcha_count)
    except (FileNotFoundError, subprocess.TimeoutExpired, RuntimeError, json.JSONDecodeError) as e:
        logger.error("获取评论失败: %s", e)
        return None, captcha_count

    comments = comments_data.get("comments", [])

    if not comments:
        logger.warning("该笔记无评论，跳过")
        return None, captcha_count

    # ── 步骤 3: 意图分析 ──
    classifications = classify_comments(comments)
    inquiry_count = sum(1 for c in classifications if c)
    total = len(comments)

    # ── 判断 ──
    triggered, reason = should_download(total, inquiry_count)
    logger.info(
        "结果: %s | 询盘 %d 条 | %s",
        "🔥 触发下载" if triggered else "⏭  跳过",
        inquiry_count,
        reason,
    )

    # 打印前几条询盘样本
    if inquiry_count > 0:
        logger.info("── 询盘样本 ──")
        shown = 0
        for i, (c, is_inq) in enumerate(zip(comments, classifications)):
            if is_inq:
                logger.info("  [%d] %s", i, c.get("content", "")[:100])
                shown += 1
                if shown >= 5:
                    break

    # ── 步骤 4: 下载笔记内容 ──
    download_dir = None
    if triggered:
        logger.info("✅ 合格笔记: %s", note_url[:100])
        download_dir = download_note_content(
            note_id, xsec_token=xsec_token or "",
            note_url=note_url, note_title=title,
        )
    download_ok = download_dir is not None

    # ── 记录结果 ──
    hk_tz = timezone(timedelta(hours=8))
    entry = {
        "note_url": note_url,
        "note_id": note_id,
        "xsec_token": xsec_token,
        "title": title,
        "perspective": note.get("perspective", ""),
        "total_comments": total,
        "inquiry_count": inquiry_count,
        "inquiry_ratio": round(inquiry_count / total, 4) if total > 0 else 0,
        "triggered": triggered,
        "download_ok": download_ok,
        "download_dir": str(download_dir) if download_dir else "",
        "scanned_at": datetime.now(hk_tz).isoformat(timespec="seconds"),
    }
    if triggered:
        save_qualified_lead(entry)

    return entry, captcha_count


# ═══════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════

def run(target_notes: Optional[list[dict]] = None,
        perspective: Optional[str] = None,
        red_id: Optional[str] = None,
        target_count: int = 25,
        published_within_days: int = PUBLISHED_WITHIN_DAYS):
    """主入口：发现笔记 → (视角过滤) → 获取评论 → 意图分类 → 输出合格链接。

    优先级：red_id（按博主抓取）> target_notes（预指定）> 关键词搜索 > seed_urls 降级。

    Args:
        target_notes: 预指定的笔记列表，为 None 时自动搜索发现
        perspective: 可选视角过滤。如 "素人" 则只处理素人视角笔记。
                     None 时不过滤视角。
        red_id: 可选博主小红书号。指定后直接从该博主主页抓取其笔记，
                不再进行关键词搜索。
        target_count: 关键词搜索阶段要凑够的候选笔记数（视角/质检过滤前），
                      默认 25。视角过滤和爆款门槛会进一步收窄最终数量。
        published_within_days: 时效性过滤窗口（天），默认取
                      PUBLISHED_WITHIN_DAYS（14）。
    """
    run_start = datetime.now(timezone(timedelta(hours=8)))
    run_start_str = run_start.strftime("%Y-%m-%d_%H-%M")

    logger.info("=" * 55)
    logger.info("  Agent 1 — 爆款笔记猎人 启动")
    logger.info("  启动时间: %s", run_start.strftime("%Y-%m-%d %H:%M"))
    logger.info("  xhs CLI: %s", XHS_CLI_CMD)
    logger.info("  下载方式: xhs read + 直接下载图片")
    logger.info("  阈值: 询盘数≥%d OR 询盘率≥%d%%", MIN_INQUIRY_COUNT, int(MIN_INQUIRY_RATIO * 100))
    logger.info("=" * 55)

    if target_notes is None:
        if red_id:
            logger.info("按博主抓取模式: %s", red_id)
            target_notes = discover_notes_from_user(red_id)
        else:
            target_notes = load_target_notes(target_count=target_count,
                                              published_within_days=published_within_days)

    if not target_notes:
        logger.warning("无待处理笔记，退出。")
        return []

    # ── 视角过滤 ──
    if perspective:
        logger.info("正在分类 %d 条笔记的写作视角...", len(target_notes))
        perspectives = classify_perspectives(target_notes)
        # 打标签
        for note, p in zip(target_notes, perspectives):
            note["perspective"] = p
        # 统计分布
        from collections import Counter
        dist = Counter(perspectives)
        logger.info("视角分布: %s", dict(dist))
        # 过滤
        before = len(target_notes)
        target_notes = [
            n for n in target_notes
            if perspective.lower() in n.get("perspective", "").lower()
        ]
        logger.info(
            "视角过滤: '%s' → %d 条中 %d 条匹配，将处理 %d 条",
            perspective, before, len(target_notes), len(target_notes),
        )
        if not target_notes:
            logger.warning("无匹配视角的笔记，退出。")
            return []

    results = []
    qualified = 0
    captcha_count = 0

    for i, note in enumerate(target_notes):
        logger.info("\n[%d/%d] %s", i + 1, len(target_notes),
                     note["id"][:24] if note.get("id") else "?")
        try:
            result, captcha_count = process_note(note, captcha_count=captcha_count)
            if result:
                results.append(result)
                if result.get("triggered"):
                    qualified += 1
        except KeyboardInterrupt:
            logger.info("用户中断")
            break
        except RuntimeError as e:
            if "验证码" in str(e):
                logger.error("%s", e)
                break
            logger.error("未处理的异常，跳过此笔记: %s", e, exc_info=True)
        except Exception as e:
            logger.error("未处理的异常，跳过此笔记: %s", e, exc_info=True)

        if i < len(target_notes) - 1:
            time.sleep(SLEEP_BETWEEN_NOTES)

    # ── 汇总 ──
    total = len(results)
    logger.info("\n" + "=" * 55)
    logger.info("扫描完成: %d/%d 条合格 | 共处理 %d 条笔记", qualified, total, len(target_notes))

    # 归档：data_pipeline/stage1_raw/qualified_urls_{启动时间}.txt
    if qualified > 0:
        qualified_urls = [r["note_url"] for r in results if r.get("triggered")]
        urls_text = "\n".join(qualified_urls)
        STAGE1_DIR.mkdir(parents=True, exist_ok=True)
        archive_path = STAGE1_DIR / f"qualified_urls_{run_start_str}.txt"
        archive_path.write_text(urls_text, encoding="utf-8")
        logger.info("合格链接归档已保存至: %s", archive_path)

    # 爬取结果存档 → 01_materials/viral_examples/{时间}_爬取结果/
    save_crawl_results(results, run_start)
    logger.info("合格线索已保存至: %s", QUALIFIED_LEADS_PATH)
    logger.info("=" * 55)

    return results


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Agent 1 — 爆款笔记猎人")
    parser.add_argument("--perspective", type=str, default=None,
                        help="视角过滤，如 '素人'、'中介'、'教学向'。不指定则不过滤。")
    parser.add_argument("--red-id", type=str, default=None,
                        help="按博主抓取模式：指定小红书号，直接从该博主主页抓取笔记。")
    parser.add_argument("--target-count", type=int, default=25,
                        help="关键词搜索阶段要凑够的候选笔记数（视角/质检过滤前）。默认 25。")
    parser.add_argument("--days", type=int, default=PUBLISHED_WITHIN_DAYS,
                        help=f"时效性过滤窗口（天）。默认 {PUBLISHED_WITHIN_DAYS}。")
    args = parser.parse_args()
    try:
        run(perspective=args.perspective, red_id=args.red_id,
            target_count=args.target_count, published_within_days=args.days)
    except KeyboardInterrupt:
        logger.info("用户中断")
    except Exception as e:
        logger.error("致命错误: %s", e, exc_info=True)
        sys.exit(1)
