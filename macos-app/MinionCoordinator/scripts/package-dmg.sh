#!/usr/bin/env bash
set -euo pipefail

# Package MinionCoordinator as a DMG for distribution
# Usage: ./scripts/package-dmg.sh
# Requires: package-app.sh to have been run first (or runs it automatically)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
APP_NAME="MinionCoordinator"
DMG_NAME="${APP_NAME}.dmg"
BUILD_DIR="${PROJECT_DIR}/build"
DMG_STAGING="${BUILD_DIR}/dmg-staging"
DMG_OUTPUT="${BUILD_DIR}/${DMG_NAME}"

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
die()   { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# Ensure .app exists — build if needed
if [ ! -d "${BUILD_DIR}/${APP_NAME}.app" ]; then
    info "Building app bundle first..."
    "${SCRIPT_DIR}/package-app.sh" || die "Failed to build app bundle"
fi

# Prepare DMG staging area
info "Preparing DMG staging..."
rm -rf "$DMG_STAGING"
mkdir -p "$DMG_STAGING"

# Copy .app to staging
cp -R "${BUILD_DIR}/${APP_NAME}.app" "${DMG_STAGING}/"

# Create Applications symlink for drag-to-install
ln -s /Applications "${DMG_STAGING}/Applications"

# Remove old DMG if exists
rm -f "$DMG_OUTPUT"

# Create DMG
info "Creating DMG..."
hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$DMG_STAGING" \
    -ov \
    -format UDZO \
    "$DMG_OUTPUT" 2>&1 || die "hdiutil create failed"

# Clean up staging
rm -rf "$DMG_STAGING"

# Report
DMG_SIZE=$(du -h "$DMG_OUTPUT" | cut -f1)
ok "Created ${DMG_OUTPUT} (${DMG_SIZE})"
echo ""
echo "  To install:"
echo "    1. Open ${DMG_NAME}"
echo "    2. Drag ${APP_NAME} to Applications"
echo "    3. Launch from Applications or Spotlight"
echo ""
