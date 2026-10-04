#include "nidar/vehicle/mock_vehicle.hpp"

namespace nidar::vehicle {
namespace {

template <typename T>
void mark_stale(TelemetryField<T> &field, SteadyTimePoint now,
                std::chrono::milliseconds max_age) {
  if (field.validity != TelemetryValidity::Valid) {
    return;
  }
  if (max_age <= std::chrono::milliseconds::zero() ||
      field.last_update == SteadyTimePoint{} || field.last_update > now ||
      now - field.last_update > max_age) {
    field.validity = TelemetryValidity::Stale;
  }
}

VehicleCommandResult reject_command() {
  return VehicleCommandResult::RejectedByPhasePolicy;
}

} // namespace

VehicleConnectionResult
MockVehicle::connect(std::string_view endpoint,
                     std::chrono::milliseconds discovery_timeout) {
  std::lock_guard lock(mutex_);
  if (endpoint.empty() ||
      discovery_timeout <= std::chrono::milliseconds::zero()) {
    return VehicleConnectionResult::InvalidArgument;
  }
  if (state_ == ConnectionState::Connected) {
    return VehicleConnectionResult::AlreadyConnected;
  }

  state_ = ConnectionState::Connecting;
  if (next_connect_result_ == VehicleConnectionResult::Connected) {
    state_ = ConnectionState::Connected;
  } else {
    state_ = ConnectionState::Disconnected;
    invalidate(snapshot_);
  }
  condition_.notify_all();
  return next_connect_result_;
}

void MockVehicle::disconnect() noexcept {
  std::lock_guard lock(mutex_);
  state_ = ConnectionState::Disconnected;
  invalidate(snapshot_);
  condition_.notify_all();
}

ConnectionState MockVehicle::connection_status() const {
  std::lock_guard lock(mutex_);
  return state_;
}

std::optional<std::uint8_t> MockVehicle::system_id() const {
  std::lock_guard lock(mutex_);
  return state_ == ConnectionState::Connected ? system_id_ : std::nullopt;
}

TelemetrySnapshot
MockVehicle::telemetry_snapshot(std::chrono::milliseconds max_age) const {
  std::lock_guard lock(mutex_);
  auto copy = snapshot_;
  copy.assembled_at = SteadyClock::now();
  apply_freshness(copy, max_age);
  return copy;
}

bool MockVehicle::wait_for_required_telemetry(
    std::chrono::milliseconds max_age, std::chrono::milliseconds timeout) {
  if (max_age <= std::chrono::milliseconds::zero() ||
      timeout <= std::chrono::milliseconds::zero()) {
    return false;
  }

  std::unique_lock lock(mutex_);
  const auto deadline = SteadyClock::now() + timeout;
  const bool signalled = condition_.wait_until(lock, deadline, [this, max_age] {
    if (state_ != ConnectionState::Connected) {
      return true;
    }
    auto copy = snapshot_;
    copy.assembled_at = SteadyClock::now();
    apply_freshness(copy, max_age);
    return copy.required_fields_fresh(max_age);
  });

  if (!signalled || state_ != ConnectionState::Connected) {
    return false;
  }
  auto copy = snapshot_;
  copy.assembled_at = SteadyClock::now();
  apply_freshness(copy, max_age);
  return copy.required_fields_fresh(max_age);
}

VehicleCommandResult MockVehicle::arm(std::chrono::milliseconds) {
  return reject_command();
}
VehicleCommandResult MockVehicle::disarm(std::chrono::milliseconds) {
  return reject_command();
}
VehicleCommandResult MockVehicle::takeoff(double, std::chrono::milliseconds) {
  return reject_command();
}
VehicleCommandResult MockVehicle::land(std::chrono::milliseconds) {
  return reject_command();
}
VehicleCommandResult MockVehicle::hold(std::chrono::milliseconds) {
  return reject_command();
}
VehicleCommandResult MockVehicle::start_offboard(std::chrono::milliseconds) {
  return reject_command();
}
VehicleCommandResult MockVehicle::stop_offboard(std::chrono::milliseconds) {
  return reject_command();
}
VehicleCommandResult
MockVehicle::set_position_target(const PositionTargetNed &,
                                 std::chrono::milliseconds) {
  return reject_command();
}
VehicleCommandResult
MockVehicle::set_velocity_target(const VelocityTargetNed &,
                                 std::chrono::milliseconds) {
  return reject_command();
}

void MockVehicle::set_next_connect_result(VehicleConnectionResult result) {
  std::lock_guard lock(mutex_);
  next_connect_result_ = result;
}

void MockVehicle::set_system_id(std::uint8_t system_id) {
  std::lock_guard lock(mutex_);
  system_id_ = system_id;
}

void MockVehicle::publish_armed(bool armed, SteadyTimePoint timestamp,
                                TelemetryValidity validity) {
  std::lock_guard lock(mutex_);
  snapshot_.armed = {armed, validity, timestamp};
  condition_.notify_all();
}

void MockVehicle::publish_flight_mode(FlightMode mode,
                                      SteadyTimePoint timestamp,
                                      TelemetryValidity validity) {
  std::lock_guard lock(mutex_);
  snapshot_.flight_mode = {mode, validity, timestamp};
  condition_.notify_all();
}

void MockVehicle::publish_battery(BatteryState battery,
                                  SteadyTimePoint timestamp,
                                  TelemetryValidity validity) {
  std::lock_guard lock(mutex_);
  snapshot_.battery = {battery, validity, timestamp};
  condition_.notify_all();
}

void MockVehicle::invalidate(TelemetrySnapshot &snapshot) {
  snapshot.armed.validity = TelemetryValidity::Unavailable;
  snapshot.flight_mode.validity = TelemetryValidity::Unavailable;
  snapshot.battery.validity = TelemetryValidity::Unavailable;
}

void MockVehicle::apply_freshness(TelemetrySnapshot &snapshot,
                                  std::chrono::milliseconds max_age) {
  mark_stale(snapshot.armed, snapshot.assembled_at, max_age);
  mark_stale(snapshot.flight_mode, snapshot.assembled_at, max_age);
  mark_stale(snapshot.battery, snapshot.assembled_at, max_age);
}

} // namespace nidar::vehicle
