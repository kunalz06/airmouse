FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential clang clang-format clang-tidy cmake ninja-build ccache gdb \
    libgtest-dev libyaml-cpp-dev libspdlog-dev python3 shellcheck \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
