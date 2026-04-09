#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# claude-spellbook tool installer
# Copies tool configs from the spellbook into your project root.
#
# Usage:
#   bash tools/install.sh node           # Node (prettier, eslint, markdownlint)
#   bash tools/install.sh typescript     # TypeScript (tsconfig, strict eslint)
#   bash tools/install.sh svelte         # SvelteKit (svelte.config, vite, eslint)
#   bash tools/install.sh python         # Python (black, ruff)
#   bash tools/install.sh go             # Go (golangci-lint)
#   bash tools/install.sh rust           # Rust (rustfmt, clippy, toolchain)
#   bash tools/install.sh all            # Everything
#   bash tools/install.sh node --target /path/to/project
# ─────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$SCRIPT_DIR"
TARGET="${PWD}"

LANG="${1:-all}"
shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target|-t) TARGET="$2"; shift 2 ;;
    *) echo "Unknown flag: $1"; exit 1 ;;
  esac
done

echo "Installing [$LANG] tools into: $TARGET"
echo ""

# ── helpers ────────────────────────────────────────────────────
copy() {
  local src="$1" dst="$2"
  cp "$src" "$dst"
  echo "  ✓ $(basename "$dst")"
}

copy_if_missing() {
  local src="$1" dst="$2"
  if [ -f "$dst" ]; then
    echo "  ⚠ $(basename "$dst") already exists — manually merge from:"
    echo "    $src"
  else
    cp "$src" "$dst"
    echo "  ✓ $(basename "$dst")"
  fi
}

# ── language installers ────────────────────────────────────────

install_node() {
  echo "── Node (prettier, eslint, markdownlint) ──"
  copy "$TOOLS_DIR/node/package.json"       "$TARGET/package.json"
  copy "$TOOLS_DIR/node/.prettierrc"        "$TARGET/.prettierrc"
  copy "$TOOLS_DIR/node/.markdownlint.json" "$TARGET/.markdownlint.json"
  copy "$TOOLS_DIR/node/eslint.config.js"   "$TARGET/eslint.config.js"
  echo ""
  echo "  Next: cd $TARGET && npm install"
}

install_typescript() {
  echo "── TypeScript (tsc, prettier, eslint strict) ──"
  copy "$TOOLS_DIR/typescript/package.json"   "$TARGET/package.json"
  copy "$TOOLS_DIR/typescript/tsconfig.json"  "$TARGET/tsconfig.json"
  copy "$TOOLS_DIR/typescript/.prettierrc"    "$TARGET/.prettierrc"
  copy "$TOOLS_DIR/typescript/eslint.config.js" "$TARGET/eslint.config.js"
  echo ""
  echo "  Next: cd $TARGET && npm install"
}

install_svelte() {
  echo "── Svelte (SvelteKit, vite, prettier-plugin-svelte, eslint-plugin-svelte) ──"
  copy "$TOOLS_DIR/svelte/package.json"      "$TARGET/package.json"
  copy "$TOOLS_DIR/svelte/svelte.config.js"  "$TARGET/svelte.config.js"
  copy "$TOOLS_DIR/svelte/vite.config.ts"    "$TARGET/vite.config.ts"
  copy "$TOOLS_DIR/svelte/tsconfig.json"     "$TARGET/tsconfig.json"
  copy "$TOOLS_DIR/svelte/.prettierrc"       "$TARGET/.prettierrc"
  copy "$TOOLS_DIR/svelte/eslint.config.js"  "$TARGET/eslint.config.js"
  echo ""
  echo "  Next: cd $TARGET && npm install && npx svelte-kit sync"
}

install_python() {
  echo "── Python (black, ruff) ──"
  copy         "$TOOLS_DIR/python/requirements-dev.txt" "$TARGET/requirements-dev.txt"
  copy_if_missing "$TOOLS_DIR/python/pyproject.toml"    "$TARGET/pyproject.toml"
  echo ""
  echo "  Next: pip install -r requirements-dev.txt"
}

install_go() {
  echo "── Go (gofmt built-in, golangci-lint) ──"
  copy "$TOOLS_DIR/go/.golangci.yml" "$TARGET/.golangci.yml"
  echo ""
  echo "  gofmt ships with Go — no install needed"
  echo "  golangci-lint: brew install golangci-lint"
}

install_rust() {
  echo "── Rust (rustfmt, clippy, rust-analyzer) ──"
  copy "$TOOLS_DIR/rust/rustfmt.toml"        "$TARGET/rustfmt.toml"
  copy "$TOOLS_DIR/rust/clippy.toml"         "$TARGET/clippy.toml"
  copy "$TOOLS_DIR/rust/rust-toolchain.toml" "$TARGET/rust-toolchain.toml"
  echo ""
  echo "  Next: rustup component add rustfmt clippy rust-analyzer"
}

# ── dispatch ───────────────────────────────────────────────────

case "$LANG" in
  node)       install_node ;;
  typescript) install_typescript ;;
  svelte)     install_svelte ;;
  python)     install_python ;;
  go)         install_go ;;
  rust)       install_rust ;;
  all)
    install_node
    install_typescript
    install_svelte
    install_python
    install_go
    install_rust
    ;;
  *)
    echo "Usage: $0 [node|typescript|svelte|python|go|rust|all] [--target /path]"
    exit 1
    ;;
esac

echo ""
echo "Done. [$LANG] tools installed into: $TARGET"
