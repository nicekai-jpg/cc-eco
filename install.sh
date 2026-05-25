#!/usr/bin/env bash
# cc-eco installer
# Usage: curl -fsSL https://raw.githubusercontent.com/limingkai/cc-eco/main/install.sh | bash

set -euo pipefail

ECO_DIR="$HOME/.claude-ecosystems"
SCRIPT_SRC="https://raw.githubusercontent.com/limingkai/cc-eco/main/cc-eco.sh"

echo "[cc-eco] Installing..."

# Download script
mkdir -p "$ECO_DIR"
curl -fsSL "$SCRIPT_SRC" -o "$ECO_DIR/cc-eco.sh"
chmod +x "$ECO_DIR/cc-eco.sh"

# Add alias to .zshrc if not present
if ! grep -q "alias cc-eco=" "$HOME/.zshrc" 2>/dev/null; then
  echo "" >> "$HOME/.zshrc"
  echo "# cc-eco: Claude Code ecosystem switcher" >> "$HOME/.zshrc"
  echo "alias cc-eco='bash $ECO_DIR/cc-eco.sh'" >> "$HOME/.zshrc"
fi

# Add alias to .bashrc if not present
if ! grep -q "alias cc-eco=" "$HOME/.bashrc" 2>/dev/null; then
  echo "" >> "$HOME/.bashrc"
  echo "# cc-eco: Claude Code ecosystem switcher" >> "$HOME/.bashrc"
  echo "alias cc-eco='bash $ECO_DIR/cc-eco.sh'" >> "$HOME/.bashrc"
fi

echo "[cc-eco] Done! Run 'source ~/.zshrc' or open a new terminal, then:"
echo "  cc-eco init <name>    # Initialize with current state"
echo "  cc-eco -h             # Show help"
