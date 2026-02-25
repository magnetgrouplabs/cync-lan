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

COPY ./ /tmp/cync-src

RUN set -x && pip install --no-cache-dir /tmp/cync-src
#COPY static/index.html /root/cync-lan/www/index.html
COPY static/ /root/cync-lan/www/

VOLUME /root/cync-lan/config
EXPOSE 23779
EXPOSE 23778

LABEL org.opencontainers.image.source="https://github.com/baudneo/cync-lan"
LABEL org.opencontainers.image.description="Local async MQTT controller for Cync/C by GE Wi-Fi devices"

#CMD 'python -c "from cync_lan.main import main; import asyncio; import uvloop; asyncio.set_event_loop_policy(uvloop.EventLoopPolicy()); main()" --enable-export'
#CMD 'python -c "from cync_lan.main import main; main()"'
CMD cync-lan