ARG UBUNTU_24_04_IMAGE=ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3
ARG NIDAR_APT_LOCK_MODE=locked
ARG NIDAR_APT_BASELINE_GENERATION=0

FROM ${UBUNTU_24_04_IMAGE} AS mavsdk-apt
ARG NIDAR_APT_LOCK_MODE
ARG NIDAR_APT_BASELINE_GENERATION
COPY docker/apt/nidar-snapshot.sources /etc/apt/sources.list.d/nidar-snapshot.sources
COPY docker/apt/nidar-snapshot-ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
COPY docker/apt/install-locked.sh /usr/local/lib/nidar/install-locked-apt
COPY config/apt-closure /opt/nidar-apt-closure

RUN NIDAR_APT_LOCK_MODE="${NIDAR_APT_LOCK_MODE}" \
    NIDAR_APT_BASELINE_GENERATION="${NIDAR_APT_BASELINE_GENERATION}" \
    /bin/sh /usr/local/lib/nidar/install-locked-apt mavsdk-build \
      build-essential ca-certificates cmake git ninja-build pkg-config python3 python3-pip

FROM mavsdk-apt AS mavsdk-build
ARG MAVSDK_SOURCE_URL=https://github.com/mavlink/MAVSDK.git
ARG MAVSDK_SOURCE_COMMIT=9e3ca17faa84aa868caea10a3bbdab7e53810ced
COPY docker/runtime/mavsdk-telemetry-only.patch /tmp/mavsdk-telemetry-only.patch

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

FROM ${UBUNTU_24_04_IMAGE} AS app-apt
ARG NIDAR_APT_LOCK_MODE
ARG NIDAR_APT_BASELINE_GENERATION
COPY docker/apt/nidar-snapshot.sources /etc/apt/sources.list.d/nidar-snapshot.sources
COPY docker/apt/nidar-snapshot-ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
COPY docker/apt/install-locked.sh /usr/local/lib/nidar/install-locked-apt
COPY config/apt-closure /opt/nidar-apt-closure

RUN NIDAR_APT_LOCK_MODE="${NIDAR_APT_LOCK_MODE}" \
    NIDAR_APT_BASELINE_GENERATION="${NIDAR_APT_BASELINE_GENERATION}" \
    /bin/sh /usr/local/lib/nidar/install-locked-apt app-build \
      build-essential cmake ninja-build

FROM app-apt AS app-build
COPY --from=mavsdk-build /opt/mavsdk-install /opt/mavsdk-install
WORKDIR /workspace
COPY . .

RUN cmake -S . -B build/release -G Ninja \
      -DBUILD_TESTING=OFF \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_PREFIX_PATH=/opt/mavsdk-install \
 && cmake --build build/release --parallel \
 && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

FROM ${UBUNTU_24_04_IMAGE} AS runtime-apt
ARG NIDAR_APT_LOCK_MODE
ARG NIDAR_APT_BASELINE_GENERATION
COPY docker/apt/nidar-snapshot.sources /etc/apt/sources.list.d/nidar-snapshot.sources
COPY docker/apt/nidar-snapshot-ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
COPY docker/apt/install-locked.sh /usr/local/lib/nidar/install-locked-apt
COPY config/apt-closure /opt/nidar-apt-closure

RUN NIDAR_APT_LOCK_MODE="${NIDAR_APT_LOCK_MODE}" \
    NIDAR_APT_BASELINE_GENERATION="${NIDAR_APT_BASELINE_GENERATION}" \
    /bin/sh /usr/local/lib/nidar/install-locked-apt runtime \
      ca-certificates libgcc-s1 libstdc++6

FROM scratch AS apt-closure-export
COPY --from=mavsdk-apt /opt/nidar-provenance/mavsdk-build-packages.tsv /mavsdk-build-packages.tsv
COPY --from=app-apt /opt/nidar-provenance/app-build-packages.tsv /app-build-packages.tsv
COPY --from=runtime-apt /opt/nidar-provenance/runtime-packages.tsv /runtime-packages.tsv

FROM runtime-apt AS runtime
ARG NIDAR_APT_LOCK_MODE
ARG NIDAR_APT_BASELINE_GENERATION
ARG SOURCE_DATE_EPOCH
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

# The final production target can never be built from bootstrap package input.
# The isolated apt-closure-export target above is the only bootstrap consumer.
RUN test "${NIDAR_APT_LOCK_MODE}" = "locked" \
 && test "${NIDAR_APT_BASELINE_GENERATION}" = "0" \
 && test -n "${SOURCE_DATE_EPOCH}"

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

RUN mkdir -p /usr/local/share/nidar/provenance \
 && cp /opt/nidar-provenance/runtime-packages.tsv /usr/local/share/nidar/provenance/runtime-packages.tsv \
 && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/* /opt/nidar-apt-closure /usr/local/lib/nidar

# Exact installed package/version/architecture closure for all three stages.
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
