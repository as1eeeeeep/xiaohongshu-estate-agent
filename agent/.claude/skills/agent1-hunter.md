# Agent 1 — 爆款笔记猎人 (Hunter)

## 角色定位
自动化筛选高潜力的香港买房/租房小红书图文笔记。支持两种发现模式：① 关键词搜索（搜索香港房产关键词 → 发现笔记）② 按博主抓取（指定小红书号 → 抓取其全部笔记）。提取 id + xsec_token → 拼装分享链接 → 获取评论区 → LLM 意图分类 → 输出合格链接 + 爬取结果。

---

## 核心配置

### 搜索参数
- **关键词**: `"香港放售"`, `"香港楼盘介绍"`, `"香港二手笋盘"`, `"香港上车楼盘"`, `"港岛放盘"`, `"九龙新盘"`, `"香港业主急放"`, `"铜锣湾放盘"`, `"湾仔楼盘"`, `"西营盘楼盘"`, `"香港细价楼"`
- **关键词设计原则**: 广撒网策略——同时覆盖中介术语（放售/放盘/楼盘）和素人搜索词（上车/细价楼），不依赖关键词做视角过滤。真正的视角分类由 Agent1 内建的 `classify_perspectives()` 在下游完成。
- **每关键词页数**: 3 页
- **笔记类型**: `image`（只要图文，不要视频）
- **排序**: `latest`（按最新排序，确保时效性）
- **目标数量**: 25 条去重笔记

### 时效性过滤（v2.0 新增）
- **配置**: `PUBLISHED_WITHIN_DAYS = 14`（只要最近 14 天内发布的笔记）
- **实现**: 从 `note_card.corner_tag_info[type=publish_time]` 提取发布日期，支持三种格式：
  - 相对时间："X小时前"/"昨天"/"X天前" → 自动转绝对日期
  - MM-DD 格式："05-27" → 当年
  - YYYY-MM-DD 格式："2026-05-27"
- **特殊处理**: `corner_tag_info` 可能是 Python repr 字符串（`ast.literal_eval` 解析）或原生 list

### 按博主抓取（可选）
- **参数**: `--red-id <小红书号>` 或 `run(red_id="小红书号")`
- **用途**: 指定一个博主的小红书号，直接从其主页抓取所有笔记，跳过关键词搜索
- **工作流**: `xhs search-user` → 获取 user_id → 用 red_id 作为搜索词 → `xhs search` → 按 user_id 过滤 → 获取评论 → 意图分类
- **适用场景**: 已知某个高产房产博主，想批量采集其全部笔记进行拆解分析
- **注意**: `xhs user-posts` API 可能不稳定，当前采用搜索+过滤策略作为替代

### 视角过滤（可选）
- **参数**: `--perspective <标签>` 或 `run(perspective="标签")`
- **不指定时**: 不过滤视角，所有笔记正常处理
- **指定时**: 仅处理匹配该视角的笔记，不匹配的跳过（不获取评论、不下载）
- **示例视角**: `素人`、`中介`、`教学向`、`投资客`、`媒体资讯`、`租客`
- **匹配方式**: 子串包含（不区分大小写），写"素人"即可匹配"素人视角"

### 合格阈值
- 询盘数 ≥ 2 **OR** 询盘率 ≥ 20%
- 两条条件满足任一即触发

### 模型
- 使用 `LIGHT_MODEL`（当前为 `gemini-3.1-flash-lite`）
- 仅用于评论意图二分类（是/否有买房意图），非思考型任务

---

## 关键输出要求

### 1. 分享链接格式（最高优先级）
**必须**使用发现页完整分享链接：
```
https://www.xiaohongshu.com/discovery/item/{note_id}?source=webshare&xhsshare=pc_web&xsec_token={xsec_token}&xsec_source=pc_share
```
- `note_id` 和 `xsec_token` 从 `xhs search` 返回的 **item 层级**提取（不是 note_card 内部！）
- 降级路径：仅当确实拿不到 `xsec_token` 时才使用 `https://www.xiaohongshu.com/explore/{note_id}`

### 2. Timeline 归档 (`data_pipeline/stage1_raw/`)
每次运行生成带时间戳的 URL 列表：
- 文件名: `qualified_urls_{YYYY-MM-DD_HH-MM}.txt`
- 路径: `data_pipeline/stage1_raw/`

### 3. 合格线索持久化 (`04_outputs/qualified_leads.json`)
- 追加模式，同 note_url 不重复
- 记录: note_url, note_id, xsec_token, title, total_comments, inquiry_count, inquiry_ratio, scanned_at

### 4. 爬取结果 (`01_materials/viral_examples/`)
每次运行新建文件夹存放爬取的笔记内容：
- 路径: `01_materials/viral_examples/{HH时MM分}_{爬取结果}/`
- 当前时间用香港时区 (UTC+8)，精确到分钟

---

## 意图分类规则

### 判定标准
核心问题：这条评论是否暗示评论者本人可能正在香港找房、看房、买房或租房？

### ✅ 计入（有意图）— 6 类情形
1. **求推荐**: "有什么推荐""哪个盘好""XX区怎么样"
2. **求建议**: "该不该买""现在上车合适吗""买还是租""XX盘值得入手吗"
3. **问具体信息**: 询问价格、户型、面积、首付、月供、租金、学区、看房方式，暗示自己可能在考虑
4. **表达购买/租房打算**: "想买""打算买""准备上车""在找房""求中介联系""求私信""滴滴我"
5. **对比选筹**: "A和B怎么选""这个盘和那个盘对比"
6. **投资评估**: 询问租金回报、升值潜力、税费成本等投资细节

