FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3

ARG PX4_COMMIT=d6f12ad1c4f70ad3230afd7d86e971421e02fef4

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       ca-certificates git lsb-release sudo wget \
    && printf 'Acquire::http::Timeout "60";\nAcquire::https::Timeout "60";\nAcquire::Retries "2";\n' > /etc/apt/apt.conf.d/99nidar-network-timeouts \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone https://github.com/PX4/PX4-Autopilot.git PX4-Autopilot \
    && cd PX4-Autopilot \
    && git checkout --detach "${PX4_COMMIT}" \
    && test "$(git rev-parse HEAD)" = "${PX4_COMMIT}" \
    && git submodule update --init --recursive \
    && sed -i 's|http://packages.osrfoundation.org/gazebo/ubuntu-stable|https://packages.osrfoundation.org/gazebo/ubuntu-stable|' Tools/setup/ubuntu.sh \
    && ./Tools/setup/ubuntu.sh --no-nuttx \
    && make px4_sitl_default

WORKDIR /opt/PX4-Autopilot
ENV PX4_HOME_LAT=47.397742 \
    PX4_HOME_LON=8.545594 \
    PX4_HOME_ALT=488

CMD ["bash"]
