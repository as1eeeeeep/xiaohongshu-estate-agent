import os
import sys
import base64
import requests
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

img_path = Path("C:/Users/azzi/.gemini/antigravity-ide/brain/c285bed0-b2ae-4384-add9-e48f23f0624d/bedroom_staged_strict_cover_1782206055150.png")
if not img_path.exists():
    print(f"Error: image not found at {img_path}")
    sys.exit(1)

with open(img_path, "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode("utf-8")

url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
headers = {"Content-Type": "application/json"}
params = {"key": api_key}
body = {
    "contents": [{
        "parts": [
            {"text": (
                "Please analyze this staged bedroom image in detail. Compare it with the original layout:\n"
                "1. Is the wainscoting (light tiled lower wall, dark geometric border) present and identical to the original?\n"
                "2. Are the two windows in the exact same place with the same frames and glass pane divisions?\n"
                "3. Is the window-style AC unit still in the space *between* the two windows?\n"
                "4. Is the wall-mounted fan still visible to the left of the right window and below the AC unit?\n"
                "5. Is the camera perspective/angle identical, or has it shifted?\n"
                "Summarize clearly whether this image successfully preserves the original layout or if anything shifted."
            )},
            {"inlineData": {"mimeType": "image/png", "data": img_b64}}
        ]
    }]
}

print("Calling Gemini to verify new strict staged image...")
resp = requests.post(url, headers=headers, params=params, json=body, timeout=60)
if resp.status_code == 200:
    data = resp.json()
    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    print(text)
else:
    print(f"Error: {resp.status_code} - {resp.text}")
