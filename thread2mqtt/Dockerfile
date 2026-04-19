ARG BUILD_FROM
FROM ${BUILD_FROM}

# System dependencies for python-matter-server / chip-core
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        libuv1 \
        libglib2.0-0 \
        zlib1g \
        libjson-c5 \
        libnl-3-200 \
        libnl-route-3-200 \
        netcat-openbsd \
        bluez \
        libbluetooth-dev \
        libudev-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/thread2mqtt

COPY requirements.txt ./requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY app ./app
COPY run.sh /run.sh

RUN chmod a+x /run.sh

CMD ["/run.sh"]