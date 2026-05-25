#!/usr/bin/env bash
set -euo pipefail

VERSION="2.0.0"
ECO_DIR="$HOME/.claude-ecosystems"
CURRENT_FILE="$ECO_DIR/.current"
ISOLATION_FILE="$ECO_DIR/.isolation"
DB_PATH="$HOME/.cc-switch/cc-switch.db"
CLAUDE_DIR="$HOME/.claude"

# ─── Colors ────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${GREEN}[cc-eco]${NC} $*"; }
warn()  { echo -e "${YELLOW}[cc-eco]${NC} $*"; }
error() { echo -e "${RED}[cc-eco]${NC} $*" >&2; }

# ─── Utility ───────────────────────────────────────────────────────────────

require_init() {
  if [[ ! -f "$CURRENT_FILE" ]]; then
    error "尚未初始化，请先运行: cc-eco init <name>"
    exit 1
  fi
}

get_current() {
  cat "$CURRENT_FILE" 2>/dev/null || true
}

get_isolation_items() {
  if [[ -f "$ISOLATION_FILE" ]]; then
    cat "$ISOLATION_FILE"
  fi
}

confirm() {
  if [[ ! -t 0 ]]; then
    return 1
  fi
  echo -n -e "${YELLOW}[cc-eco]${NC} 确认？(y/N) "
  local answer
  read -r answer
  [[ "$answer" =~ ^[Yy]$ ]]
}

backup_db() {
  local backup
  backup="${DB_PATH}.bak.$(date +%Y%m%d%H%M%S)"
  cp "$DB_PATH" "$backup"
  echo "$backup"
}

# ─── DB State: Save / Restore ──────────────────────────────────────────────

save_db_state() {
  local eco_name="$1"
  local state_file="$ECO_DIR/$eco_name/db-state.json"

  python3 -c "
import json, sqlite3, sys

db_path = sys.argv[1]
state_file = sys.argv[2]
eco_name = sys.argv[3]

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

state = {
    'version': 2,
    'name': eco_name,
    'skills': {},
    'mcp_servers': {},
    'provider_settings': {},
    'common_config': None
}

# Skills
for row in conn.execute('SELECT name, enabled_claude FROM skills'):
    state['skills'][row['name']] = {'enabled_claude': row['enabled_claude']}

# MCP servers
for row in conn.execute('SELECT name, enabled_claude FROM mcp_servers'):
    state['mcp_servers'][row['name']] = {'enabled_claude': row['enabled_claude']}

# Provider settings (current claude provider)
row = conn.execute(
    'SELECT settings_config FROM providers WHERE is_current = 1 AND app_type = ?',
    ('claude',)
).fetchone()
if row and row['settings_config']:
    try:
        settings = json.loads(row['settings_config'])
        # Only save fields that differ between ecosystems
        state['provider_settings'] = {
            'enabledPlugins': settings.get('enabledPlugins', []),
            'hooks': settings.get('hooks', {}),
        }
    except json.JSONDecodeError:
        pass

# Common config (key-value table)
row = conn.execute(
    'SELECT value FROM settings WHERE key = ?',
    ('common_config_claude',)
).fetchone()
if row and row['value']:
    try:
        state['common_config'] = json.loads(row['value'])
    except json.JSONDecodeError:
        pass

conn.close()

with open(state_file, 'w') as f:
    json.dump(state, f, indent=2, ensure_ascii=False)
" "$DB_PATH" "$state_file" "$eco_name"
}

