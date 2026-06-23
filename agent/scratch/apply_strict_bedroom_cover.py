import os
import sys
import shutil
from pathlib import Path

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Inject paths
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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

# Execute copying and processing
generated_img = Path("C:/Users/azzi/.gemini/antigravity-ide/brain/c285bed0-b2ae-4384-add9-e48f23f0624d/bedroom_staged_strict_cover_1782206055150.png")
final_dir = Path("d:/xiaohongshu_estate/04_outputs/batch_622_final/西营盘-10_华利楼/v2")
batch_dir = Path("d:/xiaohongshu_estate/04_outputs/batch_622_marble_20260623_0944/pre-published/【西营盘-10】华利楼_(WAH_LEE_BUILDING)🇭🇰_2房$398萬_高性价比🏠")

cover_text_rows = [
    "西营盘核心 两房",
    "平地电梯 步行5分钟地铁",
    "398万港岛上车盘"
]

if not generated_img.exists():
    print(f"Error: Generated image does not exist at {generated_img}")
    sys.exit(1)

# Temp clean path
temp_clean = final_dir / "cover_clean_temp.png"
shutil.copy2(generated_img, temp_clean)

# Generate overlay
temp_overlay = final_dir / "cover_temp.png"
local_draw_text_overlay(temp_clean, cover_text_rows, temp_overlay)

# Save final clean & overlay to final_dir
shutil.copy2(temp_overlay, final_dir / "cover.png")
shutil.copy2(temp_clean, final_dir / "cover_clean.png")
print("Saved cover.png and cover_clean.png to batch_622_final")

# Save to backup batch_dir
if batch_dir.exists():
    shutil.copy2(temp_overlay, batch_dir / "【西营盘-10】华利楼_(WAH_LEE_BUILDING)🇭🇰_2房$398萬_高性价比🏠_cover_v2.png")
    shutil.copy2(temp_clean, batch_dir / "【西营盘-10】华利楼_(WAH_LEE_BUILDING)🇭🇰_2房$398萬_高性价比🏠_cover_v2_clean.png")
    print("Saved cover_v2.png and cover_v2_clean.png to batch_622_marble_20260623_0944")

# Cleanup temp files
if temp_clean.exists():
    temp_clean.unlink()
if temp_overlay.exists():
    temp_overlay.unlink()

print("All copies and text overlays completed successfully!")
