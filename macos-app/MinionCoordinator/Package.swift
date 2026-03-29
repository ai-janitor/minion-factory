// swift-tools-version: 5.7
import PackageDescription

let package = Package(
    name: "MinionCoordinator",
    platforms: [.macOS(.v12)],
    targets: [
        .executableTarget(
            name: "MinionCoordinator",
            path: "MinionCoordinator"
        ),
    ]
)
