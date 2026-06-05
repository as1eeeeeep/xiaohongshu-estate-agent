"""
在小红书封面外景图上叠加核心卖点文字 v2
- 仅处理跑马地和湾仔3房（谭臣大厦已完成）
- 先备份原图为 cover_raw.png，再在 cover.png 上加字
"""
from PIL import Image, ImageDraw, ImageFont
import os
import shutil

# --- 字体配置 ---
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
    """
    # 备份原图
    backup = img_path.replace(".png", "_raw.png")
    if not os.path.exists(backup):
        shutil.copy2(img_path, backup)
        print(f"[BACKUP] {backup}")

    img = Image.open(img_path).convert("RGBA")
    w, h = img.size

    if font_size is None:
        font_size = max(36, w // 12)

    font_large = get_font(font_size)
    font_small = get_font(int(font_size * 0.65))

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for line_cfg in lines:
        text = line_cfg["text"]
        color = line_cfg.get("color", (255, 255, 255))
        bg_color = line_cfg.get("bg_color", (0, 0, 0, 140))
        pos = line_cfg.get("position", 0.5)
        is_small = line_cfg.get("small", False)
        font = font_small if is_small else font_large

        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        if pos == "top":
            y = int(h * 0.05)
        elif pos == "bottom":
            y = int(h * 0.88)
        elif pos == "center":
            y = int((h - th) / 2)
        else:
            y = int(h * pos)

        x = int((w - tw) / 2)

        pad_y = int(th * 0.3)
        draw.rectangle(
            [0, y - pad_y, w, y + th + pad_y],
            fill=bg_color
        )
        draw.text((x, y), text, font=font, fill=color)

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
            "text": "跑马地 | 极品新楼",
            "color": (255, 255, 255),
            "bg_color": (180, 40, 40, 200),
            "position": 0.04
        },
        {
            "text": "12校网 | 楼龄仅2年 | 现带租约",
            "color": (255, 255, 80),
            "bg_color": (0, 0, 0, 180),
            "position": 0.84,
            "small": True
        },
        {
            "text": "收租过万 | 躺赢之选",
            "color": (255, 255, 255),
            "bg_color": (0, 0, 0, 160),
            "position": 0.91,
            "small": True
        },
    ]
)

# ===== 2. 湾仔 鸿福大厦 3房 =====
add_text_overlay(
    img_path=r"d:\xiaohongshu_estate\04_outputs\wanchai_465w_3room\cover.png",
    output_path=r"d:\xiaohongshu_estate\04_outputs\wanchai_465w_3room\cover.png",
    lines=[
        {
            "text": "湾仔捡漏 | 12校网3房",
            "color": (255, 255, 255),
            "bg_color": (20, 100, 180, 200),
            "position": 0.04
        },
        {
            "text": "铜锣湾地铁3分钟 | 平地电梯 | 租抵供",
            "color": (255, 255, 80),
            "bg_color": (0, 0, 0, 180),
            "position": 0.84,
            "small": True
        },
        {
            "text": "绝版笋价 | 手慢无",
            "color": (255, 255, 255),
            "bg_color": (0, 0, 0, 160),
            "position": 0.91,
            "small": True
        },
    ]
)

print("\n[DONE] Happy Valley + Wanchai 3-room covers updated!")
