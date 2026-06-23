import os
import sys
import base64
import shutil
import time
import requests
from pathlib import Path

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Inject paths
sys.path.insert(0, str(Path(__file__).resolve().parent.parent)) # d:\xiaohongshu_estate\agent
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent)) # d:\xiaohongshu_estate

from shared.config import API_KEY

# ═══════════════════════════════════════════════════════════════
# Local PIL Font & Text Overlay functions
# ═══════════════════════════════════════════════════════════════
from PIL import Image, ImageDraw, ImageFont

def load_best_font(font_size: int) -> ImageFont.ImageFont:
    for path in [
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/arial.ttf",
    ]:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, font_size)
            except Exception:
                continue
    return ImageFont.load_default()

def load_emoji_font(font_size: int) -> ImageFont.ImageFont:
    for path in [
        "C:/Windows/Fonts/seguiemj.ttf",
        "C:/Windows/Fonts/seguisym.ttf",
        "C:/Windows/Fonts/msyh.ttc",
    ]:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, font_size)
            except Exception:
                continue
    return load_best_font(font_size)

def _is_emoji_char(c: str) -> bool:
    cp = ord(c)
    if cp > 0xFFFF:
        return True
    if cp in (0x200D,):
        return True
    if 0x1F000 <= cp <= 0x1FFFF:
        return True
    if 0x231A <= cp <= 0x23FF:
        return True
    if 0x2600 <= cp <= 0x27BF:
        return True
    if 0x2B50 == cp:
        return True
    if 0xFE0F == cp:
        return True
    return False

def _draw_mixed_text(draw: ImageDraw.ImageDraw, x: int, y: int, text: str,
                      font_cjk: ImageFont.ImageFont, font_emoji: ImageFont.ImageFont,
                      fill: str = "#1A1A1A") -> None:
    segments = []
    current = ""
    current_is_emoji = False
    for ch in text:
        is_emoji = _is_emoji_char(ch)
        if not current:
            current = ch
            current_is_emoji = is_emoji
        elif is_emoji == current_is_emoji:
            current += ch
        else:
            segments.append((current, current_is_emoji))
            current = ch
            current_is_emoji = is_emoji
    if current:
        segments.append((current, current_is_emoji))

    cx = x
    for seg_text, is_emoji in segments:
        font = font_emoji if is_emoji else font_cjk
        draw.text((cx, y), seg_text, font=font, fill=fill)
        try:
            bb = draw.textbbox((0, 0), seg_text, font=font)
            cx += bb[2] - bb[0]
        except Exception:
            cx += len(seg_text) * font.size

