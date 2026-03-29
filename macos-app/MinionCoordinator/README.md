# MinionCoordinator — macOS Menu Bar App

Optional macOS client for monitoring the minion coordinator hub. Polls `GET /coordinator/status` and displays server state, channels, agents, messages, and alerts in a menu bar dropdown.

## Requirements

- macOS 12.0+ (Monterey)
- Swift 5.7+ / Xcode 14.2+
- A running minion coordinator (`minion coordinator start`)

## Build

```bash
cd macos-app/MinionCoordinator
swift build -c release
```

## Package as .app

```bash
./scripts/package-app.sh
```

Creates `build/MinionCoordinator.app` — a standard macOS app bundle with `LSUIElement=true` (menu bar only, no Dock icon).

## Package as DMG (for distribution)

```bash
./scripts/package-dmg.sh
```

Creates `build/MinionCoordinator.dmg` — a standard macOS disk image with the app and an Applications shortcut for drag-to-install.

## Install

### From DMG (recommended for sharing)

1. Open `MinionCoordinator.dmg`
2. Drag `MinionCoordinator` to `Applications`
3. Launch from Applications or Spotlight

### Direct install (developer)

```bash
./scripts/package-app.sh --install
```

### Manual

```bash
cp -R build/MinionCoordinator.app /Applications/
```

## Signing & Notarization

**Current status: unsigned, local/internal only.**

The app is not signed or notarized. On first launch, macOS Gatekeeper may block it. To allow:
- Right-click → Open → "Open" in the dialog
- Or: `xattr -d com.apple.quarantine /Applications/MinionCoordinator.app`

Signing and notarization can be added later with an Apple Developer ID. The app works correctly without it for internal/team use.

## Launch

```bash
open /Applications/MinionCoordinator.app
```

Or double-click in Finder.

## First Launch

1. A colored circle appears in the menu bar (gray = not configured)
2. Click the circle → Settings
3. Enter the coordinator URL (e.g., `https://192.168.0.31:8377`)
4. Enter the auth token (or click "Load from ~/.minion/.api-token")
5. Click "Test Connection" to verify
6. Close settings — polling starts automatically

## Menu Bar Icon Colors

| Color | Meaning |
|-------|---------|
| Green | Coordinator running, all healthy |
| Yellow | Warning (stale agents, unread messages, or alerts) |
| Red | Coordinator unreachable |
| Gray | Not configured |

## What It Shows

- **Server**: port, TLS, uptime, coordinator_id, auth state
- **Channels**: name, member count, online count, unread count
- **Agents**: total, online/stale/offline breakdown
- **Messages**: total unread, unread per agent
- **Alerts**: critical/warning items with detail

## Token Storage

The auth token is stored in the macOS Keychain under service `com.minion.coordinator`. It persists across app restarts and is not stored in plain text.

## Settings

Configurable via the Settings window:
- Coordinator URL
- Auth token (Keychain-backed)
- Poll interval (3s / 5s / 10s / 30s)
- Start/stop polling

## Architecture

The app is a pure API client — it talks only to `GET /coordinator/status`. The coordinator daemon is a separate Python process. The app has zero dependency on Python or the minion CLI.

## Verified On

- macOS 12.7 (Monterey), Xcode 14.2, Swift 5.7.2 (trashcan Mac Pro)
- Builds and runs as menu bar app
- Installs to /Applications via package-app.sh
