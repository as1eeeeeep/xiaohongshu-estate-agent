# Skills 清单与分工

这里写的是创作链路里真正有用的 skill，不是越多越好。

## 文字类

| Skill | 负责什么 | 怎么用 |
|---|---|---|
| `dbs-benchmark` | 拆对标 | 拆标题、首句、图片分工、风险写法、承接动作 |
| `dbs-content` | 内容诊断 | 判断选题是否成立，不直接让它代笔 |
| `dbs-xhs-title` | 标题公式 | 每次至少出 6 个标题，覆盖 3 类触发器 |
| `dbs-hook` | 开头诊断 | 看第一句能不能独立抓人 |
| `dbs-ai-check` | AI 感检查 | 查汇报腔、排比腔、中介喊单、空概念 |
| `humanizer-zh` | 去 AI 味 | 删空话、套话、三段式、机械 emoji |

## 图片类

| Skill / 能力 | 负责什么 | 边界 |
|---|---|---|
| `imagegen` / 生图模型 | 封面底图、大字报、概念封面 | 不能伪装成真实房源实拍 |
| `baoyu-xhs-images` | 小红书图片卡片系列 | 提示词要留痕，优先栅格化成图 |
| `guizang-social-card-skill` | 3:4 组图、证据页、封面结构 | 可借版式，不得伪造数据 |
| `ian-xiaohei-illustrations` | 正文解释图、流程图、知识库配图 | 默认 16:9，不直接当房源封面 |

## 房源资料类

| 能力 | 负责什么 | 边界 |
|---|---|---|
| `songshu_house` MCP | 查真实屋苑、房源、成交、详情、附近房源 | 没有返回的字段不要编 |
| 人工资料表 | 没有 MCP 时兜底 | 必须填来源和日期 |

## 推荐调用顺序

```text
资料 / MCP
-> dbs-benchmark
-> dbs-content
-> dbs-xhs-title
-> dbs-hook
-> draft
-> dbs-ai-check
-> humanizer-zh
-> imagegen / guizang / baoyu / xiaohei
-> pre_publish_check
```

## 什么时候不用重 skill

| 场景 | 处理 |
|---|---|
| 只写一条短置顶评论 | 用 `dbs-ai-check` + `humanizer-zh` 就够 |
| 只是整理真实资料 | 不用标题公式 |
| 正文已经表现稳定 | 不强行套 6 个标题 |
| 长文报告 | 再考虑 `khazix-writer`，短笔记不用 |