### ❌ 不计入
- 纯感叹/闲聊: "好贵啊""买不起""羡慕""好看""不错""加油""马克"
- 纯观点讨论: 对房价走势、政策的分析但未暗示自己有购买打算
- 对博主本人的评论: "你好厉害""博主好美"
- 跑题讨论: 与买房租房无关的话题
- 回顾性分享: "我当年买的时候才XX万"（非当前在找房）

---

## 视角分类规则

### 判定标准
核心问题：这篇笔记是谁写的、从什么角度写的？

### 视角类型
1. **素人视角**: 普通个人分享买房/看房/装修/租房经历，第一人称叙事，真实体验分享
2. **中介视角**: 房产经纪/代理发布的房源推广、带看记录，含推销语气或联系方式
3. **教学向**: 教别人怎么买房、攻略、避坑指南、知识科普，"教你""攻略""建议"风格
4. **投资客视角**: 从投资回报、租金收益、升值潜力、税费成本角度分析房产
5. **开发商/销售视角**: 楼盘官方宣传、开盘信息、一手房源推广
6. **媒体资讯**: 新闻报道、政策解读、市场数据汇总
7. **租客视角**: 租房经历、租房体验、租金讨论
8. **其他**: 无法归入以上任何一类

### 分类输入
- 笔记标题（主要判断依据）
- 作者昵称（辅助参考）
- 笔记摘要/描述（如有）

### 过滤时机
- 视角分类在**获取评论之前**执行
- 批量分类全部笔记（一次 LLM 调用），提高效率
- 不匹配的笔记直接跳过，不浪费评论 API 调用

---

## 防风控注意事项

### 请求节流
- 笔记间休眠 **3 秒**（`SLEEP_BETWEEN_NOTES = 3`）
- 搜索页间休眠 **2 秒**（`SLEEP_BETWEEN_SEARCHES = 2`）
- 获取评论超时 120 秒，下载超时 300 秒
- 不在短时间内大批量连续请求同一接口

### Cookie 与鉴权
- Cookie 存储在 `~/.xiaohongshu-cli/cookies.json`（JSON 格式，key-value + `saved_at` 字段）
- 每次运行前先 `xhs status` 确认 `authenticated: true`
- 若 cookie 超过 7 天，xhs CLI 会自动尝试从浏览器刷新

### 笔记下载方式
- 通过 `xhs read <note_id> --json` 获取笔记详情（标题、正文、图片 URL、标签）
- stdout 重定向到临时文件再解析，绕过 Rich 库 Windows GBK 编码乱码问题
- 图片通过 `urllib.request.urlretrieve` 直接下载，无需第三方工具
- 下载目录：`04_outputs/downloads/{note_id}_{title}/`
- 每篇笔记产出：1 个 `.txt` 文本文件 + N 张图片（.webp/.jpg）

### 编码处理
- 所有 `subprocess.run` 调用必须设置:
  - `encoding="utf-8"`, `errors="replace"`
  - 环境变量: `PYTHONIOENCODING=utf-8`, `PYTHONLEGACYWINDOWSSTDIO=utf-8`
- 避免 Windows GBK 编码导致 emoji 字符报错

### 容错策略
- 搜索失败时不中断，跳过该关键词/页继续
- xhs CLI 会话过期时提示用户重新登录（`xhs login` 或手动更新 cookie）
- LLM 调用失败时降级为关键词规则分类（`_keyword_fallback`）
- API 503 时自动重试 3 次，间隔递增

### 行为特征
- 使用与浏览器一致的 User-Agent
- 不要频繁切换搜索词或翻页模式
- 尽量在同一会话内完成批量操作，避免异常登录行为
- 如果触发验证码/风控，自动指数退避重试（首次 30s → 60s → 120s → 240s → 最大 300s），连续触发 5 次才放弃运行

---

## xhs CLI 交互规范

### 子进程调用
- 统一通过 `_xhs_subprocess(args, timeout)` 调用
- 自动处理 `ok`/`error` 信封格式
- 非零退出码或非 ok 响应当作 RuntimeError

### 关键命令
```
xhs search <keyword> --type image --sort general --page <N> --json
xhs search-user <keyword> --json   # 搜索博主，获取 user_id
xhs comments <note_id> --all --json [--xsec-token <token>]
xhs read <note_id> --json          # 获取笔记详情（用于下载）
xhs status                         # 检查认证状态
xhs login                          # 重新登录
python -m 01_Agent_Scraper.hunter [--perspective <标签>] [--red-id <小红书号>]
```

### xsec_token 传递
- 搜索结果的每个 item 对象同时包含 `id` 和 `xsec_token`
- 获取评论时通过 `--xsec-token` 参数传入，避免风控拦截

---

## 文件路径速查

| 用途 | 路径 |
|---|---|
| xhs CLI 命令 | `xhs` |
| Cookie 存储 | `~/.xiaohongshu-cli/cookies.json` |
| 种子 URL（降级） | `01_materials/seed_urls.txt` |
| Stage1 归档 | `data_pipeline/stage1_raw/qualified_urls_{时间}.txt` |
| 笔记下载 | `04_outputs/downloads/{note_id}_{title}/` |
| 爬取结果 | `01_materials/viral_examples/{时间}_爬取结果/` |
| 合格线索 | `04_outputs/qualified_leads.json` |
