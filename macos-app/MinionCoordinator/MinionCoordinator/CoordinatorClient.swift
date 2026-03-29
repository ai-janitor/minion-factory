import Foundation

/// HTTP client for the coordinator API. Handles self-signed TLS certs
/// and Bearer token auth. All calls go to GET /coordinator/status.
class CoordinatorClient: NSObject, URLSessionDelegate {
    private var session: URLSession!

    override init() {
        super.init()
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 10
        self.session = URLSession(configuration: config, delegate: self, delegateQueue: nil)
    }

    /// Fetch the coordinator status snapshot.
    func fetchStatus(url: String, token: String) async throws -> CoordinatorStatusResponse {
        let endpoint = url.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
            + "/coordinator/status"

        guard let requestURL = URL(string: endpoint) else {
            throw CoordinatorError.invalidURL
        }

        var request = URLRequest(url: requestURL)
        request.httpMethod = "GET"
        if !token.isEmpty {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw CoordinatorError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw CoordinatorError.httpError(httpResponse.statusCode)
        }

        let decoder = JSONDecoder()
        return try decoder.decode(CoordinatorStatusResponse.self, from: data)
    }

    // MARK: - URLSessionDelegate — trust self-signed certs

    func urlSession(
        _ session: URLSession,
        didReceive challenge: URLAuthenticationChallenge,
        completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void
    ) {
        if challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
           let serverTrust = challenge.protectionSpace.serverTrust {
            completionHandler(.useCredential, URLCredential(trust: serverTrust))
        } else {
            completionHandler(.performDefaultHandling, nil)
        }
    }
}

enum CoordinatorError: LocalizedError {
    case invalidURL
    case invalidResponse
    case httpError(Int)

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid coordinator URL"
        case .invalidResponse: return "Invalid response from coordinator"
        case .httpError(let code): return "HTTP \(code)"
        }
    }
}
