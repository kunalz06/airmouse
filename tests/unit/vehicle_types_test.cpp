#include <chrono>

#include <gtest/gtest.h>

#include "nidar/vehicle/vehicle_types.hpp"

namespace nidar::vehicle {
using namespace std::chrono_literals;

TEST(VehicleTypes, RequiresIndependentFreshFields) {
  const auto now = SteadyClock::now();
  TelemetrySnapshot snapshot{
      .assembled_at = now,
      .armed = {true, TelemetryValidity::Valid, now - 10ms},
      .flight_mode = {FlightMode::Hold, TelemetryValidity::Valid, now - 20ms},
      .battery = {BatteryState{.voltage_volts = 15.2F},
                  TelemetryValidity::Valid, now - 30ms},
  };

  EXPECT_TRUE(snapshot.required_fields_fresh(100ms));
  snapshot.armed.last_update = now - 2s;
  EXPECT_FALSE(snapshot.required_fields_fresh(100ms));
}

} // namespace nidar::vehicle
