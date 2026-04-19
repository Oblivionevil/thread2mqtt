ARG BUILD_FROM
FROM ${BUILD_FROM}

# System dependencies for python-matter-server / chip-core
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        libuv1 \
        netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/thread2mqtt

COPY requirements.txt ./requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY app ./app
COPY run.sh /run.sh

RUN chmod a+x /run.sh

CMD ["/run.sh"]