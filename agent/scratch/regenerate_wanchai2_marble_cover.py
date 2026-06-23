"""Find living room from 湾仔-2 6.16 source images, then generate marble cover."""
import os
import sys
import base64
import json
import requests
from pathlib import Path
from dotenv import load_dotenv
from importlib import import_module

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load environment
env_path = Path("D:/xiaohongshu_estate/agent/.env")
if env_path.exists():
    load_dotenv(env_path)

api_key = os.environ.get("GEMINI_API_KEY", "")
vision_key = os.environ.get("GEMINI_API_KEY", "")  # Use same key for vision

if not api_key:
    print("ERROR: GEMINI_API_KEY not found.")
    sys.exit(1)

# Source images directory
SOURCE_DIR = Path("D:/xiaohongshu_estate/01_materials/properties/6.16主做/"
    "【湾仔-2】銅鑼灣🇭🇰半新樓_大兩房_$850萬_交通方便🍀🏠")

# Target output directory
TARGET_DIR = Path("D:/xiaohongshu_estate/04_outputs/batch_20260622_1549/pre-published/"
    "【湾仔-2】銅鑼灣🇭🇰半新樓_大兩房_$850萬_交通方便🍀🏠")

TARGET_DIR.mkdir(parents=True, exist_ok=True)

# Find all jpg images
images = sorted([f for f in SOURCE_DIR.iterdir() if f.suffix.lower() in ('.jpg', '.jpeg', '.png')])
print(f"Found {len(images)} images in source folder.")

if not images:
    print("ERROR: No images found!")
    sys.exit(1)

# Step 1: Use Vision model to find the living room
print("\n=== Step 1: Finding living room via Vision model ===")

vision_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
vision_headers = {"Content-Type": "application/json"}
vision_params = {"key": vision_key}

# Build parts with all images
parts = []
for i, img_path in enumerate(images):
    with open(img_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")
    parts.append({"inlineData": {"mimeType": "image/jpeg", "data": img_b64}})
    parts.append({"text": f"[Image {i+1}]"})

parts.append({"text": (
    "You are a property photo classifier. Look at these images and identify which ONE is the best living room photo. "
    "A living room has: sofa/couch, coffee table, TV/TV cabinet, living area layout. "
    "Bedrooms (bed visible), kitchens (cabinets/stove), bathrooms (toilet/sink/shower) do NOT count. "
    "Respond with ONLY a JSON object: {\"living_room_index\": <1-based number>, \"confidence\": \"high/medium/low\", \"reason\": \"brief reason\"}"
)})

body = {"contents": [{"parts": parts}]}

print(f"Sending {len(images)} images for classification...")
resp = requests.post(vision_url, headers=vision_headers, params=vision_params, json=body, timeout=60)

if resp.status_code != 200:
    print(f"Vision API error: {resp.status_code} - {resp.text[:500]}")
    # Fallback: use first image
    living_room_idx = 0
    print("Falling back to first image.")
else:
    data = resp.json()
    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    print(f"Vision response: {text[:500]}")

    # Parse JSON from response
    try:
        # Try to extract JSON object
        import re
        json_match = re.search(r'\{[^}]+\}', text)
        if json_match:
            result = json.loads(json_match.group(0))
            idx = result.get("living_room_index", 1)
            living_room_idx = max(0, min(idx - 1, len(images) - 1))
            print(f"Living room identified: Image {idx} (confidence: {result.get('confidence', '?')})")
            print(f"Reason: {result.get('reason', 'N/A')}")
        else:
            living_room_idx = 0
            print("Could not parse JSON, falling back to first image.")
    except Exception as e:
        living_room_idx = 0
        print(f"Parse error: {e}, falling back to first image.")

source_image = images[living_room_idx]
print(f"Selected source: {source_image.name}")

# Step 2: Generate marble cover
print("\n=== Step 2: Generating marble-style cover ===")

with open(source_image, "rb") as f:
    image_bytes = f.read()
image_b64 = base64.b64encode(image_bytes).decode("utf-8")

# Property details: 采怡阁, 406 sq ft, 850万, 2-bedroom, 23年
AREA = 406
PRICE = 850
ROOMS = 2

marble_prompt = (
    "Transform this raw living room photo into an exquisite real estate cover image with Elegant Light Luxury Marble Staging (精致轻奢大理石风).\n\n"
    "CONTEXT:\n"
    f"Apartment type: {ROOMS}-bedroom, approximately {AREA} sq ft, priced around HKD {PRICE}M.\n"
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

image_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent"
image_headers = {"Content-Type": "application/json"}
image_params = {"key": api_key}

image_body = {
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

print("Calling Gemini image generation API...")
resp = requests.post(image_url, headers=image_headers, params=image_params, json=image_body, timeout=120)

if resp.status_code != 200:
    print(f"Image API error: HTTP {resp.status_code} - {resp.text[:500]}")
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

                cover_path = TARGET_DIR / "【湾仔-2】銅鑼灣🇭🇰半新樓_大兩房_$850萬_交通方便🍀🏠_cover.png"
                clean_path = TARGET_DIR / "【湾仔-2】銅鑼灣🇭🇰半新樓_大兩房_$850萬_交通方便🍀🏠_cover_clean.png"

                cover_path.write_bytes(img_data)
                clean_path.write_bytes(img_data)
                print(f"Saved: {cover_path.name} ({len(img_data)/1024:.1f} KB)")
                print(f"Saved: {clean_path.name} ({len(img_data)/1024:.1f} KB)")

                # Update source copy
                import shutil
                orig_path = TARGET_DIR / "【湾仔-2】銅鑼灣🇭🇰半新樓_大兩房_$850萬_交通方便🍀🏠_cover_原图.jpg"
                shutil.copy2(source_image, orig_path)
                print(f"Source updated: {orig_path.name}")

                img_saved = True
                break
    if img_saved:
        break

if not img_saved:
    print("No image data found in response.")
    sys.exit(1)

print(f"\nDone! Marble cover for 湾仔-2 generated from {source_image.name}")
