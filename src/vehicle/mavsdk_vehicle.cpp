#include "nidar/vehicle/mavsdk_vehicle.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <utility>

#include <mavsdk/autopilot.h>
#include <mavsdk/connection_result.h>
#include <mavsdk/mavsdk.h>
#include <mavsdk/plugins/telemetry/telemetry.h>
#include <mavsdk/system.h>

namespace nidar::vehicle {
namespace {

template <typename T>
void mark_stale(
    TelemetryField<T>& field,
    SteadyTimePoint now,
    std::chrono::milliseconds max_age) {
  if (field.validity != TelemetryValidity::Valid) {
    return;
  }
  if (max_age <= std::chrono::milliseconds::zero() ||
      field.last_update == SteadyTimePoint{} ||
      field.last_update > now ||
      now - field.last_update > max_age) {
    field.validity = TelemetryValidity::Stale;
  }
}

void invalidate(TelemetrySnapshot& snapshot) {
  snapshot.armed.validity = TelemetryValidity::Unavailable;
  snapshot.flight_mode.validity = TelemetryValidity::Unavailable;
  snapshot.battery.validity = TelemetryValidity::Unavailable;
}

void apply_freshness(
    TelemetrySnapshot& snapshot,
    std::chrono::milliseconds max_age) {
  mark_stale(snapshot.armed, snapshot.assembled_at, max_age);
  mark_stale(snapshot.flight_mode, snapshot.assembled_at, max_age);
  mark_stale(snapshot.battery, snapshot.assembled_at, max_age);
}

FlightMode map_flight_mode(mavsdk::Telemetry::FlightMode mode) {
  switch (mode) {
    case mavsdk::Telemetry::FlightMode::Ready:
      return FlightMode::Ready;
    case mavsdk::Telemetry::FlightMode::Takeoff:
      return FlightMode::Takeoff;
    case mavsdk::Telemetry::FlightMode::Hold:
      return FlightMode::Hold;
    case mavsdk::Telemetry::FlightMode::Mission:
      return FlightMode::Mission;
    case mavsdk::Telemetry::FlightMode::ReturnToLaunch:
      return FlightMode::ReturnToLaunch;
    case mavsdk::Telemetry::FlightMode::Land:
      return FlightMode::Land;
    case mavsdk::Telemetry::FlightMode::Offboard:
      return FlightMode::Offboard;
    case mavsdk::Telemetry::FlightMode::FollowMe:
      return FlightMode::FollowMe;
    case mavsdk::Telemetry::FlightMode::Manual:
      return FlightMode::Manual;
    case mavsdk::Telemetry::FlightMode::Altctl:
      return FlightMode::AltitudeControl;
    case mavsdk::Telemetry::FlightMode::Posctl:
      return FlightMode::PositionControl;
    case mavsdk::Telemetry::FlightMode::Acro:
      return FlightMode::Acro;
    case mavsdk::Telemetry::FlightMode::Stabilized:
      return FlightMode::Stabilized;
    case mavsdk::Telemetry::FlightMode::Rattitude:
      return FlightMode::Rattitude;
    case mavsdk::Telemetry::FlightMode::Unknown:
    default:
      return FlightMode::Unknown;
  }
}

VehicleCommandResult reject_command() {
  return VehicleCommandResult::RejectedByPhasePolicy;
}

struct DiscoverySignal {
  std::mutex mutex;
  std::condition_variable condition;
  bool changed{false};
  bool active{true};
};

}  // namespace

class MavsdkVehicle::Impl {
 public:
  struct CallbackState {
    mutable std::mutex mutex;
    std::condition_variable condition;
    bool active{false};
    ConnectionState connection{ConnectionState::Disconnected};
    std::optional<std::uint8_t> system_id;
    TelemetrySnapshot snapshot{};
  };

  Impl() : callback_state_(std::make_shared<CallbackState>()) {}
  ~Impl() { disconnect(); }

