#!/usr/bin/env bash
set -eu

docker system df -v
docker buildx du
df -h /
du -sh build* .cache .ccache 2>/dev/null || true
