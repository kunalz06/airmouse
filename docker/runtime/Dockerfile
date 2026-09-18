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
