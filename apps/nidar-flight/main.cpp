#include <charconv>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <optional>
#include <string>
#include <string_view>

#include "nidar/vehicle/mavsdk_vehicle.hpp"

namespace {
using namespace std::chrono_literals;
using nidar::vehicle::MavsdkVehicle;
using nidar::vehicle::VehicleConnectionResult;

struct Options {
  bool sim{false};
  std::string endpoint;
  std::chrono::milliseconds discovery_timeout{15000ms};
  std::chrono::milliseconds telemetry_max_age{1000ms};
  std::chrono::milliseconds telemetry_wait{10000ms};
};

void print_usage(std::ostream& stream) {
  stream
      << "Usage: nidar-flight --sim --endpoint udpin://127.0.0.1:14540 "
         "[--discovery-timeout-ms N] [--telemetry-max-age-ms N] "
         "[--telemetry-wait-ms N]\n"
      << "  --sim                     run the Phase 3A SITL telemetry path\n"
      << "  --endpoint URL            MAVSDK loopback UDP listener\n"
      << "  --discovery-timeout-ms N  bounded PX4 discovery deadline\n"
      << "  --telemetry-max-age-ms N  maximum usable telemetry age\n"
      << "  --telemetry-wait-ms N     bounded initial telemetry deadline\n";
}

std::optional<std::chrono::milliseconds> parse_positive_ms(std::string_view text) {
  std::int64_t value{};
  const auto* first = text.data();
  const auto* last = first + text.size();
  const auto [ptr, error] = std::from_chars(first, last, value);
  if (error != std::errc{} || ptr != last || value <= 0) {
    return std::nullopt;
  }
  return std::chrono::milliseconds{value};
}

bool valid_sim_endpoint(std::string_view endpoint) {
  constexpr std::string_view prefix{"udpin://127.0.0.1:"};
  if (!endpoint.starts_with(prefix)) {
    return false;
  }

  const auto port_text = endpoint.substr(prefix.size());
  unsigned port{};
  const auto* first = port_text.data();
  const auto* last = first + port_text.size();
  const auto [ptr, error] = std::from_chars(first, last, port);
  return error == std::errc{} && ptr == last && port >= 1U && port <= 65535U;
}

std::optional<Options> parse_options(int argc, char** argv) {
  Options options;

  for (int index = 1; index < argc; ++index) {
    const std::string_view arg{argv[index]};
    if (arg == "--help") {
      print_usage(std::cout);
      return std::nullopt;
    }
    if (arg == "--sim") {
      options.sim = true;
      continue;
    }

    if (index + 1 >= argc) {
      return std::nullopt;
    }

    const std::string_view value{argv[++index]};
    if (arg == "--endpoint") {
      options.endpoint = value;
    } else if (arg == "--discovery-timeout-ms") {
      const auto parsed = parse_positive_ms(value);
      if (!parsed) {
        return std::nullopt;
      }
      options.discovery_timeout = *parsed;
    } else if (arg == "--telemetry-max-age-ms") {
      const auto parsed = parse_positive_ms(value);
      if (!parsed) {
        return std::nullopt;
      }
      options.telemetry_max_age = *parsed;
    } else if (arg == "--telemetry-wait-ms") {
      const auto parsed = parse_positive_ms(value);
      if (!parsed) {
        return std::nullopt;
      }
      options.telemetry_wait = *parsed;
    } else {
      return std::nullopt;
    }
  }

  if (!options.sim || !valid_sim_endpoint(options.endpoint)) {
    return std::nullopt;
  }
  return options;
}

std::string_view connection_result_name(VehicleConnectionResult result) {
  switch (result) {
    case VehicleConnectionResult::Connected:
      return "connected";
    case VehicleConnectionResult::AlreadyConnected:
      return "already-connected";
    case VehicleConnectionResult::TransportFailure:
      return "transport-failure";
    case VehicleConnectionResult::DiscoveryTimeout:
      return "discovery-timeout";
    case VehicleConnectionResult::InvalidArgument:
      return "invalid-argument";
  }
  return "unknown";
}

template <typename T>
long long age_ms(
    const nidar::vehicle::TelemetryField<T>& field,
    nidar::vehicle::SteadyTimePoint now) {
  return std::chrono::duration_cast<std::chrono::milliseconds>(
             now - field.last_update)
      .count();
}

}  // namespace

int main(int argc, char** argv) {
  if (argc == 2 && std::string_view{argv[1]} == "--help") {
    print_usage(std::cout);
    return 0;
  }

  const auto options = parse_options(argc, argv);
  if (!options) {
    print_usage(std::cerr);
    return 2;
  }

  MavsdkVehicle vehicle;
  const auto result =
      vehicle.connect(options->endpoint, options->discovery_timeout);
  if (result != VehicleConnectionResult::Connected) {
    std::cerr << "connection=" << connection_result_name(result) << '\n';
    vehicle.disconnect();
    return 3;
  }

  if (!vehicle.wait_for_required_telemetry(
          options->telemetry_max_age, options->telemetry_wait)) {
    std::cerr << "telemetry=not-ready\n";
    vehicle.disconnect();
    return 4;
  }

  const auto snapshot = vehicle.telemetry_snapshot(options->telemetry_max_age);
  const auto system_id = vehicle.system_id();
  if (!system_id || !snapshot.required_fields_fresh(options->telemetry_max_age)) {
    std::cerr << "telemetry=invalid-after-wait\n";
    vehicle.disconnect();
    return 5;
  }

  std::cout << "connection=connected\n"
            << "component=companion-computer\n"
            << "forwarding=off\n"
            << "mavsdk_version=" << vehicle.mavsdk_version() << '\n'
            << "px4_system_id=" << static_cast<unsigned>(*system_id) << '\n'
            << "telemetry=ready\n"
            << "armed_age_ms=" << age_ms(snapshot.armed, snapshot.assembled_at) << '\n'
            << "flight_mode_age_ms="
            << age_ms(snapshot.flight_mode, snapshot.assembled_at) << '\n'
            << "battery_age_ms="
            << age_ms(snapshot.battery, snapshot.assembled_at) << '\n'
            << "battery_voltage_v=" << snapshot.battery.value.voltage_volts << '\n';

  vehicle.disconnect();
  return 0;
}
