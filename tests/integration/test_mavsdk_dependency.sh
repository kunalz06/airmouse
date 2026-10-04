#!/usr/bin/env bash
set -euo pipefail

docker run --rm nidar-dev bash -lc '
  set -euo pipefail
  test "$(dpkg-query -W -f='''${Version}''' libmavsdk-dev)" = "3.17.2"
  test -r /usr/include/mavsdk/mavsdk.h
  test -r /usr/include/mavsdk/plugins/telemetry/telemetry.h
'