restore_db_state() {
  local eco_name="$1"
  local state_file="$ECO_DIR/$eco_name/db-state.json"

  if [[ ! -f "$state_file" ]]; then
    error "找不到 $eco_name/db-state.json，请先运行: cc-eco snapshot $eco_name"
    exit 1
  fi

  python3 -c "
import json, sqlite3, sys

db_path = sys.argv[1]
state_file = sys.argv[2]

with open(state_file) as f:
    state = json.load(f)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Restore skills enabled state
for skill_name, skill_data in state.get('skills', {}).items():
    cursor.execute(
        'UPDATE skills SET enabled_claude = ? WHERE name = ?',
        (skill_data['enabled_claude'], skill_name)
    )

# Restore MCP servers enabled state
for server_name, server_data in state.get('mcp_servers', {}).items():
    cursor.execute(
        'UPDATE mcp_servers SET enabled_claude = ? WHERE name = ?',
        (server_data['enabled_claude'], server_name)
    )

# Restore provider settings
provider_settings = state.get('provider_settings', {})
if provider_settings:
    # Read current settings_config, merge changed fields
    row = cursor.execute(
        'SELECT settings_config FROM providers WHERE is_current = 1 AND app_type = ?',
        ('claude',)
    ).fetchone()
    if row and row[0]:
        try:
            current = json.loads(row[0])
        except json.JSONDecodeError:
            current = {}
    else:
        current = {}

    if 'enabledPlugins' in provider_settings:
        current['enabledPlugins'] = provider_settings['enabledPlugins']
    if 'hooks' in provider_settings:
        current['hooks'] = provider_settings['hooks']

    cursor.execute(
        'UPDATE providers SET settings_config = ? WHERE is_current = 1 AND app_type = ?',
        (json.dumps(current, ensure_ascii=False), 'claude')
    )

# Restore common config (key-value table)
common_config = state.get('common_config')
if common_config is not None:
    cursor.execute(
        'INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
        ('common_config_claude', json.dumps(common_config, ensure_ascii=False))
    )

conn.commit()
conn.close()
" "$DB_PATH" "$state_file"
}

# ─── Regenerate settings.json from DB ──────────────────────────────────────

regenerate_settings() {
  python3 -c "
import json, sqlite3, sys

db_path = sys.argv[1]
settings_path = sys.argv[2]

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# Read current provider settings
row = conn.execute(
    'SELECT settings_config FROM providers WHERE is_current = 1 AND app_type = ?',
    ('claude',)
).fetchone()

if not row or not row['settings_config']:
    conn.close()
    sys.exit(0)

try:
    settings = json.loads(row['settings_config'])
except json.JSONDecodeError:
    conn.close()
    sys.exit(0)

# Merge common config if enabled
common_row = conn.execute(
    'SELECT value FROM settings WHERE key = ?',
    ('common_config_claude',)
).fetchone()
common_enabled_row = conn.execute(
    'SELECT value FROM settings WHERE key = ?',
    ('common_config_enabled',)
).fetchone()

if common_row and common_row['value'] and common_enabled_row and common_enabled_row['value'] == 'true':
    try:
        common = json.loads(common_row['value'])
        merged = {**common, **settings}
        settings = merged
    except (json.JSONDecodeError, TypeError):
        pass

# Add enabled MCP servers
mcp_servers = {}
for mcp_row in conn.execute('SELECT name, server_config FROM mcp_servers WHERE enabled_claude = 1'):
    try:
        mcp_servers[mcp_row['name']] = json.loads(mcp_row['server_config'])
    except (json.JSONDecodeError, TypeError):
        mcp_servers[mcp_row['name']] = {}

if mcp_servers:
    settings['mcpServers'] = mcp_servers

# Sanitize: remove internal fields
for key in ['apiFormat', 'apiKey', 'baseUrl', 'model', 'providerName']:
    settings.pop(key, None)

conn.close()

with open(settings_path, 'w') as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)
" "$DB_PATH" "$CLAUDE_DIR/settings.json"
}

# ─── Sync skills symlinks ──────────────────────────────────────────────────

