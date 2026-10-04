# Phase 3A note:
# The production linux/arm64 image is a Phase 4 gate because MAVSDK v3.17.2
# does not publish an Ubuntu 24.04 arm64 development package. This definition
# is retained from Phase 1 as the packaging baseline; do not treat it as a
# valid Phase 3A release image until Phase 4 adds verified arm64 MAVSDK.
FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3 AS build
WORKDIR /workspace
COPY . .
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends build-essential cmake ninja-build \
 && cmake -S . -B build/runtime -G Ninja -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release \
 && cmake --build build/runtime \
 && rm -rf /var/lib/apt/lists/*

FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3
COPY --from=build /workspace/build/runtime/nidar-flight /usr/local/bin/nidar-flight
USER 65532:65532
ENTRYPOINT ["/usr/local/bin/nidar-flight"]
