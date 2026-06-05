"""
爆款策略提炼脚本 —— 选取代表性笔记，用 Gemini 2.5 Pro 做系统性策略拆解。
"""

import os
import sys
import json
import base64
from pathlib import Path

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from openai import OpenAI

from shared import API_KEY, BASE_URL, VISION_MODEL, STAGE1_RAW_DIR, STAGE2_PARSED_DIR

MODEL = VISION_MODEL  # 爆款策略提炼 → 图文多模态，nano-banana-2

STAGE1 = STAGE1_RAW_DIR
STAGE2 = STAGE2_PARSED_DIR

# 精选 8 条代表不同策略维度的爆款笔记
SELECTED_NOTES = [
    # 价格冲击 + 稀缺捡漏型
    "2026-05-01_15.53.34_松鼠鼠找房OE_疯了_湾仔368万居然有平地电梯房！！！",
    # 身份带入 + 月薪买房型
    "2026-04-29_15.03.14_松鼠鼠找房OE_香港女生月薪一万8可以买房吗？",
    # 校网刚需 + 宝媽型
    "2026-05-11_10.32.22_松鼠鼠找房OE_想进湾仔十二校网？这类两房才是宝妈刚需盘",
    # 捡漏 + 校网双重钩子
    "2026-04-30_16.02.00_松鼠鼠找房OE_湾仔捡漏！465万拿下12校网3房！",
    # 品质景观 + 情绪价值型
    "2026-05-08_10.48.35_松鼠鼠找房OE_湾仔_海景_半新楼，这套真的很难不心动！",
    # 投资收租 + 校网组合型
    "2026-05-09_17.12.05_松鼠鼠找房OE_十二校网还能收租？跑马地这套配置真少见",
    # 户型解析 + 新盘型
    "2026-04-30_14.05.40_松鼠鼠找房OE_海盈山户型全解析_368伙现楼，两房成主力",
    # AI工具 + 话题引流型
    "2026-04-30_13.49.22_松鼠鼠找房OE_想在香港买房，有人知道AI找房工具吗？",
]


def load_note(name_stem: str) -> dict:
    """加载一条笔记的文本 + 首图 Base64。"""
    txt_file = STAGE1 / f"{name_stem}.txt"
    text = txt_file.read_text(encoding="utf-8").strip() if txt_file.exists() else ""

    # 找首图（_1 后缀）
    img_b64 = ""
    for ext in (".jpeg", ".jpg", ".png", ".webp"):
        img_file = STAGE1 / f"{name_stem}_1{ext}"
        if img_file.exists():
            with open(img_file, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")
            break

    # 也从 stage1_raw 找无编号后缀的图
    if not img_b64:
        for ext in (".jpeg", ".jpg", ".png", ".webp"):
            img_file = STAGE1 / f"{name_stem}{ext}"
            if img_file.exists():
                with open(img_file, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode("utf-8")
                break

    title = name_stem.split("_", 3)[-1] if "_" in name_stem else name_stem
    return {"title": title, "text": text, "image_b64": img_b64, "mime": "image/jpeg"}


def run():
    notes = [load_note(n) for n in SELECTED_NOTES]
    valid_notes = [n for n in notes if n["text"].strip()]
    print(f"加载 {len(valid_notes)}/{len(notes)} 条有效笔记\n")

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    # 构建多模态 messages
    user_content = [
        {
            "type": "text",
            "text": """你是小红书房产内容策略总教练。下面给你 8 条已验证的爆款小红书香港房产笔记（每条包含封面图 + 完整正文）。

请基于这些素材，输出一份系统性的《小红书香港房产爆款笔记方法论》。

【CRITICAL 输出格式要求】
- 必须使用标准 Markdown 层级标题（## ### ####）
- 禁止将分析内容塞入单个表格单元格
- 表格仅用于简洁的数据罗列（≤5列），宽表格必须拆分为列表
- 每个要点独立成段，段落之间有空行
- 每条笔记的分析用 **笔记N：标题** 加粗标注
- 代码块/模板用 ``` 包裹

【必须覆盖的维度】

## 一、标题与封面视觉策略
- 逐条分析每条笔记的封面图视觉风格（色彩、排版、核心大字）
- 提炼 4-6 种经过验证的标题公式，各给一个可直接套用的模板
- 总结封面图 + 标题的协同原则

## 二、钩子与正文结构
- 逐条拆解每条笔记的前 3 句话用了什么钩子手法（反常识、定价冲击、身份带入、制造焦虑等）
- 总结通用正文结构模板（黄金分段），标注每个段落的目的和字数建议
- 分析每条笔记如何将房源硬参数包装成情绪价值

## 三、客群精准对位
- 指出每条笔记瞄准的核心客群（新港人刚需、校网家长、投资客等）
- 总结不同客群应该用什么话术体系和内容角度

## 四、信息留白与转化钩子
- 逐条分析每条笔记刻意隐藏了什么信息制造信息差（楼盘名、价格、具体户型？）
- 归纳 3-5 种高转化行动号召（CTA）公式
- 分析每条笔记的评论区引导策略

## 五、可复用爆款模板库
- 为每类客群提取 1-2 个可以直接填空使用的 Markdown 笔记模板
- 每个模板标注：适用客群、标题公式、核心钩子、留白策略

请用结构化 Markdown 格式输出，每个结论都要有具体笔记案例作为佐证。""",
        }
    ]

    # 依次放每条笔记的封面图 + 文案
    for i, note in enumerate(valid_notes):
        user_content.append({
            "type": "text",
            "text": f"\n\n{'='*40}\n【爆款笔记 #{i+1}】标题：{note['title']}\n{'='*40}",
        })
        if note["image_b64"]:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{note['mime']};base64,{note['image_b64']}"},
            })
        # 控制每条文本长度
        text_limit = 2000
        text_preview = note["text"][:text_limit]
        if len(note["text"]) > text_limit:
            text_preview += "\n...（正文已截断）"
        user_content.append({"type": "text", "text": text_preview})

    print(f"发送 {len(user_content)} 个 content blocks 到 {MODEL}...\n")

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "你是一位拥有百万粉丝操盘经验的小红书房产内容策略专家。你的输出必须结构化、有案例佐证、可直接执行。使用标准 Markdown 格式，禁止将主体内容放在单格表格中。"},
                {"role": "user", "content": user_content},
            ],
            temperature=0.4,
            max_tokens=16384,
        )
    except Exception as e:
        print(f"[error] {MODEL} 调用失败: {e}")
        if MODEL == "gemini-2.5-pro":
            print("[fallback] 尝试 gemini-2.5-flash ...")
            resp = client.chat.completions.create(
                model="gemini-2.5-flash",
                messages=[
                    {"role": "system", "content": "你是一位拥有百万粉丝操盘经验的小红书房产内容策略专家。你的输出必须结构化、有案例佐证、可直接执行。使用标准 Markdown 格式，禁止将主体内容放在单格表格中。"},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.4,
                max_tokens=16384,
            )
        else:
            raise

    result = resp.choices[0].message.content

    output_path = STAGE2 / "爆款方法论_系统总结.md"
    output_path.write_text(result, encoding="utf-8")
    print(f"策略报告已保存: {output_path}")
    print(f"总长度: {len(result)} 字")
    print(f"行数: {result.count(chr(10)) + 1}")
    print("\n" + "=" * 60)
    # 打印前 500 字预览
    print(result[:500])


if __name__ == "__main__":
    run()
