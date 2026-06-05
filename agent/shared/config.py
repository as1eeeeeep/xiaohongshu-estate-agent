"""
共享配置 — 统一管理所有 Agent 的 API 和模型分配。

模型分配原则:
  - HEAVY_MODEL (gemini-3.1-pro): 纯文本复杂推理、创意生成
  - LIGHT_MODEL (gemini-3.1-flash): 分类、简单提取等轻量任务
  - VISION_MODEL (nano-banana-2): 所有涉及图片/多模态的任务
"""

import os
from pathlib import Path

# Configure Hugging Face Mirror for stable downloading in restricted network environments
if "HF_ENDPOINT" not in os.environ:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# 自动加载 agent/.env
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)

API_KEY = os.environ.get("GEMINI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))

# 路径定义（跨平台自适应相对路径）
AGENT_DIR = Path(__file__).resolve().parent.parent  # d:\xiaohongshu_estate\agent
PROJECT_ROOT = AGENT_DIR.parent                     # d:\xiaohongshu_estate

# 各主要子目录
DATA_PIPELINE_DIR = AGENT_DIR / "data_pipeline"
STAGE1_RAW_DIR = DATA_PIPELINE_DIR / "stage1_raw"
STAGE2_PARSED_DIR = DATA_PIPELINE_DIR / "stage2_parsed"
SOP_DOCS_DIR = DATA_PIPELINE_DIR / "sop_docs"

OUTPUTS_DIR = PROJECT_ROOT / "04_outputs"
DOWNLOADS_DIR = PROJECT_ROOT / "05_20_XHS_Downloads" / "AI_Spider"
PROPERTIES_DIR = PROJECT_ROOT / "01_materials" / "properties"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# 重型模型 — 纯文本深度推理、创意写作（等待 3.5 Pro 发布后升级）
HEAVY_MODEL = "gemini-3.1-pro-preview"

# 轻型模型 — 分类、提取、解析
LIGHT_MODEL = "gemini-3.1-flash-lite"

# 视觉模型 — 所有涉及图片/多模态的任务（nano-banana-2）
VISION_MODEL = os.environ.get("VISION_MODEL", "gemini-3.1-flash-image-preview")


def get_model_for_task(task: str) -> str:
    """根据任务类型返回合适的模型。"""
    vision_tasks = {"image", "vision", "multimodal", "photo", "picture"}
    heavy_tasks = {"generate", "strategy", "creative"}
    light_tasks = {"classify", "extract", "parse", "filter", "clean"}

    task_lower = task.lower()
    for t in vision_tasks:
        if t in task_lower:
            return VISION_MODEL
    for t in heavy_tasks:
        if t in task_lower:
            return HEAVY_MODEL
    for t in light_tasks:
        if t in task_lower:
            return LIGHT_MODEL

    return LIGHT_MODEL
