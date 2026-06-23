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

img_path = Path("d:/xiaohongshu_estate/04_outputs/batch_622_final/西营盘-10_华利楼/v2/cover_clean.png")
if not img_path.exists():
    print(f"Error: image not found at {img_path}")
    sys.exit(1)

with open(img_path, "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode("utf-8")

models = [
    "gemini-1.5-flash",
    "gemini-2.5-flash",
]

prompt = (
    "Please analyze this staged bedroom image in detail. Compare it with your knowledge of the original bedroom:\n"
    "Does this image show the exact same camera angle, perspective, walls, windows, and wainscoting as the original, or is it a completely different bedroom or perspective?\n"
    "Specifically check:\n"
    "1. Is the wainscoting (light tiled lower wall, dark geometric border) still present exactly as in the original?\n"
    "2. Are the two windows in the same place with the same frames and glass pane divisions?\n"
    "3. Is the window-style AC unit still between the windows?\n"
    "Summarize if the layout/perspective has been changed or successfully preserved."
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
                {"inlineData": {"mimeType": "image/png", "data": img_b64}}
            ]
        }]
    }
    
    print(f"Trying model {model}...")
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
            print(f"Failed: {resp.status_code} - {resp.text[:200]}")
    except Exception as e:
        print(f"Exception: {e}")
            
    if success:
        break

if not success:
    print("All models failed.")
    sys.exit(1)
