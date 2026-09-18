#!/usr/bin/env bash
set -eu

echo "This cleanup never deletes named volumes, release images, or flight evidence."
docker buildx prune --filter "until=168h" --max-used-space 10gb -f
docker container prune --filter "until=72h" -f
docker image prune -f
