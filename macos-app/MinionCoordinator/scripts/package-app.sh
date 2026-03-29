#!/usr/bin/env bash
set -euo pipefail

# Package MinionCoordinator as a macOS .app bundle
# Usage: ./scripts/package-app.sh [--install]
#   --install: copy to /Applications after packaging

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
APP_NAME="MinionCoordinator"
BUNDLE_ID="com.minion.coordinator"
APP_DIR="${PROJECT_DIR}/build/${APP_NAME}.app"

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
die()   { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# Build release
info "Building release..."
cd "$PROJECT_DIR"
swift build -c release 2>&1 || die "swift build failed"

# Find the binary
BINARY=$(find .build -name "$APP_NAME" -type f -perm +111 | grep release | head -1)
[ -n "$BINARY" ] || die "Release binary not found"
info "Binary: $BINARY"

# Create .app bundle structure
info "Creating ${APP_NAME}.app bundle..."
rm -rf "$APP_DIR"
mkdir -p "${APP_DIR}/Contents/MacOS"
mkdir -p "${APP_DIR}/Contents/Resources"

# Copy binary
cp "$BINARY" "${APP_DIR}/Contents/MacOS/${APP_NAME}"

# Create Info.plist
cat > "${APP_DIR}/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>${APP_NAME}</string>
    <key>CFBundleIdentifier</key>
    <string>${BUNDLE_ID}</string>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST

ok "Created ${APP_DIR}"

# Optional: install to /Applications
if [[ "${1:-}" == "--install" ]]; then
    info "Installing to /Applications..."
    rm -rf "/Applications/${APP_NAME}.app"
    cp -R "$APP_DIR" "/Applications/${APP_NAME}.app"
    ok "Installed to /Applications/${APP_NAME}.app"
    info "Launch: open /Applications/${APP_NAME}.app"
else
    info "To install: cp -R '${APP_DIR}' /Applications/"
    info "Or run: $0 --install"
fi
