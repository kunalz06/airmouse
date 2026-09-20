# Configuration

Host baseline (2026-09-19): Ubuntu 26.04 x86_64; filesystem capacity 468 GB; free space 408 GB. Soft limits are BuildKit cache <= 10 GB, ccache <= 5 GB, Docker total <= 30 GB, and free filesystem space >= 25 GB.

Docker Engine is installed from Docker's Ubuntu apt repository. QGroundControl v5.1.4 is installed at `/opt/qgroundcontrol/QGroundControl.AppImage` with SHA-256 `1c4ac089abfaac6c6fcd75c7b477ea18da1bc3592cddca5ab1a19c1a13410e65`. A new login is required to refresh group membership for Docker, dialout, video, and render.

Phase 2 revised Docker budget (2026-09-20): the pinned PX4/Gazebo simulation
image is 10.7 GB and BuildKit retains 22.95 GB of active source and toolchain
layers after the prescribed unused-cache pruning. The Phase 2 limit is therefore
BuildKit cache <= 23 GB and Docker images plus BuildKit cache <= 35 GB, while
maintaining at least 25 GB free filesystem space. The host had 374 GB free
after cleanup. This revision is limited to the PX4/Gazebo simulation image;
unused cache must still be pruned with `scripts/docker-gc.sh` and the bounded
10 GB cleanup attempt before expanding the budget further.
