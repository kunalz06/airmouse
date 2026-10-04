cmake_minimum_required(VERSION 3.28)

project(nidar_drone VERSION 0.2.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(CTest)

find_package(MAVSDK 3.17.2 REQUIRED)

add_library(nidar_vehicle
  src/vehicle/mock_vehicle.cpp
  src/vehicle/mavsdk_vehicle.cpp
)
target_include_directories(nidar_vehicle PUBLIC include)
target_link_libraries(nidar_vehicle PRIVATE MAVSDK::mavsdk)
target_compile_features(nidar_vehicle PUBLIC cxx_std_20)
target_compile_options(nidar_vehicle PRIVATE -Wall -Wextra -Wpedantic -Werror)

add_executable(nidar-flight apps/nidar-flight/main.cpp)
target_link_libraries(nidar-flight PRIVATE nidar_vehicle)
target_compile_features(nidar-flight PRIVATE cxx_std_20)
target_compile_options(nidar-flight PRIVATE -Wall -Wextra -Wpedantic -Werror)

if(BUILD_TESTING)
  find_package(GTest REQUIRED)
  include(GoogleTest)

  add_executable(nidar-flight-test tests/unit/nidar_flight_test.cpp)
  target_link_libraries(nidar-flight-test PRIVATE GTest::gtest_main)
  target_compile_options(nidar-flight-test PRIVATE -Wall -Wextra -Wpedantic -Werror)
  gtest_discover_tests(nidar-flight-test)

  add_executable(vehicle-types-test tests/unit/vehicle_types_test.cpp)
  target_link_libraries(vehicle-types-test PRIVATE GTest::gtest_main nidar_vehicle)
  target_compile_options(vehicle-types-test PRIVATE -Wall -Wextra -Wpedantic -Werror)
  gtest_discover_tests(vehicle-types-test)

  add_executable(mock-vehicle-test tests/unit/mock_vehicle_test.cpp)
  target_link_libraries(mock-vehicle-test PRIVATE GTest::gtest_main nidar_vehicle)
  target_compile_options(mock-vehicle-test PRIVATE -Wall -Wextra -Wpedantic -Werror)
  gtest_discover_tests(mock-vehicle-test)

  add_executable(mavsdk-vehicle-test tests/unit/mavsdk_vehicle_test.cpp)
  target_link_libraries(mavsdk-vehicle-test PRIVATE GTest::gtest_main nidar_vehicle)
  target_compile_options(mavsdk-vehicle-test PRIVATE -Wall -Wextra -Wpedantic -Werror)
  gtest_discover_tests(mavsdk-vehicle-test)
endif()