def local_draw_text_overlay(
    image_path: Path,
    text_rows: list[str],
    output_path: Path,
) -> Path:
    img = Image.open(image_path).convert("RGB")
    width, height = img.size
    draw = ImageDraw.Draw(img)

    if not text_rows:
        img.save(output_path, "PNG")
        return output_path

    headline_rows = ["".join(c for c in r if ord(c) <= 0xFFFF) for r in text_rows[:2]]
    badge_rows = list(text_rows[2:4])
    rows = headline_rows + badge_rows
    margin = int(width * 0.04)

    base_headline_size = int(min(width, height) * 0.13)
    stroke_w = max(5, int(base_headline_size * 0.12))
    badge_fs = int(base_headline_size * 0.42)

    def row_height(fs, text, sw=0):
        try:
            f = load_best_font(fs)
            bb = draw.textbbox((0, 0), text, font=f, stroke_width=sw)
            return bb[3] - bb[1]
        except Exception:
            return fs

    budget = int(height * 0.60)
    for _ in range(15):
        stroke_w = max(5, int(base_headline_size * 0.12))
        badge_fs = int(base_headline_size * 0.42)
        total = 0
        for i, line in enumerate(rows):
            if not line:
                continue
            fs = base_headline_size if i < 2 else badge_fs
            sw = stroke_w if i < 2 else 0
            total += row_height(fs, line, sw) + int(height * 0.022)
        if total <= budget:
            break
        base_headline_size = int(base_headline_size * 0.92)

    for i, line in enumerate(rows[:2]):
        if not line:
            continue
        fs = base_headline_size
        font = load_best_font(fs)
        for _ in range(10):
            try:
                bb = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_w)
                tw = bb[2] - bb[0]
            except Exception:
                tw = len(line) * fs
            if tw <= width - margin * 2:
                break
            fs = int(fs * 0.90)
            font = load_best_font(fs)

    y = int(height * 0.04)

    for i, line in enumerate(rows):
        if not line:
            continue

        if i < 2:
            fill_color = "#FFE300" if i == 0 else "#FFFFFF"
            fs = base_headline_size
            font = load_best_font(fs)
            for _ in range(10):
                try:
                    bb = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_w)
                    tw = bb[2] - bb[0]
                except Exception:
                    tw = len(line) * fs
                if tw <= width - margin * 2:
                    break
                fs = int(fs * 0.90)
                font = load_best_font(fs)

            try:
                bb = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_w)
                tw, th = bb[2] - bb[0], bb[3] - bb[1]
            except Exception:
                tw, th = len(line) * fs, fs

            x = (width - tw) // 2
            draw.text((x, y), line, font=font, fill=fill_color,
                      stroke_width=stroke_w, stroke_fill="#000000")
            y += th + int(height * 0.022)

        elif i == 2:
            fs = badge_fs
            font_cjk = load_best_font(fs)
            font_emoji = load_emoji_font(fs)
            try:
                bb = draw.textbbox((0, 0), line, font=font_cjk)
                tw, th = bb[2] - bb[0], bb[3] - bb[1]
            except Exception:
                tw, th = len(line) * fs, fs

            px, py = int(fs * 0.5), int(fs * 0.25)
            rw, rh = tw + px * 2, th + py * 2
            rx = (width - rw) // 2
            y += int(height * 0.01)

            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            odraw = ImageDraw.Draw(overlay)
            odraw.rounded_rectangle([rx, y, rx + rw, y + rh],
                                    radius=rh // 2, fill=(255, 255, 255, 76))
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
            draw = ImageDraw.Draw(img)

            _draw_mixed_text(draw, rx + px, y + py, line, font_cjk, font_emoji)
            y += rh + int(height * 0.015)

        elif i == 3:
            fs = badge_fs
            font_cjk = load_best_font(fs)
            font_emoji = load_emoji_font(fs)
            try:
                bb = draw.textbbox((0, 0), line, font=font_cjk)
                tw, th = bb[2] - bb[0], bb[3] - bb[1]
            except Exception:
                tw, th = len(line) * fs, fs

            px, py = int(fs * 0.5), int(fs * 0.22)
            rw, rh = tw + px * 2, th + py * 2
            rx = (width - rw) // 2

            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            odraw = ImageDraw.Draw(overlay)
            odraw.rounded_rectangle([rx, y, rx + rw, y + rh],
                                    radius=10, fill=(255, 227, 0, 76))
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
            draw = ImageDraw.Draw(img)

            _draw_mixed_text(draw, rx + px, y + py, line, font_cjk, font_emoji, fill="#111111")

    img.save(output_path, "PNG")
    print(f"Successfully drew and saved overlay text to: {output_path.name}")
    return output_path

# ═══════════════════════════════════════════════════════════════
# Gemini Image Gen call with retry loop and low temperature (0.1)
# ═══════════════════════════════════════════════════════════════
def local_call_gemini_image_gen(image_path: str, prompt: str, api_key: str):
    print("Reading and encoding source image...")
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    ext = Path(image_path).suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    mime_type = mime_map.get(ext, "image/jpeg")

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent"
    headers = {"Content-Type": "application/json"}
    params = {"key": api_key}

    # Set temperature to 0.1 for high structural preservation
    body = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inlineData": {"mimeType": mime_type, "data": image_b64}},
            ],
        }],
        "generationConfig": {
            "responseModalities": ["IMAGE", "TEXT"],
            "temperature": 0.1, 
        },
    }

    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        print(f"Sending POST request to Gemini Model (Attempt {attempt}/{max_attempts})...")
        try:
            resp = requests.post(url, headers=headers, params=params, json=body, timeout=120)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                for candidate in candidates:
                    parts = candidate.get("content", {}).get("parts", [])
                    for part in parts:
                        if "inlineData" in part:
                            img_b64 = part["inlineData"].get("data", "")
                            if img_b64:
                                print("Successfully retrieved image bytes from Gemini.")
                                return base64.b64decode(img_b64)
                print("[WARNING] Image data not found in 200 response candidates.")
            elif resp.status_code == 503:
                print(f"Gemini API returned 503 Service Unavailable (spiked demand).")
            else:
                print(f"Gemini API returned {resp.status_code}: {resp.text[:500]}")
                
        except Exception as e:
            print(f"Error during Gemini call: {e}")
            
        if attempt < max_attempts:
            sleep_time = 4.0 * attempt
            print(f"Retrying in {sleep_time} seconds...")
            time.sleep(sleep_time)

    return None

