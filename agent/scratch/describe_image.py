import os
import sys
import base64
import requests
import time
from pathlib import Path
from dotenv import load_dotenv

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Load environment
env_path = Path("D:/xiaohongshu_estate/agent/.env")
if env_path.exists():
    load_dotenv(env_path)

api_key = os.environ.get("GEMINI_API_KEY", "")
if not api_key:
    print("ERROR: GEMINI_API_KEY not found.")
    sys.exit(1)

img_path = Path("d:/xiaohongshu_estate/04_outputs/batch_622_final/西营盘-10_华利楼/v2/cover_原图.jpg")
if not img_path.exists():
    print(f"Error: image not found at {img_path}")
    sys.exit(1)

with open(img_path, "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode("utf-8")

models = [
    "gemini-1.5-flash",
    "gemini-2.5-flash",
    "gemini-1.5-pro",
]

prompt = (
    "Please analyze this bedroom photo in detail. Describe:\n"
    "1. The camera angle/perspective (e.g. looking straight, high/low angle, corner view, lens characteristics like wide-angle).\n"
    "2. The window layout: number of windows, shape, pane division, frames, and their exact placement relative to the walls.\n"
    "3. The room's geometry: wall positions, corners, doors, ceiling height, and floor space.\n"
    "4. Any visible furniture (bed, cabinets, wardrobe) and their positions.\n"
    "Describe everything in English in high detail, so that another model can reconstruct it without changing the perspective, layout, or windows."
)

success = False
for model in models:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"Content-Type": "application/json"}
    params = {"key": api_key}
    body = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inlineData": {"mimeType": "image/jpeg", "data": img_b64}}
            ]
        }]
    }
    
    print(f"Trying model {model}...")
    for attempt in range(3):
        try:
            resp = requests.post(url, headers=headers, params=params, json=body, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                print(f"--- Response from {model} ---")
                print(text)
                success = True
                break
            else:
                print(f"Attempt {attempt+1} failed: {resp.status_code} - {resp.text[:200]}")
                time.sleep(2)
        except Exception as e:
            print(f"Attempt {attempt+1} exception: {e}")
            time.sleep(2)
            
    if success:
        break

if not success:
    print("All models failed.")
    sys.exit(1)
