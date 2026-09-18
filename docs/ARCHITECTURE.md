# Architecture

PX4 owns attitude/rate/motor control, EKF2, arming checks, flight modes, failsafes, and low-level position/velocity control. The Pi owns mission orchestration, high-level navigation, health monitoring, logging, and approved setpoint generation. MAVSDK is isolated to the future vehicle adapter.
