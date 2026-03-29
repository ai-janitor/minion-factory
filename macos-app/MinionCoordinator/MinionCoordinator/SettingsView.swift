import SwiftUI

/// Settings view for configuring the coordinator connection.
struct SettingsView: View {
    @ObservedObject var viewModel: CoordinatorViewModel
    @State private var testResult: String?
    @State private var isTesting = false

    var body: some View {
        Form {
            Section("Connection") {
                TextField("Coordinator URL", text: $viewModel.coordinatorURL)
                    .textFieldStyle(.roundedBorder)
                    .help("e.g., https://192.168.0.31:8377")

                SecureField("Auth Token", text: $viewModel.authToken)
                    .textFieldStyle(.roundedBorder)

                HStack {
                    Button("Load from ~/.minion/.api-token") {
                        viewModel.loadTokenFromFile()
                    }

                    Button("Copy Token") {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString(viewModel.authToken, forType: .string)
                    }
                    .disabled(viewModel.authToken.isEmpty)
                }
            }

            Section("Polling") {
                Picker("Poll Interval", selection: $viewModel.pollIntervalSeconds) {
                    Text("3 seconds").tag(3)
                    Text("5 seconds").tag(5)
                    Text("10 seconds").tag(10)
                    Text("30 seconds").tag(30)
                }

                HStack {
                    if viewModel.isPolling {
                        Button("Stop Polling") { viewModel.stopPolling() }
                    } else {
                        Button("Start Polling") { viewModel.startPolling() }
                    }

                    Spacer()

                    Circle()
                        .fill(viewModel.isPolling ? .green : .gray)
                        .frame(width: 8, height: 8)
                    Text(viewModel.isPolling ? "Polling" : "Stopped")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Section("Test") {
                HStack {
                    Button("Test Connection") {
                        isTesting = true
                        testResult = nil
                        Task {
                            let ok = await viewModel.testConnection()
                            testResult = ok ? "Connected successfully" : "Failed: \(viewModel.lastError ?? "unknown")"
                            isTesting = false
                        }
                    }
                    .disabled(isTesting || viewModel.coordinatorURL.isEmpty)

                    if isTesting {
                        ProgressView()
                            .scaleEffect(0.5)
                    }

                    if let result = testResult {
                        Text(result)
                            .font(.caption)
                            .foregroundStyle(result.starts(with: "Connected") ? .green : .red)
                    }
                }
            }
        }
        .frame(width: 450, height: 350)
        .padding()
    }
}
