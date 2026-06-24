#!/usr/bin/env python3
import argparse
import base64
import json
import mimetypes
import os
import shutil
import sys
import time
from pathlib import Path

from google import genai
from google.genai import types
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageStat


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = ROOT.parent.parent / "04_outputs"  # 松鼠找房/04_outputs，与 Agent3 的笔记输出共享
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def load_text(path):
    return path.read_text(encoding="utf-8")


def load_config():
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def load_dotenv():
    for env_path in (ROOT / ".env", ROOT.parent / ".env"):
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def image_to_data_url(path):
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{data}"


def image_part(path):
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return types.Part.from_bytes(data=path.read_bytes(), mime_type=mime)


def list_images(input_dir):
    images = [
        path
        for path in sorted(Path(input_dir).iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    if not images:
        raise SystemExit(f"No supported images found in {input_dir}")
    return images


def extract_json(text):
    start = text.find("{")
    if start == -1:
        raise ValueError(f"Model did not return JSON: {text}")
    
    count = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        char = text[i]
        if escape:
            escape = False
            continue
        if char == '\\':
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if not in_string:
            if char == '{':
                count += 1
            elif char == '}':
                count -= 1
                if count == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        pass
                        
    # Fallback to simple rfind
    end = text.rfind("}")
    if end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
            
    raise ValueError(f"Model did not return JSON: {text}")


def response_text(response):
    text = getattr(response, "text", None)
    if text:
        return text
    parts = getattr(response, "parts", None) or []
    return "\n".join(getattr(part, "text", "") for part in parts if getattr(part, "text", None))


def save_gemini_image(response, output_path):
    parts = getattr(response, "parts", None)
    if not parts and getattr(response, "candidates", None):
        parts = response.candidates[0].content.parts

    for part in parts or []:
        inline_data = getattr(part, "inline_data", None)
        if inline_data and getattr(inline_data, "data", None):
            output_path.write_bytes(inline_data.data)
            return
        if hasattr(part, "as_image"):
            image = part.as_image()
            if image is not None:
                image.save(output_path)
                return
    raise ValueError("Gemini did not return an image.")


def closest_aspect_ratio(image_path):
    width, height = Image.open(image_path).size
    source_ratio = width / height
    options = {
        "1:1": 1,
        "4:3": 4 / 3,
        "3:4": 3 / 4,
        "16:9": 16 / 9,
        "9:16": 9 / 16,
    }
    return min(options, key=lambda key: abs(options[key] - source_ratio))


def match_source_geometry(image_path, source_image_path):
    source = Image.open(source_image_path)
    image = Image.open(image_path).convert("RGB")
    target_w, target_h = source.size
    target_ratio = target_w / target_h
    width, height = image.size
    ratio = width / height

    if abs(ratio - target_ratio) > 0.001:
        if ratio > target_ratio:
            new_w = round(height * target_ratio)
            left = max(0, (width - new_w) // 2)
            image = image.crop((left, 0, left + new_w, height))
        else:
            new_h = round(width / target_ratio)
            top = max(0, (height - new_h) // 2)
            image = image.crop((0, top, width, top + new_h))

    if image.size != source.size:
        image = image.resize(source.size, Image.LANCZOS)
    image.save(image_path, quality=95)


def create_client(config):
    provider = config.get("provider", "openai")
    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise SystemExit("GEMINI_API_KEY is not set.")
        return genai.Client(api_key=api_key), provider
    if provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            raise SystemExit("OPENAI_API_KEY is not set.")
        return OpenAI(), provider
    raise SystemExit(f"Unsupported provider: {provider}")


def with_retries(operation, attempts=3, delay_seconds=4):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as error:
            last_error = error
            message = str(error)
            retryable = any(code in message for code in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED"))
            if attempt == attempts or not retryable:
                raise
            print(f"Provider busy, retrying in {delay_seconds}s ({attempt}/{attempts})...", file=sys.stderr)
            time.sleep(delay_seconds)
    raise last_error


def select_cover_image(client, provider, images, config):
    if provider == "gemini":
        return select_cover_image_gemini(client, images, config)
    return select_cover_image_openai(client, images, config)


def select_cover_image_openai(client, images, config):
    prompt = load_text(ROOT / "prompts" / "select_image.md")
    content = [{"type": "input_text", "text": prompt}]

    for index, image_path in enumerate(images, start=1):
        content.append({"type": "input_text", "text": f"Image index: {index}"})
        content.append(
            {
                "type": "input_image",
                "image_url": image_to_data_url(image_path),
                "detail": "high",
            }
        )

    response = client.responses.create(
        model=config["selection_model"],
        input=[{"role": "user", "content": content}],
    )
    selection = extract_json(response.output_text)
    validate_selection(selection, len(images))
    return normalize_selection(selection)


def select_cover_image_gemini(client, images, config):
    prompt = load_text(ROOT / "prompts" / "select_image.md")
    parts = [types.Part.from_text(text=prompt)]
    for index, image_path in enumerate(images, start=1):
        parts.append(types.Part.from_text(text=f"Image index: {index}"))
        parts.append(image_part(image_path))

    response = with_retries(
        lambda: client.models.generate_content(
            model=config["gemini_selection_model"],
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
    )
    selection = extract_json(response_text(response))
    validate_selection(selection, len(images))
    return normalize_selection(selection)


def validate_selection(selection, image_count):
    allowed_rooms = {"living_room", "bedroom", "dining", "kitchen", "study", None}
    allowed_confidence = {"high", "medium", "low"}

    if selection.get("room_type") not in allowed_rooms:
        raise ValueError(f"Invalid room_type: {selection}")
    if selection.get("confidence") not in allowed_confidence:
        raise ValueError(f"Invalid confidence: {selection}")

    image_index = selection.get("image_index")
    if image_index is None:
        return
    if not isinstance(image_index, int) or image_index < 1 or image_index > image_count:
        raise ValueError(f"Invalid image_index: {selection}")


def normalize_selection(selection):
    reason = selection.get("reason", "")
    room_type = selection.get("room_type")
    if room_type == "study":
        selection["room_type"] = "living_room"
        selection["confidence"] = "medium"
        selection["reason"] = f"{reason} 已按四分类规则将工作/多功能起居空间归入客厅。"
    return selection


def build_renovation_prompt(room_type, decor_style=None):
    base_prompt = load_text(ROOT / "prompts" / "renovate.md")
    prompt = (
        f"{base_prompt}\n\n"
        f"当前房间类型是：{room_type}。\n"
        "严格只应用该房间类型对应的软装指引，禁止跨类型混搭。"
    )
    if decor_style:
        prompt += (
            f"\n\n本次整体装修风格基调：{decor_style}。"
            "在不违反以上所有红线规则的前提下，只通过地面/台面/墙面材质质感和软装搭配体现"
            "该风格，不能为了风格效果而放大房间、遮挡窗户、改变户型或添加文字水印。"
        )
    return prompt


def renovate_image(client, provider, source_image, selection, config, output_path, retry_instruction="", decor_style=None):
    if provider == "gemini":
        return renovate_image_gemini(client, source_image, selection, config, output_path, retry_instruction, decor_style)
    return renovate_image_openai(client, source_image, selection, config, output_path, retry_instruction, decor_style)


def renovation_prompt_with_retry(selection, retry_instruction="", decor_style=None):
    prompt = build_renovation_prompt(selection["room_type"], decor_style)
    if retry_instruction:
        prompt = (
            f"{prompt}\n\n"
            "上一次质检不通过。这次必须修正："
            f"{retry_instruction}"
        )
    return prompt


def renovate_image_openai(client, source_image, selection, config, output_path, retry_instruction="", decor_style=None):
    prompt = renovation_prompt_with_retry(selection, retry_instruction, decor_style)
    with source_image.open("rb") as image_file:
        result = client.images.edit(
            model=config["image_model"],
            image=image_file,
            prompt=prompt,
            quality=config["image_quality"],
            size=config["output_size"],
        )

    image_base64 = result.data[0].b64_json
    output_path.write_bytes(base64.b64decode(image_base64))
    match_source_geometry(output_path, source_image)


def renovate_image_gemini(client, source_image, selection, config, output_path, retry_instruction="", decor_style=None):
    aspect_ratio = closest_aspect_ratio(source_image)
    prompt = (
        f"{renovation_prompt_with_retry(selection, retry_instruction, decor_style)}\n\n"
        f"输出必须保持和原图一致的画面方向与宽高比例，使用 {aspect_ratio} 构图。"
    )
    response = with_retries(
        lambda: client.models.generate_content(
            model=config["gemini_image_model"],
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        image_part(source_image),
                        types.Part.from_text(text=prompt),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
            ),
        ),
    )
    save_gemini_image(response, output_path)
    match_source_geometry(output_path, source_image)


def review_renovation(client, provider, source_image, generated_image, config):
    if provider == "gemini":
        return review_renovation_gemini(client, source_image, generated_image, config)
    return review_renovation_openai(client, source_image, generated_image, config)


def review_renovation_openai(client, source_image, generated_image, config):
    prompt = load_text(ROOT / "prompts" / "qa.md")
    response = client.responses.create(
        model=config["selection_model"],
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_text", "text": "原始房源照片："},
                    {
                        "type": "input_image",
                        "image_url": image_to_data_url(source_image),
                        "detail": "high",
                    },
                    {"type": "input_text", "text": "生成后的纯装修无字图："},
                    {
                        "type": "input_image",
                        "image_url": image_to_data_url(generated_image),
                        "detail": "high",
                    },
                ],
            }
        ],
    )
    return extract_json(response.output_text)


def review_renovation_gemini(client, source_image, generated_image, config):
    prompt = load_text(ROOT / "prompts" / "qa.md")
    response = with_retries(
        lambda: client.models.generate_content(
            model=config["gemini_selection_model"],
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_text(text="原始房源照片："),
                        image_part(source_image),
                        types.Part.from_text(text="生成后的纯装修无字图："),
                        image_part(generated_image),
                    ],
                )
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
    )
    return extract_json(response_text(response))


def find_font(config, size):
    for font_path in config.get("font_candidates", []):
        if Path(font_path).exists():
            return ImageFont.truetype(font_path, size=size)
    return ImageFont.load_default()


def wrap_text(text, font, max_width, draw):
    lines = []
    current = ""
    for char in text:
        candidate = current + char
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


def draw_text_with_shadow(draw, position, text, font, fill, shadow_fill):
    x, y = position
    for dx, dy in ((0, 2), (2, 2), (2, 0)):
        draw.text((x + dx, y + dy), text, font=font, fill=shadow_fill)
    draw.text((x, y), text, font=font, fill=fill)


def region_luminance(image, box):
    crop = image.crop(box).resize((80, 80))
    r, g, b = ImageStat.Stat(crop).mean[:3]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def choose_text_palette(image, box, mood="warm"):
    luminance = region_luminance(image, box)
    if luminance > 178:
        palettes = {
            "warm": ((82, 59, 42, 255), (255, 246, 232, 210)),
            "green": ((43, 70, 58, 255), (242, 248, 240, 210)),
        }
    elif luminance > 115:
        palettes = {
            "warm": ((255, 244, 224, 255), (67, 51, 40, 150)),
            "green": ((235, 242, 220, 255), (30, 54, 43, 155)),
        }
    else:
        palettes = {
            "warm": ((255, 238, 210, 255), (20, 18, 16, 145)),
            "green": ((230, 245, 220, 255), (12, 28, 20, 145)),
        }
    return palettes[mood]


def style_editorial(canvas, title, subtitle, config):
    image = canvas.convert("RGB")
    width, height = image.size
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    fill, _shadow = choose_text_palette(image, (0, 0, int(width * 0.55), int(height * 0.28)), "warm")

    for y in range(int(height * 0.36)):
        alpha = int(82 * max(0, 1 - y / (height * 0.36)))
        draw.rectangle((0, y, int(width * 0.62), y + 1), fill=(255, 246, 232, alpha))

    title_y = int(height * 0.064)
    subtitle_y = title_y + int(width * 0.078)
    draw.text((int(width * 0.055), title_y), title, font=find_font(config, int(width * 0.052)), fill=fill)
    if subtitle:
        draw.text(
            (int(width * 0.058), subtitle_y),
            subtitle,
            font=find_font(config, int(width * 0.020)),
            fill=(fill[0], fill[1], fill[2], 220),
        )
    canvas.alpha_composite(overlay)


def style_soft_card(canvas, title, subtitle, config):
    width, height = canvas.size
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    x, y = int(width * 0.045), int(height * 0.68)
    card_w, card_h = int(width * 0.45), int(height * 0.20)
    draw.rounded_rectangle(
        (x, y, x + card_w, y + card_h),
        radius=10,
        fill=(246, 239, 226, 224),
        outline=(222, 205, 184, 210),
        width=2,
    )
    draw.text((x + int(width * 0.025), y + int(height * 0.035)), title, font=find_font(config, int(width * 0.043)), fill=(91, 64, 45, 255))
    if subtitle:
        draw.text((x + int(width * 0.026), y + int(height * 0.115)), subtitle, font=find_font(config, int(width * 0.020)), fill=(120, 91, 68, 245))
    canvas.alpha_composite(overlay)


def style_vertical(canvas, title, subtitle, config):
    width, height = canvas.size
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    grad_w = int(width * 0.27)
    for x in range(width - grad_w, width):
        alpha = int(118 * ((x - (width - grad_w)) / grad_w))
        draw.rectangle((x, 0, x + 1, height), fill=(14, 18, 19, alpha))

    title_font = find_font(config, int(width * 0.038))
    x = int(width * 0.89)
    y = int(height * 0.12)
    for char in title:
        draw_text_with_shadow(draw, (x, y), char, title_font, (245, 219, 174, 255), (0, 0, 0, 150))
        y += int(width * 0.046)
    if subtitle:
        parts = subtitle.replace("｜", "/").split("/")
        for index, part in enumerate(parts[:2]):
            draw.text((int(width * 0.79), int(height * (0.72 + index * 0.045))), part.strip(), font=find_font(config, int(width * 0.017)), fill=(245, 219, 174, 230))
    canvas.alpha_composite(overlay)


def style_cinematic_band(canvas, title, subtitle, config):
    width, height = canvas.size
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    band_y = int(height * 0.74)
    draw.rectangle((0, band_y, width, height), fill=(31, 30, 27, 150))
    draw.rectangle((int(width * 0.055), band_y + int(height * 0.035), int(width * 0.065), band_y + int(height * 0.165)), fill=(196, 157, 97, 235))
    draw.text((int(width * 0.082), band_y + int(height * 0.045)), title, font=find_font(config, int(width * 0.047)), fill=(238, 226, 205, 255))
    if subtitle:
        draw.text((int(width * 0.084), band_y + int(height * 0.13)), subtitle.replace("｜", " / "), font=find_font(config, int(width * 0.018)), fill=(214, 198, 174, 235))
    canvas.alpha_composite(overlay)


def style_xhs_sticker(canvas, title, subtitle, config):
    image = canvas.convert("RGB")
    width, height = image.size
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    x, y = int(width * 0.055), int(height * 0.055)
    sticker_h = int(height * 0.062)
    draw.rounded_rectangle((x, y, x + int(width * 0.31), y + sticker_h), radius=18, fill=(235, 241, 225, 235))
    draw.text((x + int(width * 0.018), y + int(height * 0.016)), "真实房源｜精装客厅", font=find_font(config, int(width * 0.018)), fill=(47, 78, 59, 255))
    fill, shadow = choose_text_palette(image, (x, y + int(height * 0.12), x + int(width * 0.48), y + int(height * 0.30)), "green")
    title_y = y + int(height * 0.125)
    subtitle_y = title_y + int(width * 0.082)
    draw_text_with_shadow(draw, (x, title_y), title, find_font(config, int(width * 0.058)), fill, shadow)
    if subtitle:
        draw_text_with_shadow(draw, (x + 2, subtitle_y), subtitle, find_font(config, int(width * 0.022)), (70, 94, 75, 245), (255, 255, 255, 130))
    canvas.alpha_composite(overlay)


COVER_STYLES = {
    "editorial": style_editorial,
    "card": style_soft_card,
    "vertical": style_vertical,
    "band": style_cinematic_band,
    "xhs": style_xhs_sticker,
}


def create_text_cover(no_text_path, output_path, title, subtitle, config, cover_style="editorial"):
    image = Image.open(no_text_path).convert("RGB")
    canvas = image.convert("RGBA")
    COVER_STYLES[cover_style](canvas, title, subtitle, config)
    canvas.convert("RGB").save(output_path, quality=95)


def create_style_variants(no_text_path, output_dir, title, subtitle, config):
    for style in COVER_STYLES:
        create_text_cover(
            no_text_path,
            output_dir / f"final_cover_{style}.png",
            title,
            subtitle,
            config,
            cover_style=style,
        )


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run(args):
    load_dotenv()
    config = load_config()
    images = list_images(args.input_dir)
    output_dir = Path(args.output_dir) if args.output_dir else ROOT / "output" / Path(args.input_dir).name
    output_dir.mkdir(parents=True, exist_ok=True)

    client, provider = create_client(config)
    selection = select_cover_image(client, provider, images, config)
    if args.debug_json:
        write_json(output_dir / "selection.json", selection)

    if selection.get("image_index") is None:
        if args.debug_json:
            write_json(
                output_dir / "skipped.json",
                {
                    "status": "skipped",
                    "reason": selection.get("reason", "No eligible room photo found."),
                    "selection": selection,
                },
            )
        print(f"Skipped: {selection.get('reason')}")
        return

    source_image = images[selection["image_index"] - 1]
    selected_copy = output_dir / f"original{source_image.suffix.lower()}"
    shutil.copy2(source_image, selected_copy)

    no_text_path = output_dir / "renovated_no_text.png"
    final_cover_path = output_dir / "final_cover.png"

    retry_instruction = ""
    qa = None
    for attempt in range(1, config.get("max_renovation_attempts", 1) + 1):
        renovate_image(client, provider, source_image, selection, config, no_text_path, retry_instruction, args.decor_style)
        qa = review_renovation(client, provider, source_image, no_text_path, config)
        if args.debug_json:
            write_json(output_dir / f"qa_attempt_{attempt}.json", qa)
        if qa.get("pass") is True:
            break
        retry_instruction = qa.get("retry_instruction") or "; ".join(qa.get("violations", []))
    if qa and qa.get("pass") is not True:
        print("Needs manual review: automated QA did not pass.", file=sys.stderr)
        if args.debug_json:
            write_json(
                output_dir / "needs_manual_review.json",
                {
                    "status": "needs_manual_review",
                    "reason": "Renovated image did not pass automated redline QA.",
                    "last_qa": qa,
                },
            )

    selected_cover_style = args.cover_style or config.get("default_cover_style", "editorial")
    if selected_cover_style == "random":
        import random
        selected_cover_style = random.choice(list(COVER_STYLES.keys()))
        print(f"No cover style specified. Randomly selected: {selected_cover_style}")
    create_text_cover(
        no_text_path,
        final_cover_path,
        args.title or config["default_title"],
        args.subtitle or config["default_subtitle"],
        config,
        cover_style=selected_cover_style,
    )
    if args.style_variants:
        create_style_variants(
            no_text_path,
            output_dir,
            args.title or config["default_title"],
            args.subtitle or config["default_subtitle"],
            config,
        )

    print(f"No-text image: {no_text_path}")
    print(f"Final cover: {final_cover_path}")

    if args.run_id:
        if qa and qa.get("pass") is not True:
            print(
                "Skipped copying into pre-published/: automated QA did not pass "
                "(see needs_manual_review.json before publishing this cover manually).",
                file=sys.stderr,
            )
        else:
            property_name = Path(args.input_dir).name
            publish_dir = OUTPUTS_DIR / args.run_id / "pre-published"
            publish_dir.mkdir(parents=True, exist_ok=True)
            published_cover = publish_dir / f"{property_name}_cover.png"
            published_clean = publish_dir / f"{property_name}_cover_clean.png"
            shutil.copy2(final_cover_path, published_cover)
            shutil.copy2(no_text_path, published_clean)
            print(f"Cover copied alongside Agent3 note: {published_cover}")


def parse_args():
    parser = argparse.ArgumentParser(description="Create Xiaohongshu real-estate covers from listing photos.")
    parser.add_argument("input_dir", help="Directory containing photos from one listing.")
    parser.add_argument("--output-dir", help="Output directory. Defaults to output/<input_dir_name>.")
    parser.add_argument("--title", help="Cover title text for the final text overlay.")
    parser.add_argument("--subtitle", help="Cover subtitle text for the final text overlay.")
    parser.add_argument(
        "--cover-style",
        choices=sorted(COVER_STYLES) + ["random"],
        default=None,
        help="Final cover text style. Defaults to tuned editorial coffee style. "
             "Use 'random' to pick one of the five styles at random.",
    )
    parser.add_argument("--style-variants", action="store_true", help="Also write all five tuned text style variants.")
    parser.add_argument(
        "--decor-style",
        default=None,
        help="Optional decor style tag for the AI renovation step (e.g. '大理石'). "
             "Applied as a material/finish theme on top of the room-type guidance; "
             "never overrides the red-line rules in prompts/renovate.md.",
    )
    parser.add_argument("--debug-json", action="store_true", help="Write internal selection and QA JSON files.")
    parser.add_argument(
        "--run-id",
        default=None,
        help="Pipeline run id (YYYYMMDD_HHMM) shared with Agent3. When set, the final cover "
             "(and its clean no-text version) is also copied into "
             "04_outputs/<run-id>/pre-published/<property_name>_cover[.{_clean}].png, "
             "next to the Agent3 note for that same property, so an operator finds the "
             "note and its cover in one folder instead of two.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
