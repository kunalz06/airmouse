#pragma once

#include <chrono>
#include <cmath>
#include <cstdint>
#include <optional>

namespace nidar::vehicle {

using SteadyClock = std::chrono::steady_clock;
using SteadyTimePoint = SteadyClock::time_point;

enum class ConnectionState {
  Disconnected,
  Connecting,
  Connected,
};

enum class VehicleConnectionResult {
  Connected,
  AlreadyConnected,
  TransportFailure,
  DiscoveryTimeout,
  Cancelled,
  InvalidArgument,
};

enum class VehicleCommandResult {
  RejectedByPhasePolicy,
};

enum class TelemetryValidity {
  Unavailable,
  Valid,
  Stale,
  Invalid,
};

enum class FlightMode {
  Unknown,
  Ready,
  Takeoff,
  Hold,
  Mission,
  ReturnToLaunch,
  Land,
  Offboard,
  FollowMe,
  Manual,
  AltitudeControl,
  PositionControl,
  Acro,
  Stabilized,
  Rattitude,
};

struct BatteryState {
  float voltage_volts{NAN};
  float current_amps{NAN};
  float remaining_percent{NAN};
};

struct PositionTargetNed {
  double north_m{};
  double east_m{};
  double down_m{};
  double yaw_deg{};
};

struct VelocityTargetNed {
  double north_m_s{};
  double east_m_s{};
  double down_m_s{};
  double yaw_deg{};
};

template <typename T> struct TelemetryField {
  T value{};
  TelemetryValidity validity{TelemetryValidity::Unavailable};
  SteadyTimePoint last_update{};
};

struct TelemetrySnapshot {
  SteadyTimePoint assembled_at{};
  TelemetryField<bool> armed{};
  TelemetryField<FlightMode> flight_mode{};
  TelemetryField<BatteryState> battery{};

  [[nodiscard]] bool
  required_fields_fresh(std::chrono::milliseconds max_age) const {
    if (max_age <= std::chrono::milliseconds::zero()) {
      return false;
    }

    const auto fresh = [this, max_age](const auto &field) {
      return field.validity == TelemetryValidity::Valid &&
             field.last_update != SteadyTimePoint{} &&
             field.last_update <= assembled_at &&
             assembled_at - field.last_update <= max_age;
    };

    return fresh(armed) && fresh(flight_mode) && fresh(battery);
  }
};

} // namespace nidar::vehicle