  VehicleConnectionResult connect(
      std::string_view endpoint,
      std::chrono::milliseconds discovery_timeout) {
    if (endpoint.empty() ||
        discovery_timeout <= std::chrono::milliseconds::zero()) {
      return VehicleConnectionResult::InvalidArgument;
    }

    std::lock_guard lifecycle_lock(lifecycle_mutex_);
    if (sdk_) {
      return VehicleConnectionResult::AlreadyConnected;
    }

    {
      std::lock_guard state_lock(callback_state_->mutex);
      callback_state_->active = false;
      callback_state_->connection = ConnectionState::Connecting;
      callback_state_->system_id.reset();
      invalidate(callback_state_->snapshot);
    }

    auto configuration =
        mavsdk::Mavsdk::Configuration{mavsdk::ComponentType::CompanionComputer};
    sdk_ = std::make_unique<mavsdk::Mavsdk>(configuration);

    auto [connection_result, connection_handle] =
        sdk_->add_any_connection_with_handle(
            std::string(endpoint), mavsdk::ForwardingOption::ForwardingOff);
    if (connection_result != mavsdk::ConnectionResult::Success) {
      reset_failed_connection();
      return VehicleConnectionResult::TransportFailure;
    }
    connection_handle_ = connection_handle;

    auto discovery = std::make_shared<DiscoverySignal>();
    std::weak_ptr<DiscoverySignal> weak_discovery = discovery;
    const auto discovery_handle = sdk_->subscribe_on_new_system([weak_discovery] {
      if (const auto signal = weak_discovery.lock()) {
        std::lock_guard lock(signal->mutex);
        if (signal->active) {
          signal->changed = true;
          signal->condition.notify_all();
        }
      }
    });

    const auto deadline = SteadyClock::now() + discovery_timeout;
    std::shared_ptr<mavsdk::System> selected;
    auto find_px4 = [this]() -> std::shared_ptr<mavsdk::System> {
      const auto systems = sdk_->systems();
      const auto found = std::find_if(
          systems.begin(), systems.end(), [](const auto& system) {
            return system && system->is_connected() &&
                   system->has_autopilot() &&
                   system->autopilot_type() == mavsdk::Autopilot::Px4;
          });
      return found == systems.end() ? nullptr : *found;
    };

    while (!(selected = find_px4())) {
      std::unique_lock signal_lock(discovery->mutex);
      if (discovery->condition.wait_until(
              signal_lock, deadline, [discovery] { return discovery->changed; })) {
        discovery->changed = false;
        continue;
      }
      break;
    }

    {
      std::lock_guard signal_lock(discovery->mutex);
      discovery->active = false;
    }
    sdk_->unsubscribe_on_new_system(discovery_handle);

    if (!selected) {
      remove_connection_only();
      reset_failed_connection();
      return VehicleConnectionResult::DiscoveryTimeout;
    }

    system_ = std::move(selected);
    telemetry_ = std::make_unique<mavsdk::Telemetry>(system_);

    {
      std::lock_guard state_lock(callback_state_->mutex);
      callback_state_->active = true;
      callback_state_->connection = ConnectionState::Connected;
      callback_state_->system_id = system_->get_system_id();
      invalidate(callback_state_->snapshot);
      callback_state_->condition.notify_all();
    }

    subscribe_callbacks();
    return VehicleConnectionResult::Connected;
  }

  void disconnect() noexcept {
    std::lock_guard lifecycle_lock(lifecycle_mutex_);
    {
      std::lock_guard state_lock(callback_state_->mutex);
      callback_state_->active = false;
      callback_state_->connection = ConnectionState::Disconnected;
      callback_state_->system_id.reset();
      invalidate(callback_state_->snapshot);
      callback_state_->condition.notify_all();
    }

    unsubscribe_callbacks();
    remove_connection_only();
    telemetry_.reset();
    system_.reset();
    sdk_.reset();
  }

  [[nodiscard]] ConnectionState connection_status() const {
    std::lock_guard lock(callback_state_->mutex);
    return callback_state_->connection;
  }

  [[nodiscard]] std::optional<std::uint8_t> system_id() const {
    std::lock_guard lock(callback_state_->mutex);
    return callback_state_->connection == ConnectionState::Connected
               ? callback_state_->system_id
               : std::nullopt;
  }

