cmake_minimum_required(VERSION 3.28)

project(nidar_drone VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(CTest)

add_executable(nidar-flight apps/nidar-flight/main.cpp)
target_compile_features(nidar-flight PRIVATE cxx_std_20)

if(BUILD_TESTING)
  find_package(GTest REQUIRED)
  add_executable(nidar-flight-test tests/unit/nidar_flight_test.cpp)
  target_link_libraries(nidar-flight-test PRIVATE GTest::gtest_main)
  include(GoogleTest)
  gtest_discover_tests(nidar-flight-test)
endif()
