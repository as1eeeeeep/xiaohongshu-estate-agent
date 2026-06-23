# 小红书写作创作交接包

这个包给能接手内容创作的人或 Agent 用。目标很简单：用真实资料写出能发布、能复盘、不过度销售的小红书内容。

## 先看哪几份

| 文件 | 用途 |
|---|---|
| `AGENTS.md` | 给 AI / Codex 用的执行规则 |
| `docs/01-创作流程总览.md` | 从一句任务到留痕包的完整流程 |
| `docs/02-Skills清单与分工.md` | 我常用的 skill 和各自负责什么 |
| `docs/04-大字报封面与生图SOP.md` | 生图模型做小红书大字报封面的做法 |
| `skills/xhs-writing-creator/` | 可复制安装的 Codex skill |
| `cases/case01_syp440_dazibao/README.md` | 已验证可用的大字报封面案例 |
| `templates/note_package/` | 每篇笔记建包时直接复制的模板 |

## 默认工作流

```text
真实资料 -> 对标拆解 -> 标题公式 -> 正文初稿 -> AI 感检查 -> 图片/封面 -> 审核 -> 留痕包
```

做香港房产内容时，多加一条：房源、价格、面积、地铁、成交都必须有来源，不能编。

## 最小交付

一篇笔记最少要交付：

- 标题 6 个，标明标题公式或触发器。
- 正文 1-2 版，不像内部汇报。
- 封面短句和图片顺序。
- 生图提示词或真实图来源。
- 发布前检查：事实、合规、用户视角。

## 不要原样复制案例

`cases/` 是学习样板，不是发布素材库。别人接手后要替换自己的房源、品牌、资质、价格有效期和联系方式。

## 如果对方想装成 skill

把 `skills/xhs-writing-creator/` 复制到对方的 Codex skills 目录：

```bash
cp -R skills/xhs-writing-creator ~/.codex/skills/xhs-writing-creator
```

以后可以这样触发：

```text
Use $xhs-writing-creator 帮我基于这套资料写一篇小红书笔记，并做封面提示词和发布前检查。
```

