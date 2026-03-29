import SwiftUI

/// Main menu bar dropdown view — shows coordinator status at a glance.
struct StatusMenuView: View {
    @ObservedObject var viewModel: CoordinatorViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Header
            HStack {
                Text("Minion Coordinator")
                    .font(.headline)
                Spacer()
                statusBadge
            }
            .padding(.bottom, 4)

            Divider()

            if let response = viewModel.lastResponse {
                serverSection(response.server, auth: response.auth)
                Divider()
                channelsSection(response.channels)
                Divider()
                agentsSection(response.agents)
                Divider()
                messagesSection(response.messages)

                if response.alerts.total > 0 {
                    Divider()
                    alertsSection(response.alerts)
                }
            } else if let error = viewModel.lastError {
                Label(error, systemImage: "exclamationmark.triangle")
                    .foregroundStyle(.red)
                    .font(.caption)
            } else {
                Text("Connecting...")
                    .foregroundStyle(.secondary)
            }

            Divider()

            // Actions
            Button("Open Dashboard...") {
                if let url = URL(string: viewModel.coordinatorURL) {
                    NSWorkspace.shared.open(url)
                }
            }

            Button("Refresh") {
                Task { await viewModel.poll() }
            }
            .keyboardShortcut("r")

            Button("Settings...") {
                NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)
            }

            Divider()

            Button("Quit") {
                NSApplication.shared.terminate(nil)
            }
            .keyboardShortcut("q")
        }
        .padding(12)
        .frame(width: 320)
    }

    // MARK: - Status badge

    private var statusBadge: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(statusColor)
                .frame(width: 8, height: 8)
            Text(statusText)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }

    private var statusColor: Color {
        switch viewModel.serverStatus {
        case .running: return .green
        case .warning: return .yellow
        case .unreachable: return .red
        case .unconfigured: return .gray
        }
    }

    private var statusText: String {
        switch viewModel.serverStatus {
        case .running: return "Running"
        case .warning: return "Warning"
        case .unreachable: return "Unreachable"
        case .unconfigured: return "Not Configured"
        }
    }

    // MARK: - Server section

    private func serverSection(_ server: ServerInfo, auth: AuthInfo) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Label("Server", systemImage: "server.rack")
                .font(.subheadline.bold())

            HStack {
                Text("Port \(server.port)")
                if server.tls { Text("TLS").foregroundStyle(.green) }
                Spacer()
                Text("Up \(viewModel.uptimeString)")
                    .foregroundStyle(.secondary)
            }
            .font(.caption)

            HStack {
                Text("Auth: \(auth.enabled ? "Enabled" : "Disabled")")
                if let cid = server.coordinatorId {
                    Spacer()
                    Text("ID: \(cid)")
                }
            }
            .font(.caption)
            .foregroundStyle(.secondary)
        }
    }

    // MARK: - Channels section

    private func channelsSection(_ channels: ChannelSummary) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Label("Channels (\(channels.count))", systemImage: "number")
                .font(.subheadline.bold())

            ForEach(channels.items) { channel in
                HStack {
                    Text("#\(channel.name)")
                        .font(.caption.monospaced())
                    Spacer()
                    Text("\(channel.onlineCount)/\(channel.memberCount) online")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    if channel.totalUnread > 0 {
                        Text("\(channel.totalUnread)")
                            .font(.caption2.bold())
                            .padding(.horizontal, 5)
                            .padding(.vertical, 1)
                            .background(.red)
                            .foregroundStyle(.white)
                            .clipShape(Capsule())
                    }
                }
            }
        }
    }

    // MARK: - Agents section

    private func agentsSection(_ agents: AgentSummary) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Label("Agents (\(agents.total))", systemImage: "person.3")
                .font(.subheadline.bold())

            HStack(spacing: 12) {
                agentCount(agents.online, label: "Online", color: .green)
                agentCount(agents.stale, label: "Stale", color: .yellow)
                agentCount(agents.offline, label: "Offline", color: .red)
            }
            .font(.caption)
        }
    }

    private func agentCount(_ count: Int, label: String, color: Color) -> some View {
        HStack(spacing: 3) {
            Circle().fill(color).frame(width: 6, height: 6)
            Text("\(count) \(label)")
        }
    }

    // MARK: - Messages section

    private func messagesSection(_ messages: MessageSummary) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Label("Messages", systemImage: "envelope")
                .font(.subheadline.bold())

            if messages.totalUnread == 0 {
                Text("No unread messages")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                Text("\(messages.totalUnread) unread")
                    .font(.caption)

                ForEach(Array(messages.unreadByAgent.sorted(by: { $0.key < $1.key })), id: \.key) { agent, count in
                    HStack {
                        Text(agent)
                            .font(.caption.monospaced())
                        Spacer()
                        Text("\(count)")
                            .font(.caption.bold())
                    }
                }
            }
        }
    }

    // MARK: - Alerts section

    private func alertsSection(_ alerts: AlertSummary) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Label("Alerts (\(alerts.total))", systemImage: "exclamationmark.triangle")
                .font(.subheadline.bold())
                .foregroundStyle(alerts.items.contains(where: { $0.severity == "critical" }) ? .red : .yellow)

            ForEach(alerts.items) { alert in
                HStack {
                    Image(systemName: alert.severity == "critical" ? "xmark.circle.fill" : "exclamationmark.triangle.fill")
                        .foregroundStyle(alert.severity == "critical" ? .red : .yellow)
                        .font(.caption)
                    Text(alertDescription(alert))
                        .font(.caption)
                    Spacer()
                }
            }
        }
    }

    private func alertDescription(_ alert: AlertItem) -> String {
        switch alert.type {
        case "hp_critical":
            return "\(alert.agent ?? "?") at \(alert.hpPct ?? 0)% HP"
        case "stalled_requirement":
            return "\(alert.project): stalled requirement"
        case "unread_messages":
            return "\(alert.agent ?? "?") has unread messages"
        default:
            return "\(alert.type) in \(alert.project)"
        }
    }
}
