# Deployment

The runtime target is a minimal linux/arm64 image for Raspberry Pi 5. It contains no Gazebo, PX4 development toolchain, compiler, IDE, CI tooling, or large dev packages. Logs and flight evidence remain outside image layers with bounded, non-silent retention.