  [[nodiscard]] TelemetrySnapshot telemetry_snapshot(
      std::chrono::milliseconds max_age) const {
    std::lock_guard lock(callback_state_->mutex);
    auto copy = callback_state_->snapshot;
    copy.assembled_at = SteadyClock::now();
    apply_freshness(copy, max_age);
    return copy;
  }

  bool wait_for_required_telemetry(
      std::chrono::milliseconds max_age,
      std::chrono::milliseconds timeout) {
    if (max_age <= std::chrono::milliseconds::zero() ||
        timeout <= std::chrono::milliseconds::zero()) {
      return false;
    }

    std::unique_lock lock(callback_state_->mutex);
    const auto deadline = SteadyClock::now() + timeout;
    const auto predicate = [this, max_age] {
      if (callback_state_->connection != ConnectionState::Connected) {
        return true;
      }
      auto copy = callback_state_->snapshot;
      copy.assembled_at = SteadyClock::now();
      apply_freshness(copy, max_age);
      return copy.required_fields_fresh(max_age);
    };

    const bool signalled =
        callback_state_->condition.wait_until(lock, deadline, predicate);
    if (!signalled ||
        callback_state_->connection != ConnectionState::Connected) {
      return false;
    }

    auto copy = callback_state_->snapshot;
    copy.assembled_at = SteadyClock::now();
    apply_freshness(copy, max_age);
    return copy.required_fields_fresh(max_age);
  }

  [[nodiscard]] std::string version() const {
    std::lock_guard lifecycle_lock(lifecycle_mutex_);
    if (sdk_) {
      return sdk_->version();
    }
    auto configuration =
        mavsdk::Mavsdk::Configuration{mavsdk::ComponentType::CompanionComputer};
    mavsdk::Mavsdk sdk{configuration};
    return sdk.version();
  }

 private:
  void subscribe_callbacks() {
    const std::weak_ptr<CallbackState> weak_state = callback_state_;

    is_connected_handle_ = system_->subscribe_is_connected(
        [weak_state](bool connected) {
          if (connected) {
            return;
          }
          if (const auto state = weak_state.lock()) {
            std::lock_guard lock(state->mutex);
            if (!state->active) {
              return;
            }
            state->connection = ConnectionState::Disconnected;
            state->system_id.reset();
            invalidate(state->snapshot);
            state->condition.notify_all();
          }
        });

    armed_handle_ = telemetry_->subscribe_armed([weak_state](bool armed) {
      if (const auto state = weak_state.lock()) {
        std::lock_guard lock(state->mutex);
        if (!state->active ||
            state->connection != ConnectionState::Connected) {
          return;
        }
        state->snapshot.armed = {
            armed, TelemetryValidity::Valid, SteadyClock::now()};
        state->condition.notify_all();
      }
    });

    flight_mode_handle_ = telemetry_->subscribe_flight_mode(
        [weak_state](mavsdk::Telemetry::FlightMode mode) {
          if (const auto state = weak_state.lock()) {
            std::lock_guard lock(state->mutex);
            if (!state->active ||
                state->connection != ConnectionState::Connected) {
              return;
            }
            state->snapshot.flight_mode = {
                map_flight_mode(mode),
                TelemetryValidity::Valid,
                SteadyClock::now()};
            state->condition.notify_all();
          }
        });

    battery_handle_ = telemetry_->subscribe_battery(
        [weak_state](mavsdk::Telemetry::Battery battery) {
          if (const auto state = weak_state.lock()) {
            std::lock_guard lock(state->mutex);
            if (!state->active ||
                state->connection != ConnectionState::Connected) {
              return;
            }
            const bool valid_voltage =
                std::isfinite(battery.voltage_v) && battery.voltage_v > 0.0F;
            state->snapshot.battery = {
                BatteryState{
                    .voltage_volts = battery.voltage_v,
                    .current_amps = battery.current_battery_a,
                    .remaining_percent = battery.remaining_percent,
                },
                valid_voltage ? TelemetryValidity::Valid
                              : TelemetryValidity::Invalid,
                SteadyClock::now()};
            state->condition.notify_all();
          }
        });
  }

