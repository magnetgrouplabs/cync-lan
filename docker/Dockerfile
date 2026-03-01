FROM python:3.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    DEBIAN_FRONTEND=noninteractive

RUN set -x \
    && mkdir -p /root/cync-lan/certs \
    && openssl req -x509 -newkey rsa:4096 \
        -keyout '/root/cync-lan/certs/key.pem' -out '/root/cync-lan/certs/cert.pem' \
        -subj '/CN=*.xlink.cn' -sha256 -days 3650 -nodes

WORKDIR /tmp/cync-src
COPY ./ .

# Install dependencies and the local package, then immediately nuke the source files
RUN set -x \
    && pip install --no-cache-dir \
        "pyyaml==6.0.2" \
        "uvloop>=0.21.0" \
        "aiomqtt==2.3.0" \
        "aiohttp>=3.10.8" \
        "fastapi>=0.115.12" \
        "uvicorn>=0.34.3" \
        "tzlocal>=5.3.1" \
        . \
    && rm -rf /tmp/cync-src

COPY static/ /root/cync-lan/www/

VOLUME /root/cync-lan/config
EXPOSE 23779 23778

LABEL org.opencontainers.image.source="https://github.com/baudneo/cync-lan"
LABEL org.opencontainers.image.description="Local async MQTT controller for Cync/C by GE Wi-Fi devices"

# Use the exec form (JSON array) for CMD to pass signals cleanly
CMD ["cync-lan"]