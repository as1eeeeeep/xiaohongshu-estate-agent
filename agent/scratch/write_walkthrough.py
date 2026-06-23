import sys
import os

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TARGET = r"C:\Users\azzi\.gemini\antigravity-ide\brain\c24f3992-7e21-42d5-b824-0cad3cf40eb0\walkthrough.md"

content = """# 房源笔记与轻奢大理石风 staging 封面图生成完成报告

根据您的最新要求，已针对 **炮台山、湾仔268万、湾仔440万、铜锣湾大两房** 这 4 套房源进行了“大理石轻奢风”风格的主题生成。

本次生成重点：
1. **轻奢豪华风封面**：封面图以高雅的**白色大理石地板/墙面**（marble textures）、精致五金件、高档绒面/布艺家具及舒适多层光源为主，营造出极其干净、高级、吸引女性的高颜值豪华感。封面一律为**无字底图**。
2. **高点击欲望标题**：重新打磨标题，采用“闺蜜看哭了”、“独立女性的底气”、“拒老破小”等具备强烈点击诱惑和情感共鸣的爆款文案。
3. **免责声明完整性**：继续严格在 `.md` 和 `.txt` 正文开头保留免责声明。

本次轻奢版输出主路径：[batch_20260622_1549](file:///D:/xiaohongshu_estate/04_outputs/batch_20260622_1549/pre-published)

---

## 📁 打包分类目录结构与生成内容清单

每套房源的独立文件夹均包含以下内容：
1. **Markdown 笔记** (`.md`) - 包含结构化内容和关联素材链接。
2. **纯文本笔记** (`.txt`) - 直接用于复制到小红书发布。已在开头保留了专属免责声明。
3. **轻奢 staging 封面图** (`_cover.png` 和 `_cover_clean.png`) - 均为**无字、轻奢大理石风 staging 渲染**的高清大图。
4. **房源现状原图** (`_cover_原图.jpg` 或 `.png`) - 供核对现状和作为小红书笔记“第二页”使用。
5. **小红书行文思路策略文件** (`_strategy.md`) - 包含对爆款逻辑的规划。

---

## 🔍 各房源生成结果清单与快速链接

### 1. 灣仔 268万 开放式（精致轻奢风）
- **高点击标题**：`港漂女生的底气 268万买湾仔精致家`
- **房源文件夹**: [灣仔🇭🇰開放式_$268万_有電梯（要走一層樓梯）](file:///D:/xiaohongshu_estate/04_outputs/batch_20260622_1549/pre-published/灣仔🇭🇰開放式_$268万_有電梯（要走一層樓梯）)
- **纯文本笔记**: [灣仔...txt](file:///D:/xiaohongshu_estate/04_outputs/batch_20260622_1549/pre-published/灣仔🇭🇰開放式_$268万_有電梯（要走一層樓梯）/灣仔🇭🇰開放式_$268万_有電梯（要走一層樓梯）.txt)
- **Staging 封面图**: [cover.png](file:///D:/xiaohongshu_estate/04_outputs/batch_20260622_1549/pre-published/灣仔🇭🇰開放式_$268万_有電梯（要走一層樓梯）/灣仔🇭🇰開放式_$268万_有電梯（要走一層樓梯）_cover.png)

### 2. 湾仔-1 440万 332呎大一房（大理石轻奢风）
- **高点击标题**：`中环上班女生，400多万留港岛看这套`
- **房源文件夹**: [【湾仔-1】灣仔🇭🇰筍盤_$440萬_（現一房_🉑間兩房）_平地電梯_交通方便_🈶少少海景](file:///D:/xiaohongshu_estate/04_outputs/batch_20260622_1549/pre-published/【湾仔-1】灣仔🇭🇰筍盤_$440萬_（現一房_🉑間兩房）_平地電梯_交通方便_🈶少少海景)
- **纯文本笔记**: [【湾仔-1】...txt](file:///D:/xiaohongshu_estate/04_outputs/batch_20260622_1549/pre-published/【湾仔-1】灣仔🇭🇰筍盤_$440萬_（現一房_🉑間兩房）_平地電梯_交通方便_🈶少少海景/【湾仔-1】灣仔🇭🇰筍盤_$440萬_（現一房_🉑間兩房）_平地電梯_交通方便_🈶少少海景.txt)
- **Staging 封面图**: [cover.png](file:///D:/xiaohongshu_estate/04_outputs/batch_20260622_1549/pre-published/【湾仔-1】灣仔🇭🇰筍盤_$440萬_（現一房_🉑間兩房')_平地電梯_交通方便_🈶少少海景/【湾仔-1】灣仔🇭🇰筍盤_$440萬_（現一房_🉑間兩房）_平地電梯_交通方便_🈶少少海景_cover.png)

### 3. 炮台山 670万 797呎大三房两卫（大理石豪华轻奢）
- **高点击标题**：`670万住炮台山大理石3房，闺蜜看哭了`
- **房源文件夹**: [【34】炮台山三房两卫，797呎670万_大三房！！](file:///D:/xiaohongshu_estate/04_outputs/batch_20260622_1549/pre-published/【34】炮台山三房两卫，797呎670万_大三房！！)
- **纯文本笔记**: [【34】炮台山...txt](file:///D:/xiaohongshu_estate/04_outputs/batch_20260622_1549/pre-published/【34】炮台山三房两卫，797呎670万_大三房！！/【34】炮台山三房两卫，797呎670万_大三房！！.txt)
- **Staging 封面图**: [cover.png](file:///D:/xiaohongshu_estate/04_outputs/batch_20260622_1549/pre-published/【34】炮台山三房两卫，797呎670万_大三房！！/【34】炮台山三房两卫，797呎670万_大三房！！_cover.png)

### 4. 湾仔-2 铜锣湾 850万 两房半新楼（精致大理石轻奢）
- **高点击标题**：`拒老破小！铜锣湾850万住轻奢大两房`
- **房源文件夹**: [【湾仔-2】銅鑼灣🇭🇰半新樓_大兩房_$850萬_交通方便🍀🏠](file:///D:/xiaohongshu_estate/04_outputs/batch_20260622_1549/pre-published/【湾仔-2】銅鑼灣🇭🇰半新樓_大兩房_$850萬_交通方便🍀🏠)
- **纯文本笔记**: [【湾仔-2】...txt](file:///D:/xiaohongshu_estate/04_outputs/batch_20260622_1549/pre-published/【湾仔-2】銅鑼灣🇭🇰半新樓_大兩房_$850萬_交通方便🍀🏠/【湾仔-2】銅鑼灣🇭🇰半新樓_大兩房_$850萬_交通方便🍀🏠.txt)
- **Staging 封面图**: [cover.png](file:///D:/xiaohongshu_estate/04_outputs/batch_20260622_1549/pre-published/【湾仔-2】銅鑼灣🇭🇰半新樓_大兩房_$850萬_交通方便🍀🏠/【湾仔-2】銅鑼灣🇭🇰半新樓_大兩房_$850萬_交通方便🍀🏠_cover.png)

---

## 🛠️ 规范校对与合规检查

1. **免责声明完整性**：
   所有新生成的 4 篇笔记首行均包含了要求的免责声明，且在 `.txt` 中完全保留。
2. **轻奢 staging 封面图去字**：
   所有重新生成的轻奢大理石风 staging 封面图均没有文字，完全为干净的质感底图。
3. **受众匹配度**：
   正文用语自然顺畅，大理石风格的豪华质感被恰当地融合进了正文中对精致生活感的描述。
"""

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated walkthrough.md successfully!")
