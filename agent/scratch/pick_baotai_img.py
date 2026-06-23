"""识别炮台山室内图，选一个合适的（非1号/10号）"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

import base64
from pathlib import Path
from openai import OpenAI
from shared.config import API_KEY, BASE_URL, VISION_MODEL

prop_dir = Path("D:/xiaohongshu_estate/01_materials/properties/6.16主做/【34】炮台山三房两卫，797呎670万_大三房！！")

# 排除 1.jpg (v1用) 和 10.jpg (v2用走廊图)
candidates = []
for f in sorted(prop_dir.iterdir()):
    if f.suffix.lower() in ('.jpg','.jpeg','.png') and 'cover' not in f.name:
        num = ''.join(c for c in f.stem.split('！')[-1] if c.isdigit())
        if num and int(num) not in (1, 10, 21):
            candidates.append(f)

print(f"候选图片: {len(candidates)} 张")
for c in candidates:
    print(f"  {c.name}")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

best = None
for img_path in candidates:
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    data_url = f"data:image/jpeg;base64,{b64}"

    try:
        resp = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "What type of room is shown? Answer ONE WORD: living_room, bedroom, kitchen, bathroom, study, dining_room, balcony, hallway, entrance, or other. Is it a good candidate for a real estate cover photo? Reply: ROOM_TYPE|YES/NO"},
                    {"type": "image_url", "image_url": {"url": data_url, "detail": "low"}},
                ],
            }],
            temperature=0.1,
            max_tokens=30,
        )
        result = resp.choices[0].message.content.strip()
        parts = result.split("|")
        room = parts[0].strip().lower().strip(".,;:'\"!?")
        good = len(parts) > 1 and "yes" in parts[1].lower()
        print(f"  {img_path.name}: {room} {'✅' if good else '❌'}")
        if good and room in ("living_room", "bedroom", "study", "dining_room", "other"):
            if best is None:
                best = img_path
    except Exception as e:
        print(f"  {img_path.name}: error {e}")

if not best and candidates:
    best = candidates[0]

print(f"\n推荐: {best.name if best else '无'}")
