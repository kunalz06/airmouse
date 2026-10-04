#pragma once

#include <chrono>
#include <cstdint>
#include <optional>
#include <string_view>

#include "nidar/vehicle/vehicle_types.hpp"

namespace nidar::vehicle {

class IVehicle {
public:
  virtual ~IVehicle() = default;

  virtual VehicleConnectionResult
  connect(std::string_view endpoint,
          std::chrono::milliseconds discovery_timeout) = 0;
  virtual void disconnect() noexcept = 0;

  [[nodiscard]] virtual ConnectionState connection_status() const = 0;
  [[nodiscard]] virtual std::optional<std::uint8_t> system_id() const = 0;
  [[nodiscard]] virtual TelemetrySnapshot
  telemetry_snapshot(std::chrono::milliseconds max_age) const = 0;
  virtual bool
  wait_for_required_telemetry(std::chrono::milliseconds max_age,
                              std::chrono::milliseconds timeout) = 0;

  virtual VehicleCommandResult arm(std::chrono::milliseconds timeout) = 0;
  virtual VehicleCommandResult disarm(std::chrono::milliseconds timeout) = 0;
  virtual VehicleCommandResult takeoff(double relative_altitude_m,
                                       std::chrono::milliseconds timeout) = 0;
  virtual VehicleCommandResult land(std::chrono::milliseconds timeout) = 0;
  virtual VehicleCommandResult hold(std::chrono::milliseconds timeout) = 0;
  virtual VehicleCommandResult
  start_offboard(std::chrono::milliseconds timeout) = 0;
  virtual VehicleCommandResult
  stop_offboard(std::chrono::milliseconds timeout) = 0;
  virtual VehicleCommandResult
  set_position_target(const PositionTargetNed &target,
                      std::chrono::milliseconds timeout) = 0;
  virtual VehicleCommandResult
  set_velocity_target(const VelocityTargetNed &target,
                      std::chrono::milliseconds timeout) = 0;
};

} // namespace nidar::vehicle