# ═══════════════════════════════════════════════════════════════
# Prompt Builder (Extra Strict on Perspective and Window Layout)
# ═══════════════════════════════════════════════════════════════
def custom_build_cover_prompt(property_data, room_type="bedroom"):
    style_name = "Elegant Light Luxury Marble Staging (精致轻奢大理石风)"
    vibe = "luxurious polished white marble flooring or wall accents (大理石质感), delicate metallic / brass finishes (五金轻奢), high-end plush velvet or bouclé upholstery, soft warm spotlights, clean and glamorous interior design with a highly aesthetic and premium look appealing to female professionals"
    
    room_label = "bedroom"
    staging_guide = (
        "Stage the bedroom elegantly in light luxury marble style: premium velvet tufted headboard, "
        "soft high-thread-count bedding in cream or white, bedside nightstands with white marble tops "
        "and gold handles, soft glowing warm brass bedside lamps, and a cozy area rug."
    )
        
    area = property_data.get("area_sqft", "314")
    price = property_data.get("price_wan", "398")
    rooms = property_data.get("rooms", "2")
    room_desc = f"{rooms}-bedroom" if rooms else ""
    
    prompt = (
        f"Transform this raw {room_label} photo into an exquisite real estate cover image with {style_name}.\n\n"
        f"CONTEXT:\n"
        f"Apartment type: {room_desc}, approximately {area} sq ft, priced around HKD {price}M.\n"
        f"Desired vibe: {vibe}.\n"
        f"STAGING BRIEF:\n"
        f"1. LIGHTING IS EVERYTHING — add abundant, soft, uniform warm natural daylight streaming through the windows, creating a bright and glowing ambiance. Add cozy multi-layered indoor lights (soft spotlights, glowing brass lamps) to make it feel warm, high-end and illuminated.\n"
        f"2. Keep the window area completely clear. Do not place any furniture, thick curtains, plants, or tall items blocking the window view or daylight.\n"
        f"3. {staging_guide}\n\n"
        f"CRITICAL PIXEL-ALIGNED STRUCTURE PRESERVATION RULES (HARD RED LINES):\n"
        f"- 🚫 DO NOT CHANGE THE CAMERA ANGLE, VIEWPOINT, ZOOM, TILT, ROTATION, OR PERSPECTIVE. The camera position and focal length of the output image must be 100% IDENTICAL and pixel-aligned with the input raw photo. Do not move the camera by even a fraction of a degree.\n"
        f"- 🚫 DO NOT MODIFY, MOVE, REDRAW, OR ALTER THE WINDOWS, WINDOW PANES, WINDOW FRAMES, OR BALCONY DOOR layout. The shape, position, sizes, lines, and configurations of the windows and doors must remain exactly identical to the input raw photo. Keep the window exactly as-is.\n"
        f"- 🚫 DO NOT move walls, columns, ceilings, floors, or structural borders. Keep the boundaries of the bedroom 100% frozen in place. The walls and corners must line up exactly with the input photo.\n"
        f"- This is a virtual staging (虚拟样板间/虚拟软装) overlay. Keep all structural elements unchanged, only change superficial textures (polished marble texture for accents, cream paint for walls) and add furniture staging items (bed cover, pillow, bedside accessories).\n"
        f"- 🚫 ABSOLUTELY NO text, letters, numbers, characters, labels, watermarks, symbols, or signatures of any language on the generated image itself.\n"
        f"- 🚫 DO NOT block, cover, or obstruct any window panes or window views.\n"
        f"- Maximum 1-2 small plants. Not a jungle.\n"
        f"- Must look like a REAL professional photograph, not 3D render or CGI.\n"
    )
    return prompt

