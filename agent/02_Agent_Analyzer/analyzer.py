"""
Agent_Analyzer 核心拆解脚本 —— 多模态分析小红书图文笔记。
流程：配对 txt+图片 → Base64 编码 → RAG 检索 Top-2 爆款方法论 → 调用多模态 API → 输出 JSON
"""

import argparse
import os
import sys
import json
import base64
import re
import time
import datetime
from pathlib import Path
from typing import Optional

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from openai import OpenAI

# Ensure the parent `agent` directory is on sys.path for shared config
sys.path.append(str(Path(__file__).resolve().parents[1]))
from shared import API_KEY, BASE_URL, VISION_MODEL, get_run_id

# ─── 可配置项 ─────────────────────────────────────────────────
# VISION_MODEL = nano-banana-2（图文多模态提取）
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
COLLECTION_NAME = "sop_methods"
RETRIEVAL_TOP_K = 2
QUERY_PREFIX_LEN = 50
MAX_RETRIES = 3
# ─────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
STAGE1_DIR = PROJECT_ROOT / "data_pipeline" / "stage1_raw"
STAGE2_DIR = PROJECT_ROOT.parent / "04_outputs"  # base, run_id subfolder appended at runtime
KB_DIR = SCRIPT_DIR / "knowledge_base"
SYSTEM_PROMPT_PATH = SCRIPT_DIR / "system_prompt.txt"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
IMAGE_MIME_MAP = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif",
}


def image_to_data_url(image_path: Path) -> str:
    """读图片文件，返回 Base64 data URL。"""
    ext = image_path.suffix.lower()
    mime = IMAGE_MIME_MAP.get(ext, "image/jpeg")
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _scan_subdir(stage_dir: Path) -> list[dict]:
    """子目录模式：每个子目录是一条笔记，内包含 .txt + 图片。"""
    pairs = []
    for subdir in sorted(stage_dir.iterdir()):
        if not subdir.is_dir():
            continue
        txt_path = None
        images: list[Path] = []
        for f in sorted(subdir.iterdir()):
            if f.suffix.lower() in (".txt", ".md") and txt_path is None:
                txt_path = f
            elif f.suffix.lower() in IMAGE_EXTENSIONS:
                images.append(f)
        if txt_path:
            note_url = ""
            meta_path = subdir / "meta.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    note_url = meta.get("note_url", "")
                except Exception:
                    pass
            # 降级1：从目录名提取 24 位 note_id 构造 XHS 链接
            if not note_url:
                m = re.match(r"^([a-f0-9]{24})", subdir.name)
                if m:
                    note_url = f"https://www.xiaohongshu.com/explore/{m.group(1)}"
            # 降级2：本地图文没有 URL，用相对路径
            if not note_url:
                try:
                    note_url = str(subdir.relative_to(stage_dir)).replace("\\", "/")
                except ValueError:
                    note_url = subdir.name
            pairs.append({"name": subdir.name, "txt_path": txt_path, "images": images, "note_url": note_url})
            print(f"[pair] {subdir.name[:50]}: txt + {len(images)} 张图片")
    return pairs


def _scan_flat(stage_dir: Path) -> list[dict]:
    """平铺目录模式：同名 .txt/.md 与图片配对，支持 _1, _2 编号后缀。"""
    text_files = {}
    for ext in ("*.txt", "*.md"):
        for p in stage_dir.glob(ext):
            text_files[p.stem] = p

    image_files: dict[str, list[Path]] = {}
    for ext in IMAGE_EXTENSIONS:
        for p in stage_dir.glob(f"*{ext}"):
            stem = p.stem
            base = re.sub(r"_\d+$", "", stem)
            if base in text_files:
                image_files.setdefault(base, []).append(p)
            elif stem in text_files:
                image_files.setdefault(stem, []).append(p)

    pairs = []
    for name, txt_path in sorted(text_files.items()):
        images = sorted(image_files.get(name, []))
        pairs.append({"name": name, "txt_path": txt_path, "images": images})
        print(f"[pair] {name[:50]}: txt + {len(images)} 张图片")
    return pairs


def pair_notes_with_images(stage_dir: Path) -> list[dict]:
    """
    扫描目录，将同名的 .txt/.md 文件与图片配对。
    自动检测：若存在子目录且内含 .txt 文件，则按子目录模式处理；
    否则按平铺模式处理。
    """
    # 检测是否为子目录结构
    for subdir in stage_dir.iterdir():
        if subdir.is_dir():
            for f in subdir.iterdir():
                if f.suffix.lower() in (".txt", ".md"):
                    print("[scan] 检测到子目录结构，按子目录模式扫描")
                    pairs = _scan_subdir(stage_dir)
                    print(f"\n[scan] 共发现 {len(pairs)} 条笔记待处理")
                    return pairs

    print("[scan] 检测到平铺结构，按平铺模式扫描")
    pairs = _scan_flat(stage_dir)
    print(f"\n[scan] 共发现 {len(pairs)} 条笔记待处理")
    return pairs


