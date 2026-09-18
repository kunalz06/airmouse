# Safety

PX4 remains independently safe if the Pi crashes, hangs, loses MAVLink, loses Offboard control, or powers off. NIDAR must never bypass PX4 safety checks. Flight-affecting behavior requires automated tests, SITL, fault injection, ARM64 packaging validation, and independent review.
