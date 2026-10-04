#!/usr/bin/env bash
set -euo pipefail

version="$(docker run --rm nidar-dev dpkg-query -W -f='${Version}' libmavsdk-dev)"
if [[ "${version}" != "3.17.2" ]]; then
  printf 'unexpected MAVSDK package version: %s\n' "${version}" >&2
  exit 1
fi

docker run --rm nidar-dev test -r /usr/include/mavsdk/mavsdk.h
docker run --rm nidar-dev test -r /usr/include/mavsdk/plugins/telemetry/telemetry.h
