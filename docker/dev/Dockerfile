FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3

ARG MAVSDK_VERSION=3.17.2
ARG MAVSDK_SHA256=9a8c0e960b6cda8f1b09d522a3fd7ea214808ebca922c7ad482d1194243f8cc5

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl clang clang-format clang-tidy cmake ninja-build ccache gdb \
    libgtest-dev libyaml-cpp-dev libspdlog-dev python3 ripgrep shellcheck \
 && curl --fail --location --retry 3 \
    -o /tmp/mavsdk.deb \
    "https://github.com/mavlink/MAVSDK/releases/download/v${MAVSDK_VERSION}/libmavsdk-dev_${MAVSDK_VERSION}_ubuntu24.04_amd64.deb" \
 && echo "${MAVSDK_SHA256}  /tmp/mavsdk.deb" | sha256sum --check --strict \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends /tmp/mavsdk.deb \
 && rm -rf /var/lib/apt/lists/* /tmp/mavsdk.deb

WORKDIR /workspace
