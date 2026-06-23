# Agent3（小红书房产文案生成器）调用规则

## 强制规则：必须通过脚本执行，禁止手写模仿

任何"用 Agent3 风格写小红书文案""按 amateur/agent/lean persona 生成房产笔记"
之类的批量生成任务，必须通过 subprocess 执行真实脚本：

```
python 03_Agent_Generator/writer.py --persona <amateur|agent|lean> --count N [--run-id ...]
```

**禁止自己手写文案来模仿 Agent3 的 persona 风格。** 手写内容不是 Agent3 的真实输出——
它绕过了 `writer.py` 内置的：

- 固定 system prompt（每个 persona 的人设、Hook Strategy、禁用词列表）
- 程序化输出校验 `_validate_note()`（标题长度 / 禁用词 / emoji数量 / CTA完整性 /
  lean persona 的装修风格词和"致命伤缺点"红线检查）
- 固定的 `HEAVY_MODEL` 调用（`shared/config.py` 里配置的模型，不是当前对话用的模型）

手写文案的风格会随"当前是哪个 AI 在写"而漂移——这正是 Agent3 重构前反复出现的
稳定性问题的根因。脚本本身已经是确定性、可重复、有校验关卡的，唯一的风险点是
"调用者绕开脚本自己写"，所以这条规则必须严格遵守。

这条规则对所有编程助手生效，不限于 Claude Code——Codex、其他 agent 同样适用。

## 例外

只有以下情况可以不调用脚本：
- 用户明确要求"帮我手写/改写这一篇具体文案"（针对单篇已有内容的人工编辑，不是批量生成新内容）
- 阅读/分析已生成的输出文件（不涉及新生成内容）

## 脚本位置与用法

- 主脚本: `03_Agent_Generator/writer.py`
- 三个 persona: `amateur`（素人）/ `agent`（中介）/ `lean`（极简中介）
- 默认从 `01_materials/properties/` 随机选房源；可用 `--property-dir` 指定
- 输出: `04_outputs/{run_id}/drafts/`（JSON 草稿）+ `04_outputs/{run_id}/pre-published/`（发布稿 .md）
- 详细设计文档: `.claude/skills/agent3-writer.md`

## 当前已知限制（不要凭记忆假设，先看代码）

- 已移除：封面图生成、discussion persona、策略文件落盘（`save_strategy()` 已删除）
- 模型固定为 `shared/config.py` 中的 `HEAVY_MODEL`（当前 `gemini-3.1-pro-preview`，preview
  模型可能被 Google 静默更新/弃用，如果输出风格突然漂移先检查这里）
- 如果代码和这份文档/skill 文档冲突，以 `writer.py` 实际代码为准

## 另起的生图 Agent

封面图生成功能已从 Agent3 完全移除。如果你正在用 Codex 单独搭建一个新的生图 agent
来接续这部分功能，请只继承红线规则（房间不能放大、不能遮挡窗户、不能有文字水印、
保持房间真实功能）和房间类型软装方案，不要依赖任何已删除的 `writer.py` 符号
（`generate_cover()` / `_find_living_room_image()` / `_build_cover_prompt()` 等均已不存在）。

这个独立生图 agent 已经落地在 `06_Agent_CoverCreator/`（选图 → AI 装修生图 → 红线质检
重试 → 本地排版加字，5种封面风格）。调用方式见该目录下的 `README.md`，统一入口是
`06_Agent_CoverCreator/run.sh`，Codex 和 Claude Code 都应该调这个脚本，不要手写复刻它的
prompt 逻辑——原因和 Agent3 禁止手写模仿一样：脚本是确定性的，手写会导致风格漂移。
