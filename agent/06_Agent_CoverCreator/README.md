# 06 Agent Cover Creator

这个文件夹是一套“香港房源小红书封面”自动化工作流。

流程：

1. 从同一套房源的多张实拍照片里选封面底图。
2. 按房间类型生成一版“纯装修、无文字”的真实摄影风格图片。
3. 对比原图做红线质检，不通过则自动重试一次。
4. 用本地排版在装修图上加标题，生成最终封面。

## 安装

```bash
cd "/Users/asleep/松鼠找房/agent"
source .venv/bin/activate
pip install -r requirements.txt
```

默认使用 Gemini。把 key 放在 `agent/.env`：

```bash
GEMINI_API_KEY="你的 Gemini API Key"
```

如果要改回 OpenAI，把 `config.json` 里的 `provider` 改成 `openai`，并设置 `OPENAI_API_KEY`。

## 使用

把同一套房源照片放到一个目录，例如：

```bash
mkdir -p input/listing-001
```

运行：

```bash
06_Agent_CoverCreator/run.sh 06_Agent_CoverCreator/input/listing-001 \
  --title "西营盘高质一房" \
  --subtitle "真实房源｜自然采光｜温柔奶油风"
```

默认最终封面使用已调好的 `editorial` 咖啡色杂志感排版。也可以指定 5 种调教过的自动配色风格：

```bash
--cover-style editorial  # 咖啡色杂志感，默认，标题和副标题已加大上下间距
--cover-style card       # 陶土棕柔卡片
--cover-style vertical   # 香槟金竖排
--cover-style band       # 石墨黑 + 暖金底部条
--cover-style xhs        # 橄榄绿小红书感，标题和副标题已加大上下间距
```

需要一次输出 5 个候选版本时：

```bash
06_Agent_CoverCreator/run.sh 06_Agent_CoverCreator/input/listing-001 \
  --title "西营盘高质一房" \
  --subtitle "真实房源｜自然采光｜温柔奶油风" \
  --style-variants
```

## Codex / Claude Code 一致性

Codex 和 Claude Code 都应该调用同一个入口：

```bash
cd "/Users/asleep/松鼠找房/agent"
06_Agent_CoverCreator/run.sh 06_Agent_CoverCreator/input/listing-001 \
  --title "香港质感小家" \
  --subtitle "精装客厅｜明亮窗景" \
  --cover-style editorial
```

只要输入图、标题、副标题、`config.json`、`prompts/`、`.env` 和 `.venv` 一样，两个工具调用出来的流程和版式会一致。Gemini 生图本身不是像素级确定性的，所以装修图可能会有轻微差别；本地加字风格是确定性的，同一张 `renovated_no_text.png` 会得到同样的 `final_cover.png`。

输出会写入：

```text
06_Agent_CoverCreator/output/listing-001/
  original.*
  renovated_no_text.png
  final_cover.png
  final_cover_editorial.png  # 仅在 --style-variants 时输出
  final_cover_card.png
  final_cover_vertical.png
  final_cover_band.png
  final_cover_xhs.png
```

每张真实室内素材都会被判断为客厅、卧室、餐厅、厨房之一；非典型小户型起居/工作区默认归到客厅。只有外观、户型图、截图、地图、海报、纯浴室、纯阳台等不适合封面的素材会生成 `skipped.json`。

默认不输出 JSON 调试文件。需要查看选图和质检 JSON 时加 `--debug-json`。

## 关键约束

- 纯装修图严禁文字、数字、水印。
- 不放大房间，不改变户型、墙、窗、门、地板、固定装置。
- 不遮挡窗户与采光。
- 可以加/换与香港小户型尺度相称的家具，做更明显的精装修效果，但不能让房间显大或遮挡门窗。
- 输出图片会后处理回原图尺寸和比例。
- 加字只在最后一步本地叠加，避免模型生成乱码文字。
- 加字颜色会根据文字区域的背景亮度自动调整，避免所有封面都变成白字模板。
