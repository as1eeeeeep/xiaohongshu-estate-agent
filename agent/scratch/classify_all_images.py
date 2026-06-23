import os, sys, base64, json, time
from pathlib import Path
from openai import OpenAI

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import API_KEY, BASE_URL, VISION_MODEL

PROP_DIR = Path("D:/xiaohongshu_estate/01_materials/properties/6.16主做")
OUTPUT_JSON = Path("D:/xiaohongshu_estate/agent/scratch/all_images_classified.json")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# Load existing results if any to avoid re-classifying what already succeeded
results = {}
if OUTPUT_JSON.exists():
    try:
        with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
            results = json.load(f)
    except Exception:
        results = {}

print(f"Using vision model: {VISION_MODEL}")

for prop_subdir in sorted(PROP_DIR.iterdir()):
    if not prop_subdir.is_dir():
        continue
    prop_name = prop_subdir.name
    
    # Initialize if not present
    if prop_name not in results:
        results[prop_name] = []
        
    print(f"\nProcessing property: {prop_name}")
    
    # List images
    img_files = []
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    for f in sorted(prop_subdir.iterdir()):
        if f.suffix.lower() in exts and "cover_原图" not in f.name:
            img_files.append(f)
            
    for img_path in img_files:
        # Check if already classified successfully
        existing = [item for item in results[prop_name] if item["filename"] == img_path.name and item["room_type"] != "error"]
        if existing:
            print(f"  {img_path.name} already classified: {existing[0]['room_type']} (is_indoor={existing[0]['is_indoor']})")
            continue
            
        print(f"  Analyzing image: {img_path.name} ... ", end="", flush=True)
        
        # Read and encode image
        try:
            with open(img_path, "rb") as img_f:
                b64_data = base64.b64encode(img_f.read()).decode("utf-8")
        except Exception as file_err:
            print(f"File read error: {file_err}")
            continue
        
        mime_type = "image/jpeg"
        if img_path.suffix.lower() == ".png":
            mime_type = "image/png"
        elif img_path.suffix.lower() == ".webp":
            mime_type = "image/webp"
            
        data_url = f"data:{mime_type};base64,{b64_data}"
        
        prompt = (
            "Determine the type of room/scene shown in this real estate photo. "
            "First, classify if it is an indoor room scene of the apartment itself. "
            "Select exactly one class from: [living_room, bedroom, kitchen, bathroom, dining_room, balcony, other_indoor, non_indoor]. "
            "Note: non_indoor includes hallways, elevators, building lobby, building exterior, street views, maps, floor plans, or text. "
            "Output your answer in JSON format with two keys:\n"
            "\"is_indoor\": true or false,\n"
            "\"room_type\": one of the classes above.\n"
            "Output ONLY the JSON object, nothing else. Do not include markdown code block formatting."
        )
        
        success = False
        last_err = ""
        for attempt in range(4):
            try:
                # Add delay between calls to avoid hitting rate limits
                time.sleep(1.5)
                
                resp = client.chat.completions.create(
                    model=VISION_MODEL,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_url, "detail": "low"}},
                        ]
                    }],
                    temperature=0.1,
                    max_tokens=100,
                    timeout=30
                )
                raw_text = resp.choices[0].message.content.strip()
                if raw_text.startswith("```"):
                    import re
                    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                    raw_text = re.sub(r"\s*```$", "", raw_text)
                    raw_text = raw_text.strip()
                    
                info = json.loads(raw_text)
                info["filename"] = img_path.name
                info["abs_path"] = str(img_path.resolve())
                
                # Update list (remove any prior error for this file)
                results[prop_name] = [item for item in results[prop_name] if item["filename"] != img_path.name]
                results[prop_name].append(info)
                
                print(f"Classified: {info['room_type']} (is_indoor={info['is_indoor']})")
                success = True
                break
            except Exception as e:
                last_err = str(e)
                time.sleep(2.0 * (attempt + 1)) # exponential backoff
                
        if not success:
            print(f"FAILED after 4 attempts. Error: {last_err}")
            results[prop_name] = [item for item in results[prop_name] if item["filename"] != img_path.name]
            results[prop_name].append({
                "filename": img_path.name,
                "abs_path": str(img_path.resolve()),
                "is_indoor": False,
                "room_type": "error",
                "error": last_err
            })
            
        # Intermediary save
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\nAll classification results completed and saved to: {OUTPUT_JSON}")
