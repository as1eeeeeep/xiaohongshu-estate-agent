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
    print("Error: GEMINI_API_KEY not found in environment.")
    sys.exit(1)

# Target directory and files
target_dir = Path("D:/xiaohongshu_estate/04_outputs/batch_20260617_1648/assembled/【湾仔-2】銅鑼灣🇭🇰半新樓_大兩房_$850萬_交通方便🍀🏠/v1")
original_image_path = target_dir / "【湾仔-2】銅鑼灣🇭🇰半新樓_大兩房_$850萬_交通方便🍀🏠_cover_原图_v1.jpg"

if not original_image_path.exists():
    print(f"Error: Original source image not found at {original_image_path}")
    sys.exit(1)

# Encode original image
with open(original_image_path, "rb") as f:
    image_bytes = f.read()
image_b64 = base64.b64encode(image_bytes).decode("utf-8")

# Strict prompt focusing on keeping window size and geometry unchanged
strict_prompt = (
    "Transform this raw living room photo into an exquisite real estate cover image with Exquisite Cozy Cream Style (精致温润奶油风).\n\n"
    "CONTEXT:\n"
    "This is a high-quality comfortable home.\n"
    "Apartment type: 2-bedroom, approximately 406 sq ft, priced around HKD 8.5M.\n"
    "⚠️ The room is exactly 406 sq ft — this is a FIXED dimension. Do NOT make it look larger.\n"
    "Desired vibe: warm cream, soft beige, light oak wood finishes, minimalist textured fabrics, chic, modern, highly refined, cozy and premium.\n\n"
    "STAGING BRIEF:\n"
    "1. LIGHTING IS EVERYTHING — add abundant, soft, uniform warm natural daylight streaming through the windows, creating a bright and healing glow. Add cozy multi-layered indoor light sources (table lamps glowing, warm overhead light) to make the space feel cozy and illuminated, not dark.\n"
    "2. Do NOT widen, expand, or stretch the room. The room boundaries, walls, ceilings, floors, and dimensions stay 100% identical to the input image.\n"
    "3. Stage the living room tastefully in the target aesthetic: a clean minimalist sofa, a soft textured rug flat on the floor, a minimalist light wood coffee table. Small staging accessories only — no major clutter.\n"
    "4. Keep the window area completely clear. Do not place any furniture, thick curtains, plants, or tall items blocking the window view or daylight.\n\n"
    "HARD RULES:\n"
    "- 🚫 DO NOT enlarge or deform the room. 406 sq ft is the real size. Making the room look larger or longer is a dealbreaker.\n"
    "- If the original photo only shows part of the room, present that part beautifully — do NOT invent or imagine extra spaces, rooms, or balconies.\n"
    "- 🚫 ABSOLUTELY NO text, letters, numbers, characters, labels, watermarks, symbols, or signatures of any language on the generated image itself.\n"
    "- 🚫 CRITICAL: Keep the size, shape, aspect ratio, frame style, panel divisions, and dimensions of the windows EXACTLY identical to the source photo. Do not enlarge, stretch, shrink, change, or deform the windows. The window geometry and window frames must be preserved perfectly.\n"
    "- 🚫 DO NOT block, cover, or obstruct any window panes or window views.\n"
    "- Maximum 1-2 small plants. Not a jungle.\n"
    "- Must look like a REAL professional photograph, not 3D render or CGI.\n"
    "- Keep original wall colors, flooring, windows, and room layout. No fake windows. No moving walls.\n"
)

# Call Gemini image-to-image API
url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent"
headers = {"Content-Type": "application/json"}
params = {"key": api_key}

body = {
    "contents": [{
        "parts": [
            {"text": strict_prompt},
            {"inlineData": {"mimeType": "image/jpeg", "data": image_b64}},
        ],
    }],
    "generationConfig": {
        "responseModalities": ["IMAGE", "TEXT"],
        "temperature": 0.85, # slightly higher temp to get variations across runs
    },
}

print("Staring generation of 5 candidates...")

for candidate_idx in range(1, 6):
    print(f"Generating Candidate {candidate_idx}/5...")
    try:
        resp = requests.post(url, headers=headers, params=params, json=body, timeout=120)
        if resp.status_code != 200:
            print(f"  Failed: HTTP {resp.status_code} - {resp.text[:300]}")
            continue
            
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            print("  Failed: No candidates returned.")
            continue
            
        img_saved = False
        for candidate in candidates:
            parts = candidate.get("content", {}).get("parts", [])
            for part in parts:
                if "inlineData" in part:
                    img_b64 = part["inlineData"].get("data", "")
                    if img_b64:
                        img_data = base64.b64decode(img_b64)
                        out_path = target_dir / f"candidate_{candidate_idx}.png"
                        out_path.write_bytes(img_data)
                        print(f"  Success: Saved to {out_path.name}")
                        img_saved = True
                        break
            if img_saved:
                break
        if not img_saved:
            print("  Failed: No inline image data found in response parts.")
    except Exception as e:
        print(f"  Exception occurred: {e}")

print("\nDone! Candidates are generated. Please inspect them.")
