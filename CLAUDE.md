# Claude Code 项目入口

这个仓库的真实工作目录是：

```bash
/Users/asleep/松鼠找房/agent
```

Claude Code 如果从 `/Users/asleep/松鼠找房` 启动，先执行：

```bash
cd "/Users/asleep/松鼠找房/agent"
```

然后读取并遵守：

```text
/Users/asleep/松鼠找房/agent/CLAUDE.md
```

## Agent6 封面生成

运行封面生成时，优先使用绝对路径，避免 Claude Code 在外层目录触发
`ENOENT: Bun could not find a file`：

```bash
/Users/asleep/松鼠找房/agent/06_Agent_CoverCreator/run.sh /Users/asleep/松鼠找房/agent/06_Agent_CoverCreator/input/listing-001 \
  --title "香港质感小家" \
  --subtitle "精装客厅｜明亮窗景"
```

不要手写复刻 Agent3 或 Agent6 的 prompt 逻辑；调用真实脚本。
