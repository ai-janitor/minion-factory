#!/usr/bin/env bash
set -euo pipefail

# minion-factory installer
# Usage: curl -sSL https://raw.githubusercontent.com/ai-janitor/minion-factory/main/scripts/install.sh | bash

# ── Configuration ────────────────────────────────────────────────────────────

REPO="https://github.com/ai-janitor/minion-factory.git"
TOOL_NAME="minion"

# Old packages to remove before installing
OLD_PACKAGES=(minion-comms minion-swarm minion-tasks)

# ── Output helpers ───────────────────────────────────────────────────────────

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m==>\033[0m %s\n' "$*"; }
die()   { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# ── Step 1: Remove old packages ─────────────────────────────────────────────

for pkg in "${OLD_PACKAGES[@]}"; do
    if command -v uv &>/dev/null; then
        uv tool uninstall "$pkg" 2>/dev/null && info "Removed $pkg (uv)" || true
    fi
    if command -v pipx &>/dev/null; then
        pipx uninstall "$pkg" 2>/dev/null && info "Removed $pkg (pipx)" || true
    fi
done

# Remove stale bin stubs from pip installs
for stub in /usr/local/bin/minion-swarm /usr/local/bin/run-minion; do
    if [ -f "$stub" ]; then
        rm -f "$stub" 2>/dev/null && info "Removed stale $stub" \
            || warn "Could not remove $stub — delete manually"
    fi
done

# ── Step 2: Install minion-factory ───────────────────────────────────────────

info "Installing ${TOOL_NAME}..."

if command -v uv &>/dev/null; then
    info "Using uv"
    uv tool install "git+${REPO}" --force 2>/dev/null \
        || uv tool install "git+${REPO}" 2>/dev/null \
        || die "uv tool install failed."
elif command -v pipx &>/dev/null; then
    info "Using pipx"
    pipx install "git+${REPO}" --force 2>/dev/null \
        || pipx install "git+${REPO}" 2>/dev/null \
        || die "pipx install failed."
elif command -v pip &>/dev/null; then
    warn "uv/pipx not found — falling back to pip"
    pip install "git+${REPO}" --user --break-system-packages 2>/dev/null \
        || pip install "git+${REPO}" --user 2>/dev/null \
        || pip install "git+${REPO}" 2>/dev/null \
        || die "pip install failed. Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
else
    die "No Python package manager found. Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

# Verify the command is on PATH
if ! command -v "${TOOL_NAME}" &>/dev/null; then
    warn "${TOOL_NAME} not found on PATH. Add ~/.local/bin to PATH:"
    warn "  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# ── Step 3: Deploy contract docs ────────────────────────────────────────────

info "Installing daemon contracts..."
"${TOOL_NAME}" install-docs \
    || warn "install-docs failed — contracts not deployed"

# ── Done ─────────────────────────────────────────────────────────────────────

echo ""
ok "${TOOL_NAME} installed!"
echo ""
echo "  Contracts:  ~/.minion_work/docs/contracts/"
echo ""
echo "  Usage:"
echo "    minion spawn-party --crew ff1 --project-dir ."
echo ""
