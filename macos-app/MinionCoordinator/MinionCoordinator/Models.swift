import Foundation

// MARK: - Server status enum for menu bar icon

enum ServerStatus {
    case running    // green — all healthy
    case warning    // yellow — stale agents or unread messages
    case unreachable // red — can't reach coordinator
    case unconfigured // gray — no URL configured
}

// MARK: - Codable structs matching GET /coordinator/status (schema_version=2)

struct CoordinatorStatusResponse: Codable {
    let schemaVersion: Int
    let timestamp: String
    let server: ServerInfo
    let auth: AuthInfo
    let agents: AgentSummary
    let agentsList: [AgentEntry]
    let messages: MessageSummary
    let alerts: AlertSummary
    let channels: ChannelSummary
    let projects: ProjectSummary

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case timestamp, server, auth, agents
        case agentsList = "agents_list"
        case messages, alerts, channels, projects
    }
}

struct ServerInfo: Codable {
    let status: String
    let coordinatorId: String?
    let uptimeSeconds: Int
    let port: Int
    let tls: Bool
    let startedAt: String

    enum CodingKeys: String, CodingKey {
        case status
        case coordinatorId = "coordinator_id"
        case uptimeSeconds = "uptime_seconds"
        case port, tls
        case startedAt = "started_at"
    }
}

struct AuthInfo: Codable {
    let enabled: Bool
    let tokenPath: String?

    enum CodingKeys: String, CodingKey {
        case enabled
        case tokenPath = "token_path"
    }
}

struct AgentSummary: Codable {
    let total: Int
    let online: Int
    let stale: Int
    let offline: Int
    let byClass: [String: Int]

    enum CodingKeys: String, CodingKey {
        case total, online, stale, offline
        case byClass = "by_class"
    }
}

struct AgentEntry: Codable, Identifiable {
    let name: String
    let agentClass: String
    let machine: String
    let model: String?
    let presence: String

    var id: String { "\(machine)/\(name)" }

    enum CodingKeys: String, CodingKey {
        case name
        case agentClass = "class"
        case machine, model, presence
    }
}

struct MessageSummary: Codable {
    let totalUnread: Int
    let unreadByAgent: [String: Int]

    enum CodingKeys: String, CodingKey {
        case totalUnread = "total_unread"
        case unreadByAgent = "unread_by_agent"
    }
}

struct AlertSummary: Codable {
    let total: Int
    let items: [AlertItem]
}

struct AlertItem: Codable, Identifiable {
    let type: String
    let severity: String
    let project: String
    let agent: String?
    let hpPct: Int?

    var id: String { "\(type)-\(project)-\(agent ?? "")" }

    enum CodingKeys: String, CodingKey {
        case type, severity, project, agent
        case hpPct = "hp_pct"
    }
}

struct ChannelSummary: Codable {
    let count: Int
    let items: [ChannelEntry]
}

struct ChannelEntry: Codable, Identifiable {
    let name: String
    let memberCount: Int
    let onlineCount: Int
    let totalUnread: Int
    let members: [String]

    var id: String { name }

    enum CodingKeys: String, CodingKey {
        case name
        case memberCount = "member_count"
        case onlineCount = "online_count"
        case totalUnread = "total_unread"
        case members
    }
}

struct ProjectSummary: Codable {
    let count: Int
    let names: [String]
    let summaries: [ProjectDetail]?
}

struct ProjectDetail: Codable, Identifiable {
    let name: String
    let tasks: [String: Int]?
    let backlog: [String: Int]?
    let requirements: [String: Int]?

    var id: String { name }
}
