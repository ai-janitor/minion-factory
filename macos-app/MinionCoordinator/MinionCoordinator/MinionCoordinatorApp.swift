import SwiftUI
import AppKit
import Combine

/// MinionCoordinator — macOS menu bar app for observing the minion coordinator hub.
/// Uses NSStatusItem for macOS 12+ compatibility.
/// Polls GET /coordinator/status every 5 seconds and displays server state,
/// channels, agents, unread counts, and alerts.
@main
struct MinionCoordinatorApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        Settings {
            SettingsView(viewModel: appDelegate.viewModel)
        }
    }
}

/// App delegate manages the NSStatusItem (menu bar icon) and popover.
class AppDelegate: NSObject, NSApplicationDelegate, NSPopoverDelegate {
    @MainActor let viewModel = CoordinatorViewModel()
    private var statusItem: NSStatusItem!
    private var popover: NSPopover!
    private var cancellables = Set<AnyCancellable>()

    func applicationDidFinishLaunching(_ notification: Notification) {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)

        if let button = statusItem.button {
            button.image = NSImage(systemSymbolName: "circle.fill", accessibilityDescription: "Coordinator Status")
            button.action = #selector(togglePopover)
            button.target = self
        }

        popover = NSPopover()
        popover.contentSize = NSSize(width: 320, height: 480)
        popover.behavior = .transient
        popover.delegate = self

        DispatchQueue.main.async { [self] in
            let hostingView = NSHostingController(rootView: StatusMenuView(viewModel: viewModel))
            popover.contentViewController = hostingView
            updateIcon()

            viewModel.$serverStatus
                .receive(on: RunLoop.main)
                .sink { [weak self] _ in self?.updateIcon() }
                .store(in: &cancellables)
        }
    }

    @objc func togglePopover() {
        if let button = statusItem.button {
            if popover.isShown {
                popover.performClose(nil)
            } else {
                popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
                NSApplication.shared.activate(ignoringOtherApps: true)
            }
        }
    }

    @MainActor
    private func updateIcon() {
        guard let button = statusItem.button else { return }
        let color: NSColor
        switch viewModel.serverStatus {
        case .running: color = .systemGreen
        case .warning: color = .systemYellow
        case .unreachable: color = .systemRed
        case .unconfigured: color = .systemGray
        }

        let config = NSImage.SymbolConfiguration(pointSize: 14, weight: .regular)
        if let image = NSImage(systemSymbolName: "circle.fill", accessibilityDescription: nil)?
            .withSymbolConfiguration(config) {
            let coloredImage = image.tinted(with: color)
            button.image = coloredImage
        }
    }
}

extension NSImage {
    /// Tint an NSImage with a color.
    func tinted(with color: NSColor) -> NSImage {
        let image = self.copy() as! NSImage
        image.lockFocus()
        color.set()
        let rect = NSRect(origin: .zero, size: image.size)
        rect.fill(using: .sourceAtop)
        image.unlockFocus()
        image.isTemplate = false
        return image
    }
}