# ═══════════════════════════════════════════════════════════════
# Execution
# ═══════════════════════════════════════════════════════════════
source_img = Path("d:/xiaohongshu_estate/04_outputs/batch_622_final/西营盘-10_华利楼/v2/cover_原图.jpg")
final_dir = Path("d:/xiaohongshu_estate/04_outputs/batch_622_final/西营盘-10_华利楼/v2")
batch_dir = Path("d:/xiaohongshu_estate/04_outputs/batch_622_marble_20260623_0944/pre-published/【西营盘-10】华利楼_(WAH_LEE_BUILDING)🇭🇰_2房$398萬_高性价比🏠")

property_data = {
    "name": "西营盘-10_华利楼",
    "district": "西营盘",
    "sub_district": "西营盘",
    "price_wan": 398,
    "rooms": 2,
    "area_sqft": 314,
    "has_lift": True,
    "lift_type": "平地电梯"
}

cover_text_rows = [
    "西营盘核心 两房",
    "平地电梯 步行5分钟地铁",
    "398万港岛上车盘"
]

print("Building cover prompt...")
prompt_str = custom_build_cover_prompt(property_data, room_type="bedroom")
print(f"Prompt content length: {len(prompt_str)} characters.")

print("Calling Gemini Image Gen API with Low Temp...")
image_data = local_call_gemini_image_gen(str(source_img.resolve()), prompt_str, API_KEY)

if not image_data:
    print("[ERROR] Gemini image generation failed after retries!")
    sys.exit(1)

# Temp paths for staging
temp_clean = final_dir / "cover_clean_temp.png"
temp_clean.write_bytes(image_data)
print(f"Generated clean cover in temp path: {temp_clean.name}")

# Perform text overlay
temp_overlay = final_dir / "cover_temp.png"
print("Overlaying text onto cover image...")
local_draw_text_overlay(
    image_path=temp_clean,
    text_rows=cover_text_rows,
    output_path=temp_overlay
)

# Overwrite in batch_622_final
shutil.copy2(temp_overlay, final_dir / "cover.png")
shutil.copy2(temp_clean, final_dir / "cover_clean.png")
print("Updated files in batch_622_final/西营盘-10_华利楼/v2/")

# Overwrite in batch_622_marble_20260623_0944
if batch_dir.exists():
    shutil.copy2(temp_overlay, batch_dir / "【西营盘-10】华利楼_(WAH_LEE_BUILDING)🇭🇰_2房$398萬_高性价比🏠_cover_v2.png")
    shutil.copy2(temp_clean, batch_dir / "【西营盘-10】华利楼_(WAH_LEE_BUILDING)🇭🇰_2房$398萬_高性价比🏠_cover_v2_clean.png")
    print("Updated files in batch_622_marble_20260623_0944/pre-published/...")

# Clean up temp files
if temp_clean.exists():
    temp_clean.unlink()
if temp_overlay.exists():
    temp_overlay.unlink()

print("Bedroom cover regeneration with strict pixel-aligned perspective completed successfully!")
