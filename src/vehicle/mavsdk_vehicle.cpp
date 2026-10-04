#include "nidar/vehicle/mavsdk_vehicle.hpp"

#include <algorithm>
#include <atomic>
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

void invalidate(TelemetrySnapshot &snapshot) {
  snapshot.armed.validity = TelemetryValidity::Unavailable;
  snapshot.flight_mode.validity = TelemetryValidity::Unavailable;
  snapshot.battery.validity = TelemetryValidity::Unavailable;
}

void apply_freshness(TelemetrySnapshot &snapshot,
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
  bool cancelled{false};
};

bool is_cancelled(const std::shared_ptr<DiscoverySignal> &signal) {
  std::lock_guard lock(signal->mutex);
  return signal->cancelled;
}

} // namespace

class MavsdkVehicle::Impl {
public:
  struct CallbackState {
    mutable std::mutex mutex;
    std::condition_variable condition;
    bool active{false};
    std::uint64_t generation{0};
    ConnectionState connection{ConnectionState::Disconnected};
    std::optional<std::uint8_t> system_id;
    TelemetrySnapshot snapshot{};
  };

  struct ConnectionBundle {
    std::shared_ptr<mavsdk::Mavsdk> sdk;
    std::shared_ptr<mavsdk::System> system;
    std::unique_ptr<mavsdk::Telemetry> telemetry;
    std::optional<mavsdk::Mavsdk::ConnectionHandle> connection_handle;
    std::optional<mavsdk::System::IsConnectedHandle> is_connected_handle;
    std::optional<mavsdk::Telemetry::ArmedHandle> armed_handle;
    std::optional<mavsdk::Telemetry::FlightModeHandle> flight_mode_handle;
    std::optional<mavsdk::Telemetry::BatteryHandle> battery_handle;
    std::atomic_bool shutdown_started{false};

    void shutdown() noexcept {
      if (shutdown_started.exchange(true)) {
        return;
      }

      if (telemetry) {
        if (armed_handle) {
          telemetry->unsubscribe_armed(*armed_handle);
        }
        if (flight_mode_handle) {
          telemetry->unsubscribe_flight_mode(*flight_mode_handle);
        }
        if (battery_handle) {
          telemetry->unsubscribe_battery(*battery_handle);
        }
      }
      if (system && is_connected_handle) {
        system->unsubscribe_is_connected(*is_connected_handle);
      }
      if (sdk && connection_handle) {
        sdk->remove_connection(*connection_handle);
      }

      armed_handle.reset();
      flight_mode_handle.reset();
      battery_handle.reset();
      is_connected_handle.reset();
      connection_handle.reset();
      telemetry.reset();
      system.reset();
      sdk.reset();
    }

    ~ConnectionBundle() { shutdown(); }
  };

  Impl() : callback_state_(std::make_shared<CallbackState>()) {}
  ~Impl() { disconnect(); }

