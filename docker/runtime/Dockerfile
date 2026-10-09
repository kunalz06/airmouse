ARG UBUNTU_24_04_IMAGE=ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3

FROM ${UBUNTU_24_04_IMAGE} AS mavsdk-build
ARG MAVSDK_SOURCE_URL=https://github.com/mavlink/MAVSDK.git
ARG MAVSDK_SOURCE_COMMIT=9e3ca17faa84aa868caea10a3bbdab7e53810ced

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential ca-certificates cmake git ninja-build pkg-config python3 python3-pip \
 && rm -rf /var/lib/apt/lists/*

RUN git clone --filter=blob:none "${MAVSDK_SOURCE_URL}" /opt/mavsdk-src \
 && cd /opt/mavsdk-src \
 && git checkout --detach "${MAVSDK_SOURCE_COMMIT}" \
 && test "$(git rev-parse HEAD)" = "${MAVSDK_SOURCE_COMMIT}" \
 && git submodule update --init --recursive

RUN cmake -S /opt/mavsdk-src -B /opt/mavsdk-build -G Ninja \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_INSTALL_PREFIX=/opt/mavsdk-install \
      -DBUILD_SHARED_LIBS=ON \
      -DBUILD_MAVSDK_SERVER=OFF \
 && cmake --build /opt/mavsdk-build --parallel \
 && cmake --install /opt/mavsdk-build

FROM ${UBUNTU_24_04_IMAGE} AS app-build
COPY --from=mavsdk-build /opt/mavsdk-install /opt/mavsdk-install
WORKDIR /workspace
COPY . .

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential cmake ninja-build \
 && cmake -S . -B build/release -G Ninja \
      -DBUILD_TESTING=OFF \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_PREFIX_PATH=/opt/mavsdk-install \
 && cmake --build build/release --parallel \
 && rm -rf /var/lib/apt/lists/*

FROM ${UBUNTU_24_04_IMAGE} AS runtime
ARG NIDAR_GIT_COMMIT
ARG NIDAR_BUILD_TIMESTAMP
ARG NIDAR_VERSION=0.2.0
ARG MAVSDK_VERSION=3.17.2
ARG MAVSDK_SOURCE_COMMIT=9e3ca17faa84aa868caea10a3bbdab7e53810ced
ARG RUNTIME_BASE_DIGEST=sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3

LABEL org.opencontainers.image.title="nidar-runtime" \
      org.opencontainers.image.description="NIDAR telemetry-only ARM64 runtime" \
      org.opencontainers.image.version="${NIDAR_VERSION}" \
      org.opencontainers.image.revision="${NIDAR_GIT_COMMIT}" \
      org.opencontainers.image.created="${NIDAR_BUILD_TIMESTAMP}" \
      org.opencontainers.image.base.digest="${RUNTIME_BASE_DIGEST}" \
      io.nidar.target.architecture="linux/arm64" \
      io.nidar.mavsdk.version="${MAVSDK_VERSION}" \
      io.nidar.mavsdk.source-commit="${MAVSDK_SOURCE_COMMIT}"

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates libgcc-s1 libstdc++6 \
 && rm -rf /var/lib/apt/lists/*

COPY --from=mavsdk-build /opt/mavsdk-install/lib/libmavsdk.so.3.17.2 /usr/local/lib/
COPY --from=app-build /workspace/build/release/nidar-flight /usr/local/bin/nidar-flight

RUN ln -s libmavsdk.so.3.17.2 /usr/local/lib/libmavsdk.so.3 \
 && ln -s libmavsdk.so.3.17.2 /usr/local/lib/libmavsdk.so \
 && ldconfig \
 && test -x /usr/local/bin/nidar-flight \
 && test -e /usr/local/lib/libmavsdk.so

USER 65532:65532
ENTRYPOINT ["/usr/local/bin/nidar-flight"]
