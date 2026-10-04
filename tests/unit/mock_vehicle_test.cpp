#include <chrono>

#include <gtest/gtest.h>

#include "nidar/vehicle/mock_vehicle.hpp"

namespace nidar::vehicle {
using namespace std::chrono_literals;

TEST(MockVehicle, BatteryDoesNotRefreshArmed) {
  MockVehicle vehicle;
  ASSERT_EQ(vehicle.connect("udpin://127.0.0.1:14540", 1s),
            VehicleConnectionResult::Connected);

  const auto now = SteadyClock::now();
  vehicle.publish_armed(true, now - 100ms);
  vehicle.publish_battery(BatteryState{.voltage_volts = 15.2F}, now - 10ms);

  const auto snapshot = vehicle.telemetry_snapshot(1s);
  EXPECT_EQ(snapshot.armed.last_update, now - 100ms);
  EXPECT_EQ(snapshot.battery.last_update, now - 10ms);
}

TEST(MockVehicle, DisconnectInvalidatesEveryField) {
  MockVehicle vehicle;
  ASSERT_EQ(vehicle.connect("udpin://127.0.0.1:14540", 1s),
            VehicleConnectionResult::Connected);
  const auto now = SteadyClock::now();
  vehicle.publish_armed(true, now);
  vehicle.publish_flight_mode(FlightMode::Hold, now);
  vehicle.publish_battery(BatteryState{.voltage_volts = 15.2F}, now);

  vehicle.disconnect();
  const auto snapshot = vehicle.telemetry_snapshot(1s);
  EXPECT_EQ(snapshot.armed.validity, TelemetryValidity::Unavailable);
  EXPECT_EQ(snapshot.flight_mode.validity, TelemetryValidity::Unavailable);
  EXPECT_EQ(snapshot.battery.validity, TelemetryValidity::Unavailable);
  EXPECT_EQ(vehicle.connection_status(), ConnectionState::Disconnected);
}

TEST(MockVehicle, StaleFieldIsNotUsable) {
  MockVehicle vehicle;
  ASSERT_EQ(vehicle.connect("udpin://127.0.0.1:14540", 1s),
            VehicleConnectionResult::Connected);
  const auto now = SteadyClock::now();
  vehicle.publish_armed(true, now - 2s);

  const auto snapshot = vehicle.telemetry_snapshot(100ms);
  EXPECT_EQ(snapshot.armed.validity, TelemetryValidity::Stale);
}

TEST(MockVehicle, RejectsEveryActiveCommand) {
  MockVehicle vehicle;
  const auto timeout = 1s;
  EXPECT_EQ(vehicle.arm(timeout), VehicleCommandResult::RejectedByPhasePolicy);
  EXPECT_EQ(vehicle.disarm(timeout),
            VehicleCommandResult::RejectedByPhasePolicy);
  EXPECT_EQ(vehicle.takeoff(1.5, timeout),
            VehicleCommandResult::RejectedByPhasePolicy);
  EXPECT_EQ(vehicle.land(timeout), VehicleCommandResult::RejectedByPhasePolicy);
  EXPECT_EQ(vehicle.hold(timeout), VehicleCommandResult::RejectedByPhasePolicy);
  EXPECT_EQ(vehicle.start_offboard(timeout),
            VehicleCommandResult::RejectedByPhasePolicy);
  EXPECT_EQ(vehicle.stop_offboard(timeout),
            VehicleCommandResult::RejectedByPhasePolicy);
  EXPECT_EQ(vehicle.set_position_target({}, timeout),
            VehicleCommandResult::RejectedByPhasePolicy);
  EXPECT_EQ(vehicle.set_velocity_target({}, timeout),
            VehicleCommandResult::RejectedByPhasePolicy);
}

} // namespace nidar::vehicle
