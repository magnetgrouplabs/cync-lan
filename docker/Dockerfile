FROM python:3.13-slim-bookworm AS final

#ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN set -x \
    && mkdir -p /root/cync-lan/certs \
    && openssl req -x509 -newkey rsa:4096 \
        -keyout '/root/cync-lan/certs/key.pem' -out '/root/cync-lan/certs/cert.pem' \
        -subj '/CN=*.xlink.cn' -sha256 -days 3650 -nodes

COPY ./ /tmp/cync-src

RUN set -x \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -yq --no-install-recommends \
        openssl build-essential cmake \
    && pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir /tmp/cync-src \
    && DEBIAN_FRONTEND=noninteractive apt-get remove -yq build-essential cmake \
    && DEBIAN_FRONTEND=noninteractive apt-get autoremove -yq \
    && DEBIAN_FRONTEND=noninteractive apt-get clean \
    && rm -rf /var/lib/apt/lists/*

VOLUME /root/cync-lan/config
EXPOSE 23779

ENV CYNC_MQTT_HOST="homeassistant.local" \
    CYNC_MQTT_PORT=1883 \
    CYNC_PORT=23779 \
    CYNC_HOST="0.0.0.0" \
    CYNC_CERT="/root/cync-lan/certs/cert.pem" \
    CYNC_KEY="/root/cync-lan/certs/key.pem" \
    CYNC_DEBUG=0 \
    CYNC_RAW_DEBUG=0 \
    CYNC_TOPIC="cync_lan" \
    CYNC_HASS_TOPIC="homeassistant" \
    CYNC_HASS_STATUS_TOPIC="status" \
    CYNC_HASS_BIRTH_MSG="online" \
    CYNC_HASS_WILL_MSG="offline" \
    CYNC_MQTT_CONN_DELAY=10 \
    CYNC_CMD_BROADCASTS=2 \
    CYNC_MAX_TCP_CONN=8 \
    CYNC_TCP_WHITELIST=""

LABEL org.opencontainers.image.source="https://github.com/baudneo/cync-lan"
LABEL org.opencontainers.image.description="Local async MQTT controller for Cync/C by GE Wi-Fi devices"

CMD cync-lan
