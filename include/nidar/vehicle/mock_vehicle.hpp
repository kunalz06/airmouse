#pragma once

#include <condition_variable>
#include <mutex>
#include <optional>
#include <string_view>

#include "nidar/vehicle/ivehicle.hpp"

namespace nidar::vehicle {

class MockVehicle final : public IVehicle {
public:
  MockVehicle() = default;
  ~MockVehicle() override = default;

  VehicleConnectionResult
  connect(std::string_view endpoint,
          std::chrono::milliseconds discovery_timeout) override;
  void disconnect() noexcept override;

  [[nodiscard]] ConnectionState connection_status() const override;
  [[nodiscard]] std::optional<std::uint8_t> system_id() const override;
  [[nodiscard]] TelemetrySnapshot
  telemetry_snapshot(std::chrono::milliseconds max_age) const override;
  bool wait_for_required_telemetry(std::chrono::milliseconds max_age,
                                   std::chrono::milliseconds timeout) override;

  VehicleCommandResult arm(std::chrono::milliseconds timeout) override;
  VehicleCommandResult disarm(std::chrono::milliseconds timeout) override;
  VehicleCommandResult takeoff(double relative_altitude_m,
                               std::chrono::milliseconds timeout) override;
  VehicleCommandResult land(std::chrono::milliseconds timeout) override;
  VehicleCommandResult hold(std::chrono::milliseconds timeout) override;
  VehicleCommandResult
  start_offboard(std::chrono::milliseconds timeout) override;
  VehicleCommandResult
  stop_offboard(std::chrono::milliseconds timeout) override;
  VehicleCommandResult
  set_position_target(const PositionTargetNed &target,
                      std::chrono::milliseconds timeout) override;
  VehicleCommandResult
  set_velocity_target(const VelocityTargetNed &target,
                      std::chrono::milliseconds timeout) override;

  void set_next_connect_result(VehicleConnectionResult result);
  void set_system_id(std::uint8_t system_id);
  void publish_armed(bool armed, SteadyTimePoint timestamp);
  void publish_flight_mode(FlightMode mode, SteadyTimePoint timestamp);
  void publish_battery(BatteryState battery, SteadyTimePoint timestamp);

private:
  static void invalidate(TelemetrySnapshot &snapshot);
  static void apply_freshness(TelemetrySnapshot &snapshot,
                              std::chrono::milliseconds max_age);

  mutable std::mutex mutex_;
  std::condition_variable condition_;
  ConnectionState state_{ConnectionState::Disconnected};
  VehicleConnectionResult next_connect_result_{
      VehicleConnectionResult::Connected};
  std::optional<std::uint8_t> system_id_{1};
  TelemetrySnapshot snapshot_{};
};

} // namespace nidar::vehicle
