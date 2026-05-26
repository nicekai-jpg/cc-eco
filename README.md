# cc-eco

Claude Code 生态切换工具，在 [CC Switch](https://ccswitch.io) 之上增加生态维度，实现 Superpowers / GSD / ... 的完全隔离与快速切换。

## 核心理念

**存档/读档模式**：每个生态保存完整的 DB 状态快照（`db-state.json`），切换时直接保存当前状态、恢复目标状态，不依赖推算。

## 安装

```bash
# 方式一：pip 安装（推荐）
pip3 install cc-eco

# 方式二：一键安装
curl -fsSL https://raw.githubusercontent.com/nicekai-jpg/cc-eco/main/install.sh | bash
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
| `~/.claude/commands/` | 符号链接快照 |
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
Phase 2: 备份 — 备份 CC Switch 数据库
Phase 3: 读档 — 从目标生态的 db-state.json 恢复 DB 状态
Phase 4: 换传送门 — 替换文件级符号链接
Phase 5: 同步 skills — 删除禁用的、创建启用的符号链接
Phase 6: 重新生成 settings.json
Phase 7: 重启 — 重启 Claude Code 和 CC Switch
```

## 跨平台支持

| 平台 | 支持级别 | 说明 |
|------|---------|------|
| macOS | 完整 | pkill + open + osascript |
| Linux | 完整 | pkill + xdg-terminal-emulator / 检测终端 |
| Windows | 尽力 | taskkill + os.startfile，符号链接需开发者模式 |

## 依赖

- [CC Switch](https://ccswitch.io) — Claude Code 配置管理工具
- Python 3.9+ — 运行时（macOS/Linux 自带）

## 从 v2 升级

v3 与 v2 数据格式完全兼容，无需迁移：

- `db-state.json` 格式不变
- `eco.json` 格式不变
- `~/.claude-ecosystems/` 目录结构不变

重新运行安装脚本即可升级，旧版 `cc-eco.sh` 会被自动清理。

## License

MIT