sync_skills_symlinks() {
  local eco_name="$1"
  local state_file="$ECO_DIR/$eco_name/db-state.json"

  if [[ ! -f "$state_file" ]]; then
    return
  fi

  # Build enabled/disabled lists from db-state.json
  local enabled_list disabled_list
  enabled_list="$(python3 -c "
import json, sys
with open(sys.argv[1]) as f:
    state = json.load(f)
for name, data in state.get('skills', {}).items():
    if data.get('enabled_claude') == 1:
        print(name)
" "$state_file")"

  disabled_list="$(python3 -c "
import json, sys
with open(sys.argv[1]) as f:
    state = json.load(f)
for name, data in state.get('skills', {}).items():
    if data.get('enabled_claude') == 0:
        print(name)
" "$state_file")"

  local skills_dir="$CLAUDE_DIR/skills"

  # Delete disabled skills
  if [[ -n "$disabled_list" ]]; then
    while IFS= read -r skill_name; do
      [[ -z "$skill_name" ]] && continue
      if [[ -L "$skills_dir/$skill_name" || -d "$skills_dir/$skill_name" ]]; then
        rm -rf "${skills_dir:?}/$skill_name"
      fi
    done < <(echo "$disabled_list")
  fi

  # Create enabled skills (symlink to cc-switch)
  if [[ -n "$enabled_list" ]]; then
    while IFS= read -r skill_name; do
      [[ -z "$skill_name" ]] && continue
      if [[ ! -e "$skills_dir/$skill_name" ]]; then
        if [[ -d "$HOME/.cc-switch/skills/$skill_name" ]]; then
          ln -s "$HOME/.cc-switch/skills/$skill_name" "$skills_dir/$skill_name"
        fi
      fi
    done < <(echo "$enabled_list")
  fi

  # Clean orphan symlinks (pointing to cc-switch but not in db-state)
  local known_names
  known_names="$(python3 -c "
import json, sys
with open(sys.argv[1]) as f:
    state = json.load(f)
for name in state.get('skills', {}).keys():
    print(name)
" "$state_file")"

  if [[ -d "$skills_dir" ]] && [[ -n "$(ls -A "$skills_dir" 2>/dev/null)" ]]; then
    for entry in "$skills_dir"/*; do
      [[ ! -e "$entry" ]] && continue
      local entry_name
      entry_name="$(basename "$entry")"
      local is_known
      is_known="$(echo "$known_names" | grep -xF "$entry_name" || true)"
      if [[ -z "$is_known" && -L "$entry" ]]; then
        local target
        target="$(readlink "$entry")"
        if [[ "$target" == "$HOME/.cc-switch/skills/"* ]]; then
          rm -f "$entry"
        fi
      fi
    done
  fi
}

# ─── Help ──────────────────────────────────────────────────────────────────

show_help() {
  cat <<EOF
cc-eco v${VERSION} — Claude Code 生态切换工具

用法: cc-eco <command> [options]

命令:
  init <name>              初始化，当前状态存为 <name> 快照
  snapshot <name>          从当前生态创建新快照
  switch <name>            切换到目标生态
  status                   显示当前生态状态
  list                     列出所有生态
  delete <name> [--force]  删除生态
  discover                 发现可能需要隔离的新路径
  adopt <path>             将路径加入隔离
  isolate                  显示当前隔离的路径列表

选项:
  -h, --help               显示帮助信息
  -v, --version            显示版本号
EOF
}

show_help_init() {
  echo "用法: cc-eco init <name>"
  echo "  初始化 cc-eco，将当前状态存为 <name> 快照"
}

show_help_snapshot() {
  echo "用法: cc-eco snapshot <name>"
  echo "  从当前生态创建新快照 <name>"
}

show_help_switch() {
  echo "用法: cc-eco switch <name> [--no-restart]"
  echo "  切换到目标生态 <name>"
  echo "  默认自动重启 Claude Code 和 CC Switch"
  echo "  --no-restart  不自动重启"
}

show_help_status() { echo "用法: cc-eco status — 显示当前生态状态"; }
show_help_list()   { echo "用法: cc-eco list — 列出所有生态"; }
show_help_delete() { echo "用法: cc-eco delete <name> [--force|-f] — 删除生态"; }
show_help_discover() { echo "用法: cc-eco discover — 发现可能需要隔离的新路径"; }
show_help_adopt() { echo "用法: cc-eco adopt <path> — 将路径加入隔离"; }
show_help_isolate() { echo "用法: cc-eco isolate — 显示当前隔离的路径列表"; }

# ─── Commands ──────────────────────────────────────────────────────────────

cmd_init() {
  local name="${1:-}"
  if [[ -z "$name" ]]; then
    error "缺少生态名称，用法: cc-eco init <name>"
    exit 1
  fi

  if [[ -f "$CURRENT_FILE" ]]; then
    error "已经初始化过了（当前生态: $(get_current)）"
    exit 1
  fi

  if [[ -d "$ECO_DIR/$name" && ! -f "$ECO_DIR/$name/eco.json" ]]; then
    error "目录 $ECO_DIR/$name/ 已存在但不是有效的生态快照"
    exit 1
  fi

  mkdir -p "$ECO_DIR/$name"

  # Move isolated paths into snapshot
  while IFS= read -r item; do
    [[ -z "$item" ]] && continue
    local src="$CLAUDE_DIR/$item"
    local dst="$ECO_DIR/$name/$item"

    if [[ -L "$src" ]]; then
      # Existing symlink: resolve and copy target, remove symlink
      local real_target
      real_target="$(readlink "$src")"
      if [[ -d "$real_target" ]]; then
        cp -a "$real_target" "$dst"
      else
        cp -a "$real_target" "$dst"
      fi
      rm -f "$src"
    elif [[ -d "$src" ]]; then
      mv "$src" "$dst"
    elif [[ -e "$src" ]]; then
      mv "$src" "$dst"
    else
      mkdir -p "$dst"
    fi

    ln -s "$dst" "$src"
  done < <(get_isolation_items)

  # Save current DB state
  save_db_state "$name"

  # Create eco.json
  python3 -c "
import json, sys
d = {
    'name': sys.argv[1],
    'skill_repos': [],
    'enabled_plugins': [],
    'description': ''
}
with open(sys.argv[2], 'w') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
" "$name" "$ECO_DIR/$name/eco.json"

  echo "$name" > "$CURRENT_FILE"
  info "初始化完成，当前生态: $name"
}

cmd_snapshot() {
  require_init
  local name="${1:-}"
  if [[ -z "$name" ]]; then
    error "缺少快照名称，用法: cc-eco snapshot <name>"
    exit 1
  fi

  local current
  current="$(get_current)"

  if [[ -d "$ECO_DIR/$name" ]]; then
    error "快照 '$name' 已存在"
    exit 1
  fi

  cp -a "$ECO_DIR/$current/" "$ECO_DIR/$name/"

  # Update eco.json: set name, clear skill_repos and description
  python3 -c "
import json, sys
f = sys.argv[1]
d = json.load(open(f))
d['name'] = sys.argv[2]
d['skill_repos'] = []
d['description'] = ''
json.dump(d, open(f, 'w'), indent=2, ensure_ascii=False)
" "$ECO_DIR/$name/eco.json" "$name"

  # Save current DB state to new snapshot
  save_db_state "$name"

  warn "请编辑 $ECO_DIR/$name/eco.json 设置 skill_repos 和 description"

  info "快照 '$name' 已从 '$current' 创建"
}

cmd_switch() {
  require_init
  local name=""
  local no_restart=false
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --no-restart) no_restart=true; shift ;;
      -*) error "未知选项: $1"; exit 1 ;;
      *) name="$1"; shift ;;
    esac
  done

  local current
  current="$(get_current)"

  if [[ "$name" == "$current" ]]; then
    error "已经在 '$name' 生态中"
    exit 1
  fi

  if [[ ! -d "$ECO_DIR/$name" ]]; then
    error "生态 '$name' 不存在"
    exit 1
  fi

  if [[ ! -f "$ECO_DIR/$name/db-state.json" ]]; then
    error "生态 '$name' 缺少 db-state.json，请先运行: cc-eco snapshot $name"
    exit 1
  fi

  # Phase 1: Save current DB state
  info "Phase 1: 保存当前生态 '$current' 的状态..."
  backup_db > /dev/null
  save_db_state "$current"

  # Phase 2: Restore target DB state
  info "Phase 2: 恢复目标生态 '$name' 的状态..."
  restore_db_state "$name"

  # Phase 3: Replace file-level symlinks
  info "Phase 3: 切换文件符号链接..."
  while IFS= read -r item; do
    [[ -z "$item" ]] && continue
    local src="$CLAUDE_DIR/$item"
    if [[ -L "$src" ]]; then
      rm -f "$src"
      ln -s "$ECO_DIR/$name/$item" "$src"
    else
      warn "$src 不是符号链接，跳过"
    fi
  done < <(get_isolation_items)

  # Phase 4: Sync skills symlinks
  info "Phase 4: 同步 skills 符号链接..."
  sync_skills_symlinks "$name"

  # Phase 5: Regenerate settings.json
  info "Phase 5: 重新生成 settings.json..."
  regenerate_settings

  echo "$name" > "$CURRENT_FILE"

  if [[ "$no_restart" == true ]]; then
    info "已切换到 '$name'（未重启，请手动重启 Claude Code 和 CC Switch）"
  else
    info "已切换到 '$name'，正在重启 Claude Code 和 CC Switch..."
    # Kill CC Switch
    pkill -x "cc-switch" 2>/dev/null || true
    sleep 1
    # Kill Claude Code
    pkill -x "claude" 2>/dev/null || true
    sleep 1
    # Restart CC Switch
    open "/Applications/CC Switch.app" 2>/dev/null || warn "无法启动 CC Switch"
    # Restart Claude Code in a new terminal
    osascript -e 'tell application "Terminal" to do script "claude"' 2>/dev/null || warn "无法启动 Claude Code"
    info "重启完成"
  fi
}

cmd_status() {
  require_init
  local current
  current="$(get_current)"

  echo -e "${CYAN}当前生态:${NC} $current"
  echo ""

  echo -e "${CYAN}隔离项:${NC}"
  while IFS= read -r item; do
    [[ -z "$item" ]] && continue
    local src="$CLAUDE_DIR/$item"
    if [[ -L "$src" ]]; then
      local target
      target="$(readlink "$src")"
      echo "  $item → $target"
    elif [[ -e "$src" ]]; then
      echo -e "  $item ${YELLOW}(非符号链接)${NC}"
    else
      echo -e "  $item ${RED}(不存在)${NC}"
    fi
  done < <(get_isolation_items)

  # Show skills count
  local skills_dir="$CLAUDE_DIR/skills"
  if [[ -d "$skills_dir" ]]; then
    local total
    total="$(find "$skills_dir" -maxdepth 1 -not -name '.' -not -name '..' | wc -l | tr -d ' ')"
    local db_enabled
    db_enabled="$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM skills WHERE enabled_claude = 1" 2>/dev/null || echo "?")"
    echo ""
    echo -e "${CYAN}Skills:${NC} 目录 $total 个 | DB enabled $db_enabled 个"
  fi

  # Show MCP servers
  local mcp_enabled
  mcp_enabled="$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM mcp_servers WHERE enabled_claude = 1" 2>/dev/null || echo "?")"
  echo -e "${CYAN}MCP Servers:${NC} DB enabled $mcp_enabled 个"

  # Show db-state.json info
  if [[ -f "$ECO_DIR/$current/db-state.json" ]]; then
    local state_skills state_mcp
    state_skills="$(python3 -c "import json; d=json.load(open('$ECO_DIR/$current/db-state.json')); print(len(d.get('skills',{})))" 2>/dev/null || echo "?")"
    state_mcp="$(python3 -c "import json; d=json.load(open('$ECO_DIR/$current/db-state.json')); print(len(d.get('mcp_servers',{})))" 2>/dev/null || echo "?")"
    echo -e "${CYAN}db-state.json:${NC} skills $state_skills | mcp_servers $state_mcp"
  fi
}

cmd_list() {
  require_init
  local current
  current="$(get_current)"

  for dir in "$ECO_DIR"/*/; do
    [[ ! -d "$dir" ]] && continue
    local name
    name="$(basename "$dir")"
    local size
    size="$(du -sh "$dir" 2>/dev/null | cut -f1)"
    local marker=""
    if [[ "$name" == "$current" ]]; then
      marker=" ← 当前"
    fi
    local has_state=""
    if [[ -f "$dir/db-state.json" ]]; then
      has_state=" [db-state]"
    fi
    echo "  $name ($size)$has_state$marker"
  done
}

