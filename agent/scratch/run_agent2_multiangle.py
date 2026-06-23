"""对 Agent1 本次抓取的下载内容跑 Agent2 多模态分析，作为多角度写作的参考范文。"""
import sys
from pathlib import Path
from importlib import import_module

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

analyzer = import_module("02_Agent_Analyzer.analyzer")

DOWNLOADS_DIR = Path("D:/xiaohongshu_estate/04_outputs/downloads")
OUTPUT_BASE = Path("D:/xiaohongshu_estate/04_outputs")

if __name__ == "__main__":
    analyzer.main(input_dir=DOWNLOADS_DIR, output_dir=OUTPUT_BASE, run_id="multiangle_training")
