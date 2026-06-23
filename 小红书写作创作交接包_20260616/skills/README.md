# Skills

这里放可迁移的 Codex skill。

## 当前 skill

| Skill | 用途 |
|---|---|
| `xhs-writing-creator` | 小红书写作、真实房源笔记、大字报封面、留痕包 |

## 安装方式

把整个目录复制到对方机器的 Codex skills 目录：

```bash
cp -R skills/xhs-writing-creator ~/.codex/skills/xhs-writing-creator
```

然后新开 Codex 会话，用下面的触发方式：

```text
Use $xhs-writing-creator 帮我基于这套资料写一篇小红书笔记，并做封面提示词和发布前检查。
```

如果对方没有 Codex skills 功能，也可以直接把 `skills/xhs-writing-creator/SKILL.md` 当 SOP 用。

