"""
在小红书封面外景图上叠加核心卖点文字
- 不改变原图内容，仅加字
- 使用大号醒目字体 + 半透明底条增强可读性
"""
from PIL import Image, ImageDraw, ImageFont
import os

# --- 字体配置 ---
# Windows 自带的微软雅黑粗体
FONT_PATHS = [
    "C:/Windows/Fonts/msyhbd.ttc",   # 微软雅黑粗体
    "C:/Windows/Fonts/msyh.ttc",     # 微软雅黑
    "C:/Windows/Fonts/simhei.ttf",   # 黑体
]

def get_font(size):
    for fp in FONT_PATHS:
        if os.path.exists(fp):
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()


def add_text_overlay(img_path, output_path, lines, font_size=None):
    """
    在图片上叠加多行文字。
    lines: list of dict, 每行包含:
      - text: 文字内容
      - color: 文字颜色 (R,G,B)
      - bg_color: 底条颜色 (R,G,B,A)
      - position: 'top' / 'center' / 'bottom' 或具体 y 比例 (0.0~1.0)
    """
    img = Image.open(img_path).convert("RGBA")
    w, h = img.size

    # 自动字体大小：按图片宽度的 1/12
    if font_size is None:
        font_size = max(36, w // 12)

    font_large = get_font(font_size)
    font_small = get_font(int(font_size * 0.65))

    # 创建文字叠加层
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for line_cfg in lines:
        text = line_cfg["text"]
        color = line_cfg.get("color", (255, 255, 255))
        bg_color = line_cfg.get("bg_color", (0, 0, 0, 140))
        pos = line_cfg.get("position", 0.5)
        is_small = line_cfg.get("small", False)
        font = font_small if is_small else font_large

        # 计算文字尺寸
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        # 计算 Y 位置
        if pos == "top":
            y = int(h * 0.05)
        elif pos == "bottom":
            y = int(h * 0.88)
        elif pos == "center":
            y = int((h - th) / 2)
        else:
            y = int(h * pos)

        x = int((w - tw) / 2)

        # 画半透明底条（宽度撑满图片）
        pad_y = int(th * 0.3)
        pad_x = int(tw * 0.08)
        draw.rectangle(
            [0, y - pad_y, w, y + th + pad_y],
            fill=bg_color
        )

        # 画文字
        draw.text((x, y), text, font=font, fill=color)

    # 合成
    result = Image.alpha_composite(img, overlay)
    result = result.convert("RGB")
    result.save(output_path, quality=95)
    print(f"[OK] saved: {output_path}")


# ===== 1. 跑马地 One Jardines Lookout 1房 =====
add_text_overlay(
    img_path=r"d:\xiaohongshu_estate\04_outputs\happyvalley_620w_1room\cover.png",
    output_path=r"d:\xiaohongshu_estate\04_outputs\happyvalley_620w_1room\cover.png",
    lines=[
        {
            "text": "跑马地 · 极品新楼",
            "color": (255, 255, 255),
            "bg_color": (180, 40, 40, 200),
            "position": 0.06
        },
        {
            "text": "🎓12校网 | 🆕楼龄仅2年 | 💰现带租约",
            "color": (255, 255, 80),
            "bg_color": (0, 0, 0, 180),
            "position": 0.82,
            "small": True
        },
        {
            "text": "收租过万 · 躺赢之选",
            "color": (255, 255, 255),
            "bg_color": (0, 0, 0, 160),
            "position": 0.90,
            "small": True
        },
    ]
)

# ===== 2. 湾仔 鸿福大厦 3房 =====
# 这个文件夹没有 cover.png，用文件夹里的第一张实拍图作底图
wanchai_3room_dir = r"d:\xiaohongshu_estate\04_outputs\wanchai_465w_3room"
# 找一张 jpg 做底图
jpg_files = sorted([f for f in os.listdir(wanchai_3room_dir) if f.endswith('.jpg')])
if jpg_files:
    base_img = os.path.join(wanchai_3room_dir, jpg_files[0])
else:
    # 从素材目录拿
    mat_dir = r"d:\xiaohongshu_estate\01_materials\properties\灣仔🇭🇰三房_$465萬_平地電梯（十二校網）👩‍🎓"
    mat_jpgs = sorted([f for f in os.listdir(mat_dir) if f.endswith('.jpg')])
    base_img = os.path.join(mat_dir, mat_jpgs[0])

add_text_overlay(
    img_path=base_img,
    output_path=os.path.join(wanchai_3room_dir, "cover.png"),
    lines=[
        {
            "text": "湾仔捡漏 · 12校网3房",
            "color": (255, 255, 255),
            "bg_color": (20, 100, 180, 200),
            "position": 0.06
        },
        {
            "text": "📍铜锣湾地铁3分钟 | 🛗平地电梯 | 💰租抵供",
            "color": (255, 255, 80),
            "bg_color": (0, 0, 0, 180),
            "position": 0.82,
            "small": True
        },
        {
            "text": "绝版笋价 · 手慢无",
            "color": (255, 255, 255),
            "bg_color": (0, 0, 0, 160),
            "position": 0.90,
            "small": True
        },
    ]
)

# ===== 3. 湾仔 谭臣大厦 1房 =====
add_text_overlay(
    img_path=r"d:\xiaohongshu_estate\04_outputs\wanchai_tang_250w_1room\cover.png",
    output_path=r"d:\xiaohongshu_estate\04_outputs\wanchai_tang_250w_1room\cover.png",
    lines=[
        {
            "text": "湾仔捡漏 · 首付小几十万",
            "color": (255, 255, 255),
            "bg_color": (200, 60, 20, 200),
            "position": 0.06
        },
        {
            "text": "📍湾仔地铁4分钟 | 🏠正规1房 | 💰租抵供",
            "color": (255, 255, 80),
            "bg_color": (0, 0, 0, 180),
            "position": 0.82,
            "small": True
        },
        {
            "text": "港岛核心区 · 低门槛上车",
            "color": (255, 255, 255),
            "bg_color": (0, 0, 0, 160),
            "position": 0.90,
            "small": True
        },
    ]
)

print("\n[DONE] All 3 cover images text overlay completed!")
