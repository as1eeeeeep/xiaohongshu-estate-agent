from .config import (
    API_KEY, BASE_URL, HEAVY_MODEL, LIGHT_MODEL, VISION_MODEL,
    AGENT_DIR, PROJECT_ROOT, DATA_PIPELINE_DIR, STAGE1_RAW_DIR,
    STAGE2_PARSED_DIR, SOP_DOCS_DIR, OUTPUTS_DIR, DOWNLOADS_DIR, PROPERTIES_DIR
)


import re
from datetime import datetime


def get_run_id() -> str:
    """Generate a pipeline run ID from current time, precise to minute."""
    return datetime.now().strftime("%Y%m%d_%H%M")


def sanitize_filename(name: str, max_len: int = 80) -> str:
    """Replace illegal filename characters and trim to max length."""
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = name.strip().strip(".")
    return name[:max_len]
