#include <chrono>

#include <gtest/gtest.h>

#include "nidar/vehicle/mavsdk_vehicle.hpp"

namespace nidar::vehicle {
using namespace std::chrono_literals;

TEST(MavsdkVehicle, RejectsInvalidArguments) {
  MavsdkVehicle vehicle;
  EXPECT_EQ(vehicle.connect("", 50ms), VehicleConnectionResult::InvalidArgument);
  EXPECT_EQ(
      vehicle.connect("udpin://127.0.0.1:14690", 0ms),
      VehicleConnectionResult::InvalidArgument);
}

TEST(MavsdkVehicle, MalformedUrlIsTransportFailure) {
  MavsdkVehicle vehicle;
  EXPECT_EQ(
      vehicle.connect("not-a-url", 50ms),
      VehicleConnectionResult::TransportFailure);
}

TEST(MavsdkVehicle, EmptyListenerIsDiscoveryTimeout) {
  MavsdkVehicle vehicle;
  EXPECT_EQ(
      vehicle.connect("udpin://127.0.0.1:14690", 50ms),
      VehicleConnectionResult::DiscoveryTimeout);
  EXPECT_EQ(vehicle.connection_status(), ConnectionState::Disconnected);
}

TEST(MavsdkVehicle, DisconnectIsIdempotent) {
  MavsdkVehicle vehicle;
  vehicle.disconnect();
  vehicle.disconnect();
  EXPECT_EQ(vehicle.connection_status(), ConnectionState::Disconnected);
}

TEST(MavsdkVehicle, RejectsActiveCommandsWithoutMavsdkCommandPlugins) {
  MavsdkVehicle vehicle;
  EXPECT_EQ(vehicle.arm(100ms), VehicleCommandResult::RejectedByPhasePolicy);
  EXPECT_EQ(vehicle.land(100ms), VehicleCommandResult::RejectedByPhasePolicy);
  EXPECT_EQ(vehicle.start_offboard(100ms), VehicleCommandResult::RejectedByPhasePolicy);
}

}  // namespace nidar::vehicle