cmd_delete() {
  require_init
  local name=""
  local force=false
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --force|-f) force=true; shift ;;
      -*) error "未知选项: $1"; exit 1 ;;
      *) name="$1"; shift ;;
    esac
  done
  if [[ -z "$name" ]]; then
    error "缺少生态名称，用法: cc-eco delete <name> [--force]"
    exit 1
  fi

  local current
  current="$(get_current)"
  if [[ "$name" == "$current" ]]; then
    error "不能删除当前生态 '$name'"
    exit 1
  fi

  if [[ ! -d "$ECO_DIR/$name" ]]; then
    error "生态 '$name' 不存在"
    exit 1
  fi

  if [[ "$force" == false ]]; then
    if ! confirm "确定要删除生态 '$name' 吗？"; then
      info "已取消"
      return
    fi
  fi

  rm -rf "${ECO_DIR:?}/$name"
  info "生态 '$name' 已删除"
}

cmd_discover() {
  require_init
  local isolated
  isolated="$(get_isolation_items)"

  # Runtime data to exclude
  local exclude_regex="^(transcripts|history\.jsonl|cache|backups|file-history|session-env|sessions|tasks|telemetry|plans|shell-snapshots|proxy|statsig|\.DS_Store)$"

  echo -e "${CYAN}可能需要隔离的路径:${NC}"
  local found=0
  for entry in "$CLAUDE_DIR"/*; do
    [[ ! -e "$entry" ]] && continue
    local entry_name
    entry_name="$(basename "$entry")"

    # Skip if already isolated
    if [[ -n "$isolated" ]] && echo "$isolated" | grep -qx "$entry_name"; then
      continue
    fi

    # Skip runtime data
    if echo "$entry_name" | grep -qE "$exclude_regex"; then
      continue
    fi

    # Skip symlinks (already managed)
    if [[ -L "$entry" ]]; then
      continue
    fi

    # Skip settings files (managed via DB)
    if [[ "$entry_name" == "settings.json" || "$entry_name" == "settings.local.json" ]]; then
      continue
    fi

    echo "  $entry_name ($(du -sh "$entry" 2>/dev/null | cut -f1))"
    found=$((found + 1))
  done

  if [[ $found -eq 0 ]]; then
    echo "  (无新发现)"
  fi
}

cmd_adopt() {
  require_init
  local path="${1:-}"
  if [[ -z "$path" ]]; then
    error "缺少路径，用法: cc-eco adopt <path>"
    exit 1
  fi

  local src="$CLAUDE_DIR/$path"
  if [[ ! -e "$src" ]]; then
    error "$src 不存在"
    exit 1
  fi

  if [[ -L "$src" ]]; then
    error "$src 已经是符号链接"
    exit 1
  fi

  local current
  current="$(get_current)"

  mv "$src" "$ECO_DIR/$current/$path"
  ln -s "$ECO_DIR/$current/$path" "$src"

  # Add to .isolation
  if ! grep -qx "$path" "$ISOLATION_FILE" 2>/dev/null; then
    echo "$path" >> "$ISOLATION_FILE"
  fi

  # Create empty dirs in other snapshots
  for dir in "$ECO_DIR"/*/; do
    [[ ! -d "$dir" ]] && continue
    local name
    name="$(basename "$dir")"
    if [[ "$name" != "$current" && ! -e "$dir/$path" ]]; then
      mkdir -p "$dir/$path"
    fi
  done

  info "已将 '$path' 加入隔离"
}

