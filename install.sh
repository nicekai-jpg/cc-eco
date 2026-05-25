#!/usr/bin/env bash
# cc-eco v3 installer
# Usage: curl -fsSL https://raw.githubusercontent.com/limingkai/cc-eco/main/install.sh | bash

set -euo pipefail

ECO_DIR="$HOME/.claude-ecosystems"
REPO_URL="https://raw.githubusercontent.com/limingkai/cc-eco/main"

echo "[cc-eco] Installing v3..."

# Try pip install first
if command -v pip3 &>/dev/null; then
  if pip3 install git+https://github.com/limingkai/cc-eco.git 2>/dev/null; then
    echo "[cc-eco] Installed via pip. Run 'cc-eco -h' to get started."
    exit 0
  fi
fi

# Fallback: manual download
echo "[cc-eco] pip not available, installing manually..."

mkdir -p "$ECO_DIR/cc_eco"

for file in __init__.py __main__.py cli.py db.py fs.py platform_restart.py utils.py; do
  curl -fsSL "$REPO_URL/cc_eco/$file" -o "$ECO_DIR/cc_eco/$file"
done

# Create shell wrapper
cat > "$ECO_DIR/cc-eco" <<'WRAPPER'
#!/usr/bin/env bash
PYTHONPATH="$HOME/.claude-ecosystems:$PYTHONPATH" exec python3 -m cc_eco "$@"
WRAPPER
chmod +x "$ECO_DIR/cc-eco"

# Add alias to .zshrc if not present
if ! grep -q "alias cc-eco=" "$HOME/.zshrc" 2>/dev/null; then
  echo "" >> "$HOME/.zshrc"
  echo "# cc-eco: Claude Code ecosystem switcher" >> "$HOME/.zshrc"
  echo "alias cc-eco='$ECO_DIR/cc-eco'" >> "$HOME/.zshrc"
fi

# Add alias to .bashrc if not present
if ! grep -q "alias cc-eco=" "$HOME/.bashrc" 2>/dev/null; then
  echo "" >> "$HOME/.bashrc"
  echo "# cc-eco: Claude Code ecosystem switcher" >> "$HOME/.bashrc"
  echo "alias cc-eco='$ECO_DIR/cc-eco'" >> "$HOME/.bashrc"
fi

# Clean up old v2 script if present
if [[ -f "$ECO_DIR/cc-eco.sh" ]]; then
  rm -f "$ECO_DIR/cc-eco.sh"
  echo "[cc-eco] Removed old v2 script"
fi

echo "[cc-eco] Done! Run 'source ~/.zshrc' or open a new terminal, then:"
echo "  cc-eco init <name>    # Initialize with current state"
echo "  cc-eco -h             # Show help"