import os, sys, base64, json
from pathlib import Path
from openai import OpenAI

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import API_KEY, BASE_URL, VISION_MODEL, PROPERTIES_DIR

prop_dir = PROPERTIES_DIR / "6.22主做" / "【北角-10】北角🇭🇰海港阁_395万开阳海景一房一厅带平台"
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

for i in [1, 2, 3]:
    img_path = prop_dir / f"【北角-10】北角🇭🇰海港阁_395万开阳海景一房一厅带平台_{i}.jpg"
    if not img_path.exists():
        continue
        
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
        
    resp = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe what is visible in this photo. Is it a living room, bedroom, or something else? Mention furniture like bed, sofa, TV, table, etc."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"}},
            ],
        }],
        max_tokens=150,
    )
    print(f"Image {i}: {resp.choices[0].message.content.strip()}")
