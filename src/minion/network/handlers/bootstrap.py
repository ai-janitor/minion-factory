"""Bootstrap endpoints — serve install script and version info from the coordinator.

New machines can install the minion CLI directly from the coordinator without
needing GitHub access or a source checkout.

  curl -sSL https://coordinator:8377/install.sh | bash
  curl -sSL https://coordinator:8377/version

Purpose: Client bootstrap from the coordinator hub.
Rationale: Removes GitHub dependency for new machine onboarding.
Responsibility: Serve install script and version metadata. Read-only, no auth required."""

from __future__ import annotations

import importlib.metadata
import logging
import os

logger = logging.getLogger(__name__)


# The install script is served without auth — same as the dashboard.
# It needs to be accessible to unauthenticated machines that don't have minion yet.
_NO_AUTH_PATHS = {"/install.sh", "/version"}


def register(router) -> None:
    """Register bootstrap endpoints."""
    router.add_get("/install.sh", handle_install_script)
    router.add_get("/version", handle_version)


def handle_version(handler, db_path: str, **kwargs) -> None:
    """GET /version — current minion-factory version and install info.

    Returns version, recommended install method, and coordinator URL
    so clients know what they're connecting to.
    """
    try:
        version = importlib.metadata.version("minion-factory")
    except importlib.metadata.PackageNotFoundError:
        version = "unknown"

    handler._json_response(200, {
        "version": version,
        "package": "minion-factory",
        "install_url": "/install.sh",
    })


def handle_install_script(handler, db_path: str, **kwargs) -> None:
    """GET /install.sh — serve the bootstrap install script.

    The script installs minion-factory via uv/pipx/pip from the coordinator's
    own wheel artifact if available, falling back to GitHub.
    """
    # Try to serve from the repo's scripts/install.sh if running from source
    # Otherwise serve the embedded bootstrap script
    script = _find_install_script()
    if not script:
        script = _embedded_bootstrap_script()

    body = script.encode()
    handler.send_response(200)
    handler.send_header("Content-Type", "text/x-shellscript; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Content-Disposition", "inline; filename=install.sh")
    handler.end_headers()
    handler.wfile.write(body)


def _find_install_script() -> str | None:
    """Look for scripts/install.sh relative to the package installation."""
    # Check common locations
    candidates = [
        # Running from source checkout
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "scripts", "install.sh"),
    ]
    for candidate in candidates:
        path = os.path.normpath(candidate)
        if os.path.isfile(path):
            try:
                with open(path) as f:
                    return f.read()
            except OSError:
                pass
    return None


def _embedded_bootstrap_script() -> str:
    """Fallback bootstrap script when the repo install.sh isn't found."""
    return '''#!/usr/bin/env bash
set -euo pipefail

# minion-factory bootstrap installer
# Served from the coordinator. Installs minion CLI via uv/pipx/pip.

REPO="https://github.com/ai-janitor/minion-factory.git"
TOOL_NAME="minion"

info()  { printf '\\033[1;34m==>\\033[0m %s\\n' "$*"; }
ok()    { printf '\\033[1;32m==>\\033[0m %s\\n' "$*"; }
warn()  { printf '\\033[1;33m==>\\033[0m %s\\n' "$*"; }
die()   { printf '\\033[1;31mERROR:\\033[0m %s\\n' "$*" >&2; exit 1; }

info "Installing ${TOOL_NAME}..."

if command -v uv &>/dev/null; then
    info "Using uv"
    uv tool install "git+${REPO}" --force 2>/dev/null \\
        || uv tool install "git+${REPO}" 2>/dev/null \\
        || die "uv tool install failed."
elif command -v pipx &>/dev/null; then
    info "Using pipx"
    pipx install "git+${REPO}" --force 2>/dev/null \\
        || pipx install "git+${REPO}" 2>/dev/null \\
        || die "pipx install failed."
elif command -v pip &>/dev/null; then
    warn "uv/pipx not found — falling back to pip"
    pip install "git+${REPO}" --user --break-system-packages 2>/dev/null \\
        || pip install "git+${REPO}" --user 2>/dev/null \\
        || pip install "git+${REPO}" 2>/dev/null \\
        || die "pip install failed. Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
else
    die "No Python package manager found. Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

if ! command -v "${TOOL_NAME}" &>/dev/null; then
    warn "${TOOL_NAME} not found on PATH. Add ~/.local/bin to PATH:"
    warn "  export PATH=\\"\\$HOME/.local/bin:\\$PATH\\""
fi

# Deploy contract docs
info "Installing daemon contracts..."
"${TOOL_NAME}" install-docs || warn "install-docs failed — contracts not deployed"

echo ""
ok "${TOOL_NAME} installed!"
echo ""
echo "  Usage:"
echo "    minion team join --agent <name> --class <role>"
echo ""
'''