  VehicleConnectionResult connect(std::string_view endpoint,
                                  std::chrono::milliseconds discovery_timeout) {
    if (endpoint.empty() ||
        discovery_timeout <= std::chrono::milliseconds::zero()) {
      return VehicleConnectionResult::InvalidArgument;
    }

    auto discovery = std::make_shared<DiscoverySignal>();
    std::uint64_t generation{};
    {
      std::lock_guard lifecycle_lock(lifecycle_mutex_);
      if (connecting_ || tearing_down_ || bundle_) {
        return VehicleConnectionResult::AlreadyConnected;
      }

      connecting_ = true;
      discovery_ = discovery;
      std::lock_guard state_lock(callback_state_->mutex);
      generation = ++callback_state_->generation;
      callback_state_->active = false;
      callback_state_->connection = ConnectionState::Connecting;
      callback_state_->system_id.reset();
      invalidate(callback_state_->snapshot);
    }

    if (is_cancelled(discovery)) {
      return finish_failed_connect(discovery, nullptr,
                                   VehicleConnectionResult::Cancelled);
    }

    auto bundle = std::make_shared<ConnectionBundle>();
    auto configuration =
        mavsdk::Mavsdk::Configuration{mavsdk::ComponentType::CompanionComputer};
    bundle->sdk = std::make_shared<mavsdk::Mavsdk>(configuration);

    auto [connection_result, connection_handle] =
        bundle->sdk->add_any_connection_with_handle(
            std::string(endpoint), mavsdk::ForwardingOption::ForwardingOff);
    if (connection_result != mavsdk::ConnectionResult::Success) {
      return finish_failed_connect(
          discovery, bundle,
          is_cancelled(discovery) ? VehicleConnectionResult::Cancelled
                                  : VehicleConnectionResult::TransportFailure);
    }
    bundle->connection_handle = connection_handle;

    std::weak_ptr<DiscoverySignal> weak_discovery = discovery;
    const auto discovery_handle =
        bundle->sdk->subscribe_on_new_system([weak_discovery] {
          if (const auto signal = weak_discovery.lock()) {
            std::lock_guard lock(signal->mutex);
            signal->changed = true;
            signal->condition.notify_all();
          }
        });

    const auto deadline = SteadyClock::now() + discovery_timeout;
    std::shared_ptr<mavsdk::System> selected;

    const auto find_px4 = [&bundle]() -> std::shared_ptr<mavsdk::System> {
      const auto systems = bundle->sdk->systems();
      const auto found =
          std::find_if(systems.begin(), systems.end(), [](const auto &system) {
            return system && system->is_connected() &&
                   system->has_autopilot() &&
                   system->autopilot_type() == mavsdk::Autopilot::Px4;
          });
      return found == systems.end() ? nullptr : *found;
    };

    while (!is_cancelled(discovery) && !(selected = find_px4())) {
      std::unique_lock signal_lock(discovery->mutex);
      const bool signalled =
          discovery->condition.wait_until(signal_lock, deadline, [&discovery] {
            return discovery->changed || discovery->cancelled;
          });
      if (!signalled) {
        break;
      }
      discovery->changed = false;
    }

    bundle->sdk->unsubscribe_on_new_system(discovery_handle);

    if (is_cancelled(discovery)) {
      return finish_failed_connect(discovery, bundle,
                                   VehicleConnectionResult::Cancelled);
    }
    if (!selected) {
      return finish_failed_connect(discovery, bundle,
                                   VehicleConnectionResult::DiscoveryTimeout);
    }

    bundle->system = std::move(selected);
    bundle->telemetry = std::make_unique<mavsdk::Telemetry>(bundle->system);
    subscribe_callbacks(*bundle, generation);

    bool committed = false;
    {
      std::lock_guard lifecycle_lock(lifecycle_mutex_);
      if (discovery_ == discovery && !is_cancelled(discovery)) {
        std::lock_guard state_lock(callback_state_->mutex);
        if (callback_state_->generation == generation &&
            callback_state_->connection == ConnectionState::Connecting) {
          bundle_ = bundle;
          connecting_ = false;
          discovery_.reset();

          callback_state_->active = true;
          callback_state_->connection = ConnectionState::Connected;
          callback_state_->system_id = bundle->system->get_system_id();
          invalidate(callback_state_->snapshot);
          callback_state_->condition.notify_all();
          committed = true;
        }
      }
    }

    if (!committed) {
      return finish_failed_connect(
          discovery, bundle,
          is_cancelled(discovery) ? VehicleConnectionResult::Cancelled
                                  : VehicleConnectionResult::TransportFailure);
    }

    return VehicleConnectionResult::Connected;
  }