cmd_isolate() {
  require_init
  echo -e "${CYAN}当前隔离的路径:${NC}"
  while IFS= read -r item; do
    [[ -z "$item" ]] && continue
    echo "  $item"
  done < <(get_isolation_items)
}

# ─── Main ──────────────────────────────────────────────────────────────────

cmd="${1:-}"
shift 2>/dev/null || true

case "$cmd" in
  -h|--help)     show_help; exit 0 ;;
  -v|--version)  echo "cc-eco v$VERSION"; exit 0 ;;
  init)
    [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && show_help_init && exit 0
    cmd_init "$@"
    ;;
  snapshot)
    [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && show_help_snapshot && exit 0
    cmd_snapshot "$@"
    ;;
  switch)
    [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && show_help_switch && exit 0
    cmd_switch "$@"
    ;;
  status)
    [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && show_help_status && exit 0
    cmd_status
    ;;
  list)
    [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && show_help_list && exit 0
    cmd_list
    ;;
  delete)
    [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && show_help_delete && exit 0
    cmd_delete "$@"
    ;;
  discover)
    [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && show_help_discover && exit 0
    cmd_discover
    ;;
  adopt)
    [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && show_help_adopt && exit 0
    cmd_adopt "$@"
    ;;
  isolate)
    [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && show_help_isolate && exit 0
    cmd_isolate
    ;;
  "")
    error "缺少命令，运行 cc-eco -h 查看帮助"
    exit 1
    ;;
  *)
    error "未知命令: $cmd，运行 cc-eco -h 查看帮助"
    exit 1
    ;;
esac
