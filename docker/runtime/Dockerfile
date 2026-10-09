ARG UBUNTU_24_04_IMAGE=ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3

FROM ${UBUNTU_24_04_IMAGE} AS mavsdk-build
ARG MAVSDK_SOURCE_URL=https://github.com/mavlink/MAVSDK.git
ARG MAVSDK_SOURCE_COMMIT=9e3ca17faa84aa868caea10a3bbdab7e53810ced
COPY docker/runtime/mavsdk-telemetry-only.patch /tmp/mavsdk-telemetry-only.patch

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential ca-certificates cmake git ninja-build pkg-config python3 python3-pip \
 && mkdir -p /opt/nidar-provenance \
 && LC_ALL=C dpkg-query -W -f='${binary:Package}\t${Version}\t${Architecture}\n' | LC_ALL=C sort > /opt/nidar-provenance/mavsdk-build-packages.tsv \
 && test -s /opt/nidar-provenance/mavsdk-build-packages.tsv \
 && rm -rf /var/lib/apt/lists/*

RUN git clone --filter=blob:none "${MAVSDK_SOURCE_URL}" /opt/mavsdk-src \
 && cd /opt/mavsdk-src \
 && git checkout --detach "${MAVSDK_SOURCE_COMMIT}" \
 && test "$(git rev-parse HEAD)" = "${MAVSDK_SOURCE_COMMIT}" \
 && git submodule update --init --recursive \
 && git apply --check /tmp/mavsdk-telemetry-only.patch \
 && git apply /tmp/mavsdk-telemetry-only.patch

RUN cmake -S /opt/mavsdk-src -B /opt/mavsdk-build -G Ninja \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_INSTALL_PREFIX=/opt/mavsdk-install \
      -DBUILD_TESTING=OFF \
      -DBUILD_SHARED_LIBS=ON \
      -DBUILD_MAVSDK_SERVER=OFF \
      -DENABLED_PLUGINS=telemetry \
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
 && mkdir -p /opt/nidar-provenance \
 && LC_ALL=C dpkg-query -W -f='${binary:Package}\t${Version}\t${Architecture}\n' | LC_ALL=C sort > /opt/nidar-provenance/app-build-packages.tsv \
 && test -s /opt/nidar-provenance/app-build-packages.tsv \
 && rm -rf /var/lib/apt/lists/*

FROM ${UBUNTU_24_04_IMAGE} AS runtime
ARG NIDAR_GIT_COMMIT
ARG NIDAR_BUILD_TIMESTAMP
ARG NIDAR_SOURCE_TIMESTAMP
ARG NIDAR_CI_RUN_ID=local
ARG NIDAR_CI_RUN_ATTEMPT=0
ARG NIDAR_CI_WORKFLOW=local
ARG NIDAR_CI_SHA
ARG NIDAR_CI_HEAD_SHA
ARG NIDAR_CI_REPOSITORY=local
ARG NIDAR_VERSION=0.2.0
ARG MAVSDK_VERSION=3.17.2
ARG MAVSDK_SOURCE_COMMIT=9e3ca17faa84aa868caea10a3bbdab7e53810ced
ARG RUNTIME_BASE_DIGEST=sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3

LABEL org.opencontainers.image.title="nidar-runtime" \
      org.opencontainers.image.description="NIDAR telemetry-only ARM64 runtime" \
      org.opencontainers.image.source="https://github.com/kunalz06/airmouse" \
      org.opencontainers.image.version="${NIDAR_VERSION}" \
      org.opencontainers.image.revision="${NIDAR_GIT_COMMIT}" \
      org.opencontainers.image.created="${NIDAR_BUILD_TIMESTAMP}" \
      io.nidar.source.commit-timestamp="${NIDAR_SOURCE_TIMESTAMP}" \
      io.nidar.ci.run-id="${NIDAR_CI_RUN_ID}" \
      io.nidar.ci.run-attempt="${NIDAR_CI_RUN_ATTEMPT}" \
      io.nidar.ci.workflow="${NIDAR_CI_WORKFLOW}" \
      io.nidar.ci.sha="${NIDAR_CI_SHA}" \
      io.nidar.ci.head-sha="${NIDAR_CI_HEAD_SHA}" \
      io.nidar.ci.repository="${NIDAR_CI_REPOSITORY}" \
      org.opencontainers.image.base.digest="${RUNTIME_BASE_DIGEST}" \
      io.nidar.target.architecture="linux/arm64" \
      io.nidar.mavsdk.version="${MAVSDK_VERSION}" \
      io.nidar.mavsdk.source-commit="${MAVSDK_SOURCE_COMMIT}"

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates libgcc-s1 libstdc++6 \
 && mkdir -p /usr/local/share/nidar/provenance \
 && LC_ALL=C dpkg-query -W -f='${binary:Package}\t${Version}\t${Architecture}\n' | LC_ALL=C sort > /usr/local/share/nidar/provenance/runtime-packages.tsv \
 && test -s /usr/local/share/nidar/provenance/runtime-packages.tsv \
 && rm -rf /var/lib/apt/lists/*

# Exact installed-package version/architecture closure for each stage.
# These inventories are evidence only, not pinned .deb payload hashes.
COPY --from=mavsdk-build /opt/nidar-provenance/mavsdk-build-packages.tsv /usr/local/share/nidar/provenance/
COPY --from=app-build /opt/nidar-provenance/app-build-packages.tsv /usr/local/share/nidar/provenance/
COPY --from=mavsdk-build /opt/mavsdk-install/lib/libmavsdk.so.3.17.2 /usr/local/lib/
COPY --from=app-build /workspace/build/release/nidar-flight /usr/local/bin/nidar-flight

RUN ln -s libmavsdk.so.3.17.2 /usr/local/lib/libmavsdk.so.3 \
 && ln -s libmavsdk.so.3.17.2 /usr/local/lib/libmavsdk.so \
 && ldconfig \
 && test -x /usr/local/bin/nidar-flight \
 && test -e /usr/local/lib/libmavsdk.so

USER 65532:65532
ENTRYPOINT ["/usr/local/bin/nidar-flight"]
