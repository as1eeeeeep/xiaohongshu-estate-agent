"""Regenerate marble-style cover for 湾仔-1 using 6.22 living room image."""
import os
import sys
import base64
import requests
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Load environment variables
env_path = Path("D:/xiaohongshu_estate/agent/.env")
if env_path.exists():
    load_dotenv(env_path)

api_key = os.environ.get("GEMINI_API_KEY", "")
if not api_key:
    print("Error: GEMINI_API_KEY not found.")
    sys.exit(1)

# Source: 6.22 湾仔-3 living room image (classified as living_room in 622_images_classified.json)
SOURCE_IMAGE = Path("D:/xiaohongshu_estate/01_materials/properties/6.22主做/"
    "【湾仔-3】灣仔🇭🇰筍盤_$440萬_（現一房_🉑間兩房）_平地電梯_交通方便_🈶少少海景/"
    "【湾仔-3】灣仔🇭🇰筍盤_$440萬_（現一房_🉑間兩房）_平地電梯_交通方便_🈶少少海景_2.jpg")

# Target output directory (the batch_20260622_1549 湾仔-1 folder)
TARGET_DIR = Path("D:/xiaohongshu_estate/04_outputs/batch_20260622_1549/pre-published/"
    "【湾仔-1】灣仔🇭🇰筍盤_$440萬_（現一房_🉑間兩房）_平地電梯_交通方便_🈶少少海景")

if not SOURCE_IMAGE.exists():
    print(f"ERROR: Source image not found: {SOURCE_IMAGE}")
    sys.exit(1)

TARGET_DIR.mkdir(parents=True, exist_ok=True)

# Property details from info.md
# 积福大厦, 332 sq ft, $440万, 1-bedroom (可间两房)
AREA = 332
PRICE = 440
ROOMS = 1

# Read and encode source image
with open(SOURCE_IMAGE, "rb") as f:
    image_bytes = f.read()
image_b64 = base64.b64encode(image_bytes).decode("utf-8")

# Marble-style prompt (from run_batch_marble_all.py)
marble_prompt = (
    "Transform this raw living room photo into an exquisite real estate cover image with Elegant Light Luxury Marble Staging (精致轻奢大理石风).\n\n"
    "CONTEXT:\n"
    f"Apartment type: {ROOMS}-bedroom (can convert to 2-bedroom), approximately {AREA} sq ft, priced around HKD {PRICE}M.\n"
    f"⚠️ The room is exactly {AREA} sq ft — this is a FIXED dimension. Do NOT make it look larger.\n"
    "Desired vibe: luxurious polished white marble flooring and wall accents (大理石地板和墙面质感), "
    "delicate metallic / brass finishes (五金轻奢), high-end plush velvet or boucle upholstery, "
    "soft warm spotlights, clean and glamorous interior design with a highly aesthetic and premium look appealing to female professionals.\n\n"
    "STAGING BRIEF:\n"
    "1. LIGHTING IS EVERYTHING — add abundant, soft, uniform warm natural daylight streaming through the windows, "
    "creating a bright and glowing ambiance. Add cozy multi-layered indoor lights (soft spotlights, glowing brass lamps) "
    "to make it feel warm, high-end and illuminated.\n"
    "2. Do NOT widen, expand, or stretch the room. Room boundaries, walls, ceilings, floors, and dimensions stay 100% identical.\n"
    "3. Stage in elegant light luxury marble style: a premium modern sofa in light gray or cream boucle, "
    "a luxurious low-profile coffee table with a white polished marble top and gold metal trim, "
    "a chic minimalist area rug. Keep styling refined, clean and clutter-free.\n"
    "4. Keep the window area completely clear. Do not place any furniture, thick curtains, plants, or tall items blocking the window view or daylight.\n\n"
    "HARD RULES:\n"
    "- \U0001f6ab RED LINE — ABSOLUTELY DO NOT ENLARGE THE ROOM. Square footage, floor area, dimensions, ceiling height are FIXED. "
    "If original photo only shows one corner, stay in that corner — do NOT invent space beyond what's visible.\n"
    "- \U0001f6ab ABSOLUTELY NO text, letters, numbers, characters, labels, watermarks, symbols, or signatures of any language on the generated image itself.\n"
    "- \U0001f6ab DO NOT block, cover, or obstruct any window panes or window views.\n"
    "- Maximum 1-2 small plants. Not a jungle.\n"
    "- Must look like a REAL professional photograph, not 3D render or CGI.\n"
    "- Keep original wall colors, flooring, windows, and room layout. No fake windows. No moving walls.\n"
    "- Use polished white marble tiles for flooring (大理石地板) and add subtle luxury staging textures."
)

# Call Gemini image-to-image API
url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent"
headers = {"Content-Type": "application/json"}
params = {"key": api_key}

body = {
    "contents": [{
        "parts": [
            {"text": marble_prompt},
            {"inlineData": {"mimeType": "image/jpeg", "data": image_b64}},
        ],
    }],
    "generationConfig": {
        "responseModalities": ["IMAGE", "TEXT"],
        "temperature": 0.85,
    },
}

print(f"Source: {SOURCE_IMAGE.name}")
print(f"Target: {TARGET_DIR}")
print("Generating marble-style cover...")

try:
    resp = requests.post(url, headers=headers, params=params, json=body, timeout=120)
    if resp.status_code != 200:
        print(f"HTTP {resp.status_code}: {resp.text[:500]}")
        sys.exit(1)

    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        print("No candidates returned.")
        sys.exit(1)

    img_saved = False
    for candidate in candidates:
        parts = candidate.get("content", {}).get("parts", [])
        for part in parts:
            if "inlineData" in part:
                img_b64 = part["inlineData"].get("data", "")
                if img_b64:
                    img_data = base64.b64decode(img_b64)

                    # Save as cover.png and cover_clean.png
                    cover_path = TARGET_DIR / "【湾仔-1】灣仔🇭🇰筍盤_$440萬_（現一房_🉑間兩房）_平地電梯_交通方便_🈶少少海景_cover.png"
                    clean_path = TARGET_DIR / "【湾仔-1】灣仔🇭🇰筍盤_$440萬_（現一房_🉑間兩房）_平地電梯_交通方便_🈶少少海景_cover_clean.png"

                    cover_path.write_bytes(img_data)
                    clean_path.write_bytes(img_data)
                    print(f"Saved: {cover_path.name}")
                    print(f"Saved: {clean_path.name}")

                    # Copy source image as _cover_原图.jpg
                    import shutil
                    orig_path = TARGET_DIR / "【湾仔-1】灣仔🇭🇰筍盤_$440萬_（現一房_🉑間兩房）_平地電梯_交通方便_🈶少少海景_cover_原图.jpg"
                    shutil.copy2(SOURCE_IMAGE, orig_path)
                    print(f"Source copy: {orig_path.name}")

                    img_saved = True
                    break
        if img_saved:
            break

    if not img_saved:
        print("No image data found in response.")
        sys.exit(1)

    print("\nDone! Marble cover generated successfully.")
except Exception as e:
    print(f"Exception: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
