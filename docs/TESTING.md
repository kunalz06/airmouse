# Testing

Unit tests cover state transitions, configuration, health, timeouts, frames, and navigation constraints. Integration tests cover vehicle/sensor adapters and configuration. SITL validates flight-affecting behavior; fault injection covers MAVLink/offboard loss, stale telemetry, unhealthy estimation, invalid local position, sensors, timeout, crash, corrupt config, and rejection.

Phase 4B Gate B preparation adds a digest-pinned actionlint job to `build-test` and checks the exact PR head or push SHA in the workflow lint, amd64, SITL, and ARM64 jobs. Local validation covers all workflow files with the pinned actionlint container and the release workflow's focused Python tests. Hosted PR checks must still pass on the exact PR head; after an approved merge, all three build jobs must pass again on the exact main SHA. The manual GHCR bootstrap workflow is outside PR checks and does not publish a runtime image.