  void unsubscribe_callbacks() noexcept {
    if (telemetry_) {
      if (armed_handle_) {
        telemetry_->unsubscribe_armed(*armed_handle_);
      }
      if (flight_mode_handle_) {
        telemetry_->unsubscribe_flight_mode(*flight_mode_handle_);
      }
      if (battery_handle_) {
        telemetry_->unsubscribe_battery(*battery_handle_);
      }
    }
    if (system_ && is_connected_handle_) {
      system_->unsubscribe_is_connected(*is_connected_handle_);
    }

    armed_handle_.reset();
    flight_mode_handle_.reset();
    battery_handle_.reset();
    is_connected_handle_.reset();
  }

  void remove_connection_only() noexcept {
    if (sdk_ && connection_handle_) {
      sdk_->remove_connection(*connection_handle_);
    }
    connection_handle_.reset();
  }

  void reset_failed_connection() noexcept {
    telemetry_.reset();
    system_.reset();
    sdk_.reset();
    std::lock_guard state_lock(callback_state_->mutex);
    callback_state_->active = false;
    callback_state_->connection = ConnectionState::Disconnected;
    callback_state_->system_id.reset();
    invalidate(callback_state_->snapshot);
    callback_state_->condition.notify_all();
  }

  mutable std::mutex lifecycle_mutex_;
  std::unique_ptr<mavsdk::Mavsdk> sdk_;
  std::shared_ptr<mavsdk::System> system_;
  std::unique_ptr<mavsdk::Telemetry> telemetry_;
  std::optional<mavsdk::Mavsdk::ConnectionHandle> connection_handle_;
  std::optional<mavsdk::System::IsConnectedHandle> is_connected_handle_;
  std::optional<mavsdk::Telemetry::ArmedHandle> armed_handle_;
  std::optional<mavsdk::Telemetry::FlightModeHandle> flight_mode_handle_;
  std::optional<mavsdk::Telemetry::BatteryHandle> battery_handle_;
  std::shared_ptr<CallbackState> callback_state_;
};

MavsdkVehicle::MavsdkVehicle() : impl_(std::make_unique<Impl>()) {}
MavsdkVehicle::~MavsdkVehicle() = default;

VehicleConnectionResult MavsdkVehicle::connect(
    std::string_view endpoint,
    std::chrono::milliseconds discovery_timeout) {
  return impl_->connect(endpoint, discovery_timeout);
}
void MavsdkVehicle::disconnect() noexcept { impl_->disconnect(); }
ConnectionState MavsdkVehicle::connection_status() const { return impl_->connection_status(); }
std::optional<std::uint8_t> MavsdkVehicle::system_id() const { return impl_->system_id(); }
TelemetrySnapshot MavsdkVehicle::telemetry_snapshot(std::chrono::milliseconds max_age) const {
  return impl_->telemetry_snapshot(max_age);
}
bool MavsdkVehicle::wait_for_required_telemetry(
    std::chrono::milliseconds max_age,
    std::chrono::milliseconds timeout) {
  return impl_->wait_for_required_telemetry(max_age, timeout);
}
VehicleCommandResult MavsdkVehicle::arm(std::chrono::milliseconds) { return reject_command(); }
VehicleCommandResult MavsdkVehicle::disarm(std::chrono::milliseconds) { return reject_command(); }
VehicleCommandResult MavsdkVehicle::takeoff(double, std::chrono::milliseconds) { return reject_command(); }
VehicleCommandResult MavsdkVehicle::land(std::chrono::milliseconds) { return reject_command(); }
VehicleCommandResult MavsdkVehicle::hold(std::chrono::milliseconds) { return reject_command(); }
VehicleCommandResult MavsdkVehicle::start_offboard(std::chrono::milliseconds) { return reject_command(); }
VehicleCommandResult MavsdkVehicle::stop_offboard(std::chrono::milliseconds) { return reject_command(); }
VehicleCommandResult MavsdkVehicle::set_position_target(const PositionTargetNed&, std::chrono::milliseconds) {
  return reject_command();
}
VehicleCommandResult MavsdkVehicle::set_velocity_target(const VelocityTargetNed&, std::chrono::milliseconds) {
  return reject_command();
}
std::string MavsdkVehicle::mavsdk_version() const { return impl_->version(); }

}  // namespace nidar::vehicle
