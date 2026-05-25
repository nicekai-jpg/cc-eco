# cc-eco

Claude Code 生态切换工具，在 [CC Switch](https://ccswitch.io) 之上增加生态维度，实现 Superpowers / GSD / ... 的完全隔离与快速切换。

## 核心理念

**存档/读档模式**：每个生态保存完整的 DB 状态快照（`db-state.json`），切换时直接保存当前状态、恢复目标状态，不依赖推算。

## 安装

```bash
curl -fsSL https://raw.githubusercontent.com/limingkai/cc-eco/main/install.sh | bash
```

或手动安装：

```bash
mkdir -p ~/.claude-ecosystems
curl -fsSL https://raw.githubusercontent.com/limingkai/cc-eco/main/cc-eco.sh -o ~/.claude-ecosystems/cc-eco.sh
# 在 .zshrc 中添加：
alias cc-eco='bash ~/.claude-ecosystems/cc-eco.sh'
```

## 用法

```bash
cc-eco init <name>              # 初始化，当前状态存为 <name> 快照
cc-eco snapshot <name>          # 从当前生态创建新快照
cc-eco switch <name>            # 切换到目标生态（自动重启）
cc-eco switch <name> --no-restart  # 切换但不重启
cc-eco status                   # 显示当前生态状态
cc-eco list                     # 列出所有生态
cc-eco delete <name> [--force]  # 删除生态
cc-eco discover                 # 发现可能需要隔离的新路径
cc-eco adopt <path>             # 将路径加入隔离
cc-eco isolate                  # 显示当前隔离的路径列表
```

## 快速开始

```bash
# 1. 初始化（当前状态存为 superpowers 快照）
cc-eco init superpowers

# 2. 创建 gsd 快照
cc-eco snapshot gsd

# 3. 编辑 gsd 的配置
vim ~/.claude-ecosystems/gsd/eco.json
vim ~/.claude-ecosystems/gsd/db-state.json

# 4. 切换到 gsd
cc-eco switch gsd

# 5. 切回 superpowers
cc-eco switch superpowers
```

## 隔离的文件

| 路径 | 方式 |
|------|------|
| `~/.claude/skills/` | 符号链接快照 |
| `~/.claude/agents/` | 符号链接快照 |
| `~/.claude/hooks/` | 符号链接快照 |
| `~/.claude/get-shit-done/` | 符号链接快照 |
| `~/.claude/settings.json` | DB 状态恢复后重新生成 |

## 隔离的 DB 状态

| 表 | 字段 |
|----|------|
| `skills` | `enabled_claude` |
| `mcp_servers` | `enabled_claude` |
| `providers` | `settings_config`（enabledPlugins、hooks） |
| `settings` | `common_config_claude` |

## 切换流程

```
Phase 1: 存档 — 保存当前 DB 状态到当前生态的 db-state.json
Phase 2: 读档 — 从目标生态的 db-state.json 恢复 DB 状态
Phase 3: 换传送门 — 替换文件级符号链接
Phase 4: 同步 skills — 删除禁用的、创建启用的符号链接
Phase 5: 重新生成 settings.json
```

## 依赖

- [CC Switch](https://ccswitch.io) — Claude Code 配置管理工具
- Python 3 — 解析 JSON 和操作 SQLite
- SQLite 3 — 读写 CC Switch 数据库

## License

MIT
