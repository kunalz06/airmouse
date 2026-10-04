#pragma once

#include <memory>
#include <string>

#include "nidar/vehicle/ivehicle.hpp"

namespace nidar::vehicle {

class MavsdkVehicle final : public IVehicle {
public:
  MavsdkVehicle();
  ~MavsdkVehicle() override;

  MavsdkVehicle(const MavsdkVehicle &) = delete;
  MavsdkVehicle &operator=(const MavsdkVehicle &) = delete;
  MavsdkVehicle(MavsdkVehicle &&) = delete;
  MavsdkVehicle &operator=(MavsdkVehicle &&) = delete;

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

  [[nodiscard]] std::string mavsdk_version() const;

private:
  class Impl;
  std::unique_ptr<Impl> impl_;
};

} // namespace nidar::vehicle
