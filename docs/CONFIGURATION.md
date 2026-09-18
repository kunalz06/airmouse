# Configuration

Host baseline (2026-09-19): Ubuntu 26.04 x86_64; filesystem capacity 468 GB; free space 408 GB. Soft limits are BuildKit cache <= 10 GB, ccache <= 5 GB, Docker total <= 30 GB, and free filesystem space >= 25 GB.

Docker Engine is installed from Docker's Ubuntu apt repository. QGroundControl v5.1.4 is installed at `/opt/qgroundcontrol/QGroundControl.AppImage` with SHA-256 `1c4ac089abfaac6c6fcd75c7b477ea18da1bc3592cddca5ab1a19c1a13410e65`. A new login is required to refresh group membership for Docker, dialout, video, and render.