  void disconnect() noexcept {
    std::shared_ptr<ConnectionBundle> bundle;
    {
      std::lock_guard lifecycle_lock(lifecycle_mutex_);

      if (discovery_) {
        std::lock_guard discovery_lock(discovery_->mutex);
        discovery_->cancelled = true;
        discovery_->changed = true;
        discovery_->condition.notify_all();
      }

      bundle = std::exchange(bundle_, nullptr);
      tearing_down_ = bundle != nullptr;

      std::lock_guard state_lock(callback_state_->mutex);
      ++callback_state_->generation;
      callback_state_->active = false;
      callback_state_->connection = ConnectionState::Disconnected;
      callback_state_->system_id.reset();
      invalidate(callback_state_->snapshot);
      callback_state_->condition.notify_all();
    }

    if (bundle) {
      bundle->shutdown();
      std::lock_guard lifecycle_lock(lifecycle_mutex_);
      tearing_down_ = false;
    }
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

  [[nodiscard]] TelemetrySnapshot
  telemetry_snapshot(std::chrono::milliseconds max_age) const {
    std::lock_guard lock(callback_state_->mutex);
    auto copy = callback_state_->snapshot;
    copy.assembled_at = SteadyClock::now();
    apply_freshness(copy, max_age);
    return copy;
  }

  bool wait_for_required_telemetry(std::chrono::milliseconds max_age,
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
    std::shared_ptr<mavsdk::Mavsdk> sdk;
    {
      std::lock_guard lifecycle_lock(lifecycle_mutex_);
      if (bundle_) {
        sdk = bundle_->sdk;
      }
    }
    if (sdk) {
      return sdk->version();
    }

    auto configuration =
        mavsdk::Mavsdk::Configuration{mavsdk::ComponentType::CompanionComputer};
    mavsdk::Mavsdk local_sdk{configuration};
    return local_sdk.version();
  }

private:
  VehicleConnectionResult
  finish_failed_connect(const std::shared_ptr<DiscoverySignal> &discovery,
                        const std::shared_ptr<ConnectionBundle> &bundle,
                        VehicleConnectionResult result) {
    bool current = false;
    {
      std::lock_guard lifecycle_lock(lifecycle_mutex_);
      if (discovery_ == discovery) {
        connecting_ = false;
        discovery_.reset();
        tearing_down_ = bundle != nullptr;
        current = true;
      }
    }

    if (current) {
      std::lock_guard state_lock(callback_state_->mutex);
      ++callback_state_->generation;
      callback_state_->active = false;
      callback_state_->connection = ConnectionState::Disconnected;
      callback_state_->system_id.reset();
      invalidate(callback_state_->snapshot);
      callback_state_->condition.notify_all();
    }

    if (bundle) {
      bundle->shutdown();
      if (current) {
        std::lock_guard lifecycle_lock(lifecycle_mutex_);
        tearing_down_ = false;
      }
    }
    return result;
  }

  void subscribe_callbacks(ConnectionBundle &bundle, std::uint64_t generation) {
    const std::weak_ptr<CallbackState> weak_state = callback_state_;

    bundle.is_connected_handle = bundle.system->subscribe_is_connected(
        [weak_state, generation](bool connected) {
          if (connected) {
            return;
          }
          if (const auto state = weak_state.lock()) {
            std::lock_guard lock(state->mutex);
            if (state->generation != generation) {
              return;
            }
            state->connection = ConnectionState::Disconnected;
            state->system_id.reset();
            invalidate(state->snapshot);
            state->condition.notify_all();
          }
        });

    bundle.armed_handle =
        bundle.telemetry->subscribe_armed([weak_state, generation](bool armed) {
          if (const auto state = weak_state.lock()) {
            std::lock_guard lock(state->mutex);
            if (state->generation != generation || !state->active ||
                state->connection != ConnectionState::Connected) {
              return;
            }
            state->snapshot.armed = {armed, TelemetryValidity::Valid,
                                     SteadyClock::now()};
            state->condition.notify_all();
          }
        });

    bundle.flight_mode_handle = bundle.telemetry->subscribe_flight_mode(
        [weak_state, generation](mavsdk::Telemetry::FlightMode mode) {
          if (const auto state = weak_state.lock()) {
            std::lock_guard lock(state->mutex);
            if (state->generation != generation || !state->active ||
                state->connection != ConnectionState::Connected) {
              return;
            }
            state->snapshot.flight_mode = {map_flight_mode(mode),
                                           TelemetryValidity::Valid,
                                           SteadyClock::now()};
            state->condition.notify_all();
          }
        });

    bundle.battery_handle = bundle.telemetry->subscribe_battery(
        [weak_state, generation](mavsdk::Telemetry::Battery battery) {
          if (const auto state = weak_state.lock()) {
            std::lock_guard lock(state->mutex);
            if (state->generation != generation || !state->active ||
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

  mutable std::mutex lifecycle_mutex_;
  bool connecting_{false};
  bool tearing_down_{false};
  std::shared_ptr<DiscoverySignal> discovery_;
  std::shared_ptr<ConnectionBundle> bundle_;
  std::shared_ptr<CallbackState> callback_state_;
};

MavsdkVehicle::MavsdkVehicle() : impl_(std::make_unique<Impl>()) {}
MavsdkVehicle::~MavsdkVehicle() = default;

VehicleConnectionResult
MavsdkVehicle::connect(std::string_view endpoint,
                       std::chrono::milliseconds discovery_timeout) {
  return impl_->connect(endpoint, discovery_timeout);
}

void MavsdkVehicle::disconnect() noexcept { impl_->disconnect(); }

ConnectionState MavsdkVehicle::connection_status() const {
  return impl_->connection_status();
}

std::optional<std::uint8_t> MavsdkVehicle::system_id() const {
  return impl_->system_id();
}

TelemetrySnapshot
MavsdkVehicle::telemetry_snapshot(std::chrono::milliseconds max_age) const {
  return impl_->telemetry_snapshot(max_age);
}

bool MavsdkVehicle::wait_for_required_telemetry(
    std::chrono::milliseconds max_age, std::chrono::milliseconds timeout) {
  return impl_->wait_for_required_telemetry(max_age, timeout);
}

VehicleCommandResult MavsdkVehicle::arm(std::chrono::milliseconds) {
  return reject_command();
}

VehicleCommandResult MavsdkVehicle::disarm(std::chrono::milliseconds) {
  return reject_command();
}

VehicleCommandResult MavsdkVehicle::takeoff(double, std::chrono::milliseconds) {
  return reject_command();
}

VehicleCommandResult MavsdkVehicle::land(std::chrono::milliseconds) {
  return reject_command();
}

VehicleCommandResult MavsdkVehicle::hold(std::chrono::milliseconds) {
  return reject_command();
}

VehicleCommandResult MavsdkVehicle::start_offboard(std::chrono::milliseconds) {
  return reject_command();
}

VehicleCommandResult MavsdkVehicle::stop_offboard(std::chrono::milliseconds) {
  return reject_command();
}

VehicleCommandResult
MavsdkVehicle::set_position_target(const PositionTargetNed &,
                                   std::chrono::milliseconds) {
  return reject_command();
}

VehicleCommandResult
MavsdkVehicle::set_velocity_target(const VelocityTargetNed &,
                                   std::chrono::milliseconds) {
  return reject_command();
}

std::string MavsdkVehicle::mavsdk_version() const { return impl_->version(); }

} // namespace nidar::vehicle
