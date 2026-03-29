import Foundation
import SwiftUI
import Combine

/// Main view model — polls /coordinator/status and publishes state for the UI.
@MainActor
class CoordinatorViewModel: ObservableObject {
    // Connection settings (persisted in UserDefaults)
    @AppStorage("coordinatorURL") var coordinatorURL: String = "https://127.0.0.1:8377"
    @AppStorage("pollIntervalSeconds") var pollIntervalSeconds: Int = 5

    // Published state
    @Published var serverStatus: ServerStatus = .unconfigured
    @Published var lastResponse: CoordinatorStatusResponse?
    @Published var lastError: String?
    @Published var isPolling: Bool = false

    // Token stored separately (Keychain in production, UserDefaults for v1)
    @AppStorage("authToken") var authToken: String = ""

    private let client = CoordinatorClient()
    private var pollTask: Task<Void, Never>?

    init() {
        // Auto-start polling if URL is configured
        if !coordinatorURL.isEmpty {
            startPolling()
        }
    }

    func startPolling() {
        stopPolling()
        isPolling = true
        pollTask = Task { [weak self] in
            while !Task.isCancelled {
                await self?.poll()
                try? await Task.sleep(nanoseconds: UInt64((self?.pollIntervalSeconds ?? 5)) * 1_000_000_000)
            }
        }
    }

    func stopPolling() {
        pollTask?.cancel()
        pollTask = nil
        isPolling = false
    }

    func poll() async {
        guard !coordinatorURL.isEmpty else {
            serverStatus = .unconfigured
            return
        }

        do {
            let response = try await client.fetchStatus(url: coordinatorURL, token: authToken)
            lastResponse = response
            lastError = nil

            // Determine status from response
            if response.alerts.total > 0 && response.alerts.items.contains(where: { $0.severity == "critical" }) {
                serverStatus = .warning
            } else if response.agents.stale > 0 || response.messages.totalUnread > 5 {
                serverStatus = .warning
            } else {
                serverStatus = .running
            }
        } catch {
            lastError = error.localizedDescription
            serverStatus = .unreachable
            lastResponse = nil
        }
    }

    /// Test the connection with current settings.
    func testConnection() async -> Bool {
        do {
            _ = try await client.fetchStatus(url: coordinatorURL, token: authToken)
            return true
        } catch {
            lastError = error.localizedDescription
            return false
        }
    }

    /// Read token from ~/.minion/.api-token if accessible.
    func loadTokenFromFile() {
        let path = NSHomeDirectory() + "/.minion/.api-token"
        if let content = try? String(contentsOfFile: path, encoding: .utf8) {
            authToken = content.trimmingCharacters(in: .whitespacesAndNewlines)
        }
    }

    /// Formatted uptime string.
    var uptimeString: String {
        guard let seconds = lastResponse?.server.uptimeSeconds else { return "—" }
        let hours = seconds / 3600
        let minutes = (seconds % 3600) / 60
        if hours > 0 {
            return "\(hours)h \(minutes)m"
        }
        return "\(minutes)m"
    }
}
