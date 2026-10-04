#include <array>
#include <chrono>
#include <cstdint>
#include <future>
#include <thread>

#include <arpa/inet.h>
#include <sys/socket.h>
#include <unistd.h>

#include <gtest/gtest.h>

#include "nidar/vehicle/mavsdk_vehicle.hpp"

namespace nidar::vehicle {
using namespace std::chrono_literals;

namespace {

constexpr std::uint8_t kMavlinkV1Magic = 0xFE;
constexpr std::uint8_t kHeartbeatPayloadLength = 9;
constexpr std::uint8_t kHeartbeatMessageId = 0;
constexpr std::uint8_t kHeartbeatCrcExtra = 50;
constexpr std::uint8_t kQuadrotorType = 2;
constexpr std::uint8_t kArdupilotMega = 3;
constexpr std::uint8_t kPx4 = 12;
constexpr std::uint8_t kSystemStatusStandby = 3;
constexpr std::uint8_t kMavlinkVersion = 3;

std::uint16_t crc_accumulate(std::uint8_t data, std::uint16_t crc) {
  auto tmp = static_cast<std::uint8_t>(data ^ (crc & 0xFFU));
  tmp = static_cast<std::uint8_t>(tmp ^ (tmp << 4U));
  return static_cast<std::uint16_t>((crc >> 8U) ^
                                    (static_cast<std::uint16_t>(tmp) << 8U) ^
                                    (static_cast<std::uint16_t>(tmp) << 3U) ^
                                    (static_cast<std::uint16_t>(tmp) >> 4U));
}

std::array<std::uint8_t, 17> heartbeat_packet(std::uint8_t sequence,
                                              std::uint8_t autopilot) {
  std::array<std::uint8_t, 17> packet{};
  packet[0] = kMavlinkV1Magic;
  packet[1] = kHeartbeatPayloadLength;
  packet[2] = sequence;
  packet[3] = 42;
  packet[4] = 1;
  packet[5] = kHeartbeatMessageId;

  packet[10] = kQuadrotorType;
  packet[11] = autopilot;
  packet[12] = 0;
  packet[13] = kSystemStatusStandby;
  packet[14] = kMavlinkVersion;

  std::uint16_t crc = 0xFFFFU;
  for (std::size_t index = 1; index <= 14; ++index) {
    crc = crc_accumulate(packet[index], crc);
  }
  crc = crc_accumulate(kHeartbeatCrcExtra, crc);
  packet[15] = static_cast<std::uint8_t>(crc & 0xFFU);
  packet[16] = static_cast<std::uint8_t>(crc >> 8U);
  return packet;
}

std::jthread start_heartbeat_sender(std::uint16_t port, std::uint8_t autopilot,
                                    std::chrono::milliseconds initial_delay,
                                    std::chrono::milliseconds duration) {
  return std::jthread([=] {
    std::this_thread::sleep_for(initial_delay);

    const int socket_fd = ::socket(AF_INET, SOCK_DGRAM, 0);
    if (socket_fd < 0) {
      return;
    }

    sockaddr_in destination{};
    destination.sin_family = AF_INET;
    destination.sin_port = htons(port);
    destination.sin_addr.s_addr = htonl(INADDR_LOOPBACK);

    const auto deadline = SteadyClock::now() + duration;
    std::uint8_t sequence = 0;
    while (SteadyClock::now() < deadline) {
      const auto packet = heartbeat_packet(sequence++, autopilot);
      (void)::sendto(socket_fd, packet.data(), packet.size(), 0,
                     reinterpret_cast<const sockaddr *>(&destination),
                     sizeof(destination));
      std::this_thread::sleep_for(20ms);
    }

    ::close(socket_fd);
  });
}

} // namespace

TEST(MavsdkVehicle, RejectsInvalidArguments) {
  MavsdkVehicle vehicle;
  EXPECT_EQ(vehicle.connect("", 50ms),
            VehicleConnectionResult::InvalidArgument);
  EXPECT_EQ(vehicle.connect("udpin://127.0.0.1:14690", 0ms),
            VehicleConnectionResult::InvalidArgument);
}

TEST(MavsdkVehicle, MalformedUrlIsTransportFailure) {
  MavsdkVehicle vehicle;
  EXPECT_EQ(vehicle.connect("not-a-url", 50ms),
            VehicleConnectionResult::TransportFailure);
}

TEST(MavsdkVehicle, EmptyListenerIsDiscoveryTimeout) {
  MavsdkVehicle vehicle;
  EXPECT_EQ(vehicle.connect("udpin://127.0.0.1:14690", 50ms),
            VehicleConnectionResult::DiscoveryTimeout);
  EXPECT_EQ(vehicle.connection_status(), ConnectionState::Disconnected);
}

TEST(MavsdkVehicle, RejectsNonPx4AutopilotDiscovery) {
  auto sender = start_heartbeat_sender(49693, kArdupilotMega, 50ms, 400ms);
  MavsdkVehicle vehicle;

  EXPECT_EQ(vehicle.connect("udpin://127.0.0.1:49693", 250ms),
            VehicleConnectionResult::DiscoveryTimeout);
  EXPECT_EQ(vehicle.connection_status(), ConnectionState::Disconnected);
}

TEST(MavsdkVehicle, AcceptsDelayedPx4DiscoveryWithinDeadline) {
  auto sender = start_heartbeat_sender(49694, kPx4, 100ms, 600ms);
  MavsdkVehicle vehicle;

  EXPECT_EQ(vehicle.connect("udpin://127.0.0.1:49694", 1s),
            VehicleConnectionResult::Connected);
  EXPECT_EQ(vehicle.system_id(), 42);
  vehicle.disconnect();
  EXPECT_EQ(vehicle.connection_status(), ConnectionState::Disconnected);
}

TEST(MavsdkVehicle, Px4DiscoveryAfterDeadlineTimesOut) {
  auto sender = start_heartbeat_sender(49695, kPx4, 300ms, 300ms);
  MavsdkVehicle vehicle;

  EXPECT_EQ(vehicle.connect("udpin://127.0.0.1:49695", 100ms),
            VehicleConnectionResult::DiscoveryTimeout);
  EXPECT_EQ(vehicle.connection_status(), ConnectionState::Disconnected);
}

TEST(MavsdkVehicle, DisconnectCancelsPendingDiscovery) {
  MavsdkVehicle vehicle;
  auto result = std::async(std::launch::async, [&vehicle] {
    return vehicle.connect("udpin://127.0.0.1:49691", 5s);
  });

  const auto deadline = SteadyClock::now() + 1s;
  while (vehicle.connection_status() != ConnectionState::Connecting &&
         SteadyClock::now() < deadline) {
    std::this_thread::yield();
  }
  ASSERT_EQ(vehicle.connection_status(), ConnectionState::Connecting);

  vehicle.disconnect();
  ASSERT_EQ(result.wait_for(1s), std::future_status::ready);
  EXPECT_EQ(result.get(), VehicleConnectionResult::Cancelled);
  EXPECT_EQ(vehicle.connection_status(), ConnectionState::Disconnected);

  EXPECT_EQ(vehicle.connect("udpin://127.0.0.1:49691", 50ms),
            VehicleConnectionResult::DiscoveryTimeout);
}

TEST(MavsdkVehicle, RepeatedDiscoveryTimeoutsReleaseOwnedEndpoint) {
  MavsdkVehicle vehicle;

  for (int cycle = 0; cycle < 3; ++cycle) {
    EXPECT_EQ(vehicle.connect("udpin://127.0.0.1:49692", 50ms),
              VehicleConnectionResult::DiscoveryTimeout);
    EXPECT_EQ(vehicle.connection_status(), ConnectionState::Disconnected);
  }
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
  EXPECT_EQ(vehicle.start_offboard(100ms),
            VehicleCommandResult::RejectedByPhasePolicy);
}

} // namespace nidar::vehicle