def load_retriever() -> tuple[chromadb.PersistentClient, SentenceTransformer]:
    """初始化 ChromaDB 和 embedding 模型。"""
    model = SentenceTransformer(EMBEDDING_MODEL)
    client = chromadb.PersistentClient(
        path=str(KB_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    return client, model


def retrieve_sop(query: str, client: chromadb.PersistentClient, embed_model: SentenceTransformer) -> str:
    """检索 ChromaDB，返回拼接好的 Top-K 方法论片段。"""
    try:
        collection = client.get_collection(COLLECTION_NAME)
    except Exception:
        print("[rag] 知识库未构建，请先运行 build_kb.py。本次跳过 RAG 检索。")
        return "（知识库为空，暂无参考方法论）"

    query_vec = embed_model.encode([query], normalize_embeddings=True)[0].tolist()
    results = collection.query(query_embeddings=[query_vec], n_results=RETRIEVAL_TOP_K)

    fragments = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    for i, doc in enumerate(docs):
        src = metas[i].get("source", "unknown") if i < len(metas) else "unknown"
        fragments.append(f"【来源：{src}】\n{doc}")

    if not fragments:
        return "（未检索到相关方法论）"

    return "\n\n---\n\n".join(fragments)


def load_system_prompt(sop_text: str) -> str:
    """读取 system_prompt.txt 并拼接 RAG 检索结果。"""
    if SYSTEM_PROMPT_PATH.exists():
        template = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
    else:
        template = "你是一个专业的内容分析助手。"

    if sop_text:
        return template + f"\n\n【参考团队爆款理论】：\n{sop_text}"
    return template


def call_multimodal_api(system_prompt: str, note_text: str, image_urls: list[str]) -> Optional[dict]:
    """调用 API 分析笔记。将图片以 Base64 data URL 嵌入 multimodal message。"""
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    # 构建 multimodal user message：文本 + 图片
    user_content = [{"type": "text", "text": f"【笔记原文】\n{note_text}"}]
    for url in image_urls:
        user_content.append({
            "type": "image_url",
            "image_url": {"url": url, "detail": "auto"},
        })

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"   [api] 第 {attempt} 次调用 {VISION_MODEL}（{len(image_urls)} 张图片）...")
            resp = client.chat.completions.create(
                model=VISION_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.3,
                max_tokens=4096,
            )
            raw = resp.choices[0].message.content.strip()
            json_match = re.search(r"\{[\s\S]*\}", raw)
            if json_match:
                return json.loads(json_match.group(0))
            return {"raw_response": raw, "parse_error": "未能提取 JSON"}
        except json.JSONDecodeError:
            print(f"   [warn] JSON 解析失败，响应前 200 字: {raw[:200]}")
            if attempt < MAX_RETRIES:
                time.sleep(2)
        except Exception as e:
            print(f"   [error] API 调用异常: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(3)

    return None


def process_note(
    pair: dict,
    client: chromadb.PersistentClient,
    embed_model: SentenceTransformer,
) -> Optional[dict]:
    """处理单条笔记的完整管线。"""
    name = pair["name"]
    print(f"\n{'─' * 50}")
    print(f"[process] 开始处理: {name[:60]}")

    # 1. 读取笔记原文
    note_text = pair["txt_path"].read_text(encoding="utf-8").strip()
    if not note_text:
        print(f"[skip] {name}: 文件为空")
        return None
    print(f"   文本长度: {len(note_text)} 字")

    # 2. 图片转 Base64 data URL
    image_urls = [image_to_data_url(p) for p in pair["images"]]
    print(f"   图片编码: {len(image_urls)} 张")

    # 3. RAG 检索
    query = note_text[:QUERY_PREFIX_LEN]
    print(f"   检索 query: [{query}...]")
    sop_text = retrieve_sop(query, client, embed_model)
    sop_preview = sop_text[:120].replace("\n", " ")
    print(f"   检索结果: {sop_preview}...")

    # 4. 构建 Prompt
    system_prompt = load_system_prompt(sop_text)

    # 5. 调用多模态 API
    result = call_multimodal_api(system_prompt, note_text, image_urls)

    # 6. 附加元信息
    if result:
        result["_meta"] = {
            "note_name": name,
            "note_url": pair.get("note_url", ""),
            "images_count": len(image_urls),
            "retrieved_sop": sop_text,
        }

    return result


def main(input_dir: Optional[Path] = None, output_dir: Optional[Path] = None, run_id: Optional[str] = None):
    stage1 = Path(input_dir) if input_dir else STAGE1_DIR
    run_id = run_id or get_run_id()
    stage2 = (Path(output_dir) if output_dir else STAGE2_DIR) / run_id / "analyzed"
    print("=" * 60)
    print("  Agent_Analyzer — 多模态图文笔记拆解")
    print("=" * 60)
    print(f"  API: {BASE_URL} | Model: {VISION_MODEL}")
    print(f"  Stage1 (输入): {stage1}")
    print(f"  Stage2 (输出): {stage2}\n")

    if not stage1.exists():
        print(f"[exit] 输入目录不存在: {stage1}")
        return

    print("[init] 加载 RAG 检索器 ...")
    client, embed_model = load_retriever()
    print("[init] 就绪\n")

    pairs = pair_notes_with_images(stage1)
    if not pairs:
        print("[exit] 输入目录中没有待处理的笔记。")
        return

    stage2.mkdir(parents=True, exist_ok=True)

    success = 0
    for pair in pairs:
        result = process_note(pair, client, embed_model)

        output_path = stage2 / f"{pair['name']}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        if result:
            success += 1
            print(f"[done] 结果已保存: {output_path.name}")
        else:
            print(f"[fail] 处理失败，已保存空结果: {output_path.name}")

    print(f"\n{'=' * 60}")
    print(f"  处理完成: {success}/{len(pairs)} 条成功")
    print(f"  输出目录: {stage2}")
    print("=" * 60)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent 2 — 多模态爆款笔记拆解器")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        help="输入目录（包含 .txt + 图片的笔记文件夹），默认 stage1_raw",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="输出目录（存放分析结果 JSON），默认 04_outputs",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="管线运行时间戳（YYYYmmdd_HHMM），留空则自动生成",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    main(input_dir=args.input_dir, output_dir=args.output_dir, run_id=args.run_id)
