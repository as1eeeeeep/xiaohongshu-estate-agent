"""检测每张封面原图的实际房间类型，找出违反红线的封面"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

import base64
import json
from pathlib import Path
from openai import OpenAI
from shared.config import API_KEY, BASE_URL, VISION_MODEL

OUTPUT_DIR = Path("D:/xiaohongshu_estate/04_outputs")
RUN_ID = "batch_20260616_1555"
SAVE_DIR = OUTPUT_DIR / RUN_ID / "pre-published"

# ── 每张封面原图 ──
covers = [
    ("西營盤", "v1", "cover_原图_v1.jpg"),
    ("西營盤", "v2", "cover_原图_v2.jpg"),
    ("湾仔-1", "v1", "cover_原图_v1.jpg"),
    ("湾仔-1", "v2", "cover_原图_v2.jpg"),
    ("湾仔-2", "v1", "cover_原图_v1.jpg"),
    ("湾仔-2", "v2", "cover_原图_v2.jpg"),
    ("灣仔開放式", "v1", "cover_原图_v1.jpg"),
    ("灣仔開放式", "v2", "cover_原图_v2.jpg"),
    ("铜锣湾超大", "v1", "cover_原图_v1.jpg"),
    ("铜锣湾超大", "v2", "cover_原图_v2.jpg"),
    ("北角", "v1", "cover_原图_v1.jpg"),
    ("北角", "v2", "cover_原图_v2.jpg"),
    ("炮台山", "v1", "cover_原图_v1.jpg"),
    ("炮台山", "v2", "cover_原图_v2.jpg"),
]

# ── 查找对应的原图文件 ──
def find_source(kw, ver, ending):
    """在 pre-published 和原房源目录里找原图"""
    candidates = list(SAVE_DIR.glob(f"*{kw}*{ending}")) + \
                 list(SAVE_DIR.glob(f"*{kw}*_cover_原图*.jpg"))
    # 最精确匹配
    for c in candidates:
        if ver in c.stem:
            return c
    if candidates:
        return candidates[0]
    # 在房源目录里找
    prop_base = Path("D:/xiaohongshu_estate/01_materials/properties/6.16主做")
    for pd in prop_base.iterdir():
        if pd.is_dir():
            for f in pd.iterdir():
                if f.suffix.lower() in ('.jpg','.jpeg','.png') and "cover" not in f.name:
                    # 按顺序返回
                    pass
    return None

# 直接根据之前日志的对应关系
source_map = {
    ("西營盤","v1"): "【3】西營盤🇭🇰$440萬大一房一廳帶衣帽間_鳳凰層（帶電梯_一梯兩戶）_cover_原图_v1.jpg",
    ("西營盤","v2"): "【3】西營盤🇭🇰$440萬大一房一廳帶衣帽間_鳳凰層（帶電梯_一梯兩戶）_cover_原图_v2.jpg",
    ("湾仔-1","v1"): "【湾仔-1】灣仔🇭🇰筍盤_$440萬_（現一房_🉑間兩房）_平地電梯_交通方便_🈶少少海景_cover_原图_v1.jpg",
    ("湾仔-1","v2"): "【湾仔-1】灣仔🇭🇰筍盤_$440萬_（現一房_🉑間兩房）_平地電梯_交通方便_🈶少少海景_cover_原图_v2.jpg",
    ("湾仔-2","v1"): "【湾仔-2】銅鑼灣🇭🇰半新樓_大兩房_$850萬_交通方便🍀🏠_cover_原图_v1.jpg",
    ("湾仔-2","v2"): "【湾仔-2】銅鑼灣🇭🇰半新樓_大兩房_$850萬_交通方便🍀🏠_cover_原图_v2.jpg",
    ("灣仔開放式","v1"): "灣仔🇭🇰開放式_$268万_有電梯（要走一層樓梯）_cover_原图_v1.jpg",
    ("灣仔開放式","v2"): "灣仔🇭🇰開放式_$268万_有電梯（要走一層樓梯）_cover_原图_v2.jpg",
    ("铜锣湾超大","v1"): "铜锣湾超大1房🇭🇰（可间两房）_$445万_有電梯_cover_原图_v1.jpg",
    ("铜锣湾超大","v2"): "铜锣湾超大1房🇭🇰（可间两房）_$445万_有電梯_cover_原图_v2.jpg",
    ("北角","v1"): "【29】北角🇭🇰395万开阳海景一房一厅带平台_cover_原图_v1.jpg",
    ("北角","v2"): "【29】北角🇭🇰395万开阳海景一房一厅带平台_cover_原图_v2.jpg",
    ("炮台山","v1"): "【34】炮台山三房两卫，797呎670万_大三房！！_cover_原图_v1.jpg",
    ("炮台山","v2"): "【34】炮台山三房两卫，797呎670万_大三房！！_cover_原图_v2.jpg",
}

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

RESULTS = []

for kw, ver, fname in covers:
    fpath = SAVE_DIR / source_map.get((kw, ver), fname)
    if not fpath.exists():
        print(f"✗ {kw} {ver}: 文件不存在 {fpath}")
        continue

    print(f"▸ {kw} {ver} … ", end="", flush=True)

    # 编码图片
    with open(fpath, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    mime = "image/jpeg"
    data_url = f"data:{mime};base64,{b64}"

    try:
        resp = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "What room type is shown in this photo? Answer with EXACTLY ONE WORD: living_room, bedroom, kitchen, bathroom, study, dining_room, balcony, hallway, entrance, or other. Only output the word, nothing else."},
                    {"type": "image_url", "image_url": {"url": data_url, "detail": "low"}},
                ],
            }],
            temperature=0.1,
            max_tokens=20,
        )
        actual_type = resp.choices[0].message.content.strip().lower().strip(".,;:'\"!?")

        # 判断是否违反红线：如果原图是厨房/卧室/书房/浴室但被标成 living_room
        wrong_room_types = {"kitchen", "bathroom", "study", "bedroom", "balcony", "hallway", "entrance", "dining_room"}
        is_violation = actual_type in wrong_room_types

        RESULTS.append({"keyword": kw, "version": ver, "filename": fpath.name,
                        "actual_room_type": actual_type, "is_violation": is_violation})

        if is_violation:
            print(f"⚠ 红线违反！实际是 {actual_type}")
        else:
            print(f"✓ {actual_type}")

    except Exception as e:
        print(f"✗ 失败: {e}")
        RESULTS.append({"keyword": kw, "version": ver, "filename": fpath.name,
                        "actual_room_type": "error", "is_violation": False})

print("\n\n========== 红线违反总汇 ==========")
violations = [r for r in RESULTS if r["is_violation"]]
clean = [r for r in RESULTS if not r["is_violation"]]
print(f"违反红线: {len(violations)} 张")
for v in violations:
    print(f"  ⚠ {v['keyword']} {v['version']}: 实际是 {v['actual_room_type']}")
print(f"正常: {len(clean)} 张")

# 保存结果
result_path = SAVE_DIR / "_room_type_check.json"
with open(result_path, "w", encoding="utf-8") as f:
    json.dump(RESULTS, f, ensure_ascii=False, indent=2)
print(f"\n结果已保存: {result_path}")
