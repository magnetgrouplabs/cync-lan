import os
from typing import Optional, List, Union, Tuple, Dict
import zoneinfo

import tzlocal

from cync_lan import __version__

SANITY_CHECK = 'test123'
__all__ = [
    "SANITY_CHECK",
    "ENABLE_EXPORTER",
    "CYNC_BASE_DIR",
    "CYNC_STATIC_DIR",
    "INGRESS_PORT",
    "CYNC_UUID_PATH",
    "FACTORY_EFFECTS_BYTES",
    "LOCAL_TZ",
    "CYNC_CONFIG_FILE_PATH",
    "CYNC_CLOUD_AUTH_PATH",
    "CYNC_VERSION",
    "SRC_REPO_URL",
    "DEVICE_LWT_MSG",
    "CYNC_MQTT_CONN_DELAY",
    "CYNC_CMD_BROADCASTS",
    "CYNC_MAX_TCP_CONN",
    "CYNC_TCP_WHITELIST",
    "CYNC_API_BASE",
    "CYNC_MQTT_HOST",
    "CYNC_MQTT_PORT",
    "CYNC_MQTT_USER",
    "CYNC_MQTT_PASS",
    "CYNC_SSL_CERT",
    "CYNC_SSL_KEY",
    "CYNC_TOPIC",
    "CYNC_HASS_TOPIC",
    "CYNC_HASS_STATUS_TOPIC",
    "CYNC_HASS_BIRTH_MSG",
    "CYNC_HASS_WILL_MSG",
    "CYNC_PORT",
    "CYNC_SRV_HOST",
    "CYNC_CHUNK_SIZE",
    "YES_ANSWER",
    "CYNC_RAW",
    "CYNC_DEBUG",
    "CYNC_ADDON_UUID",
    "CYNC_CORP_ID",
    "DATA_BOUNDARY",
    "RAW_MSG",
    "CYNC_LOG_NAME",
    "CYNC_ACCOUNT_USERNAME",
    "CYNC_ACCOUNT_PASSWORD",
    "CYNC_ACCOUNT_LANGUAGE",
]

YES_ANSWER = ("true", "1", "yes", "y", "t", 1)
LOCAL_TZ = zoneinfo.ZoneInfo(str(tzlocal.get_localzone()))
CYNC_LOG_NAME: str = "cync_lan"
CYNC_VERSION: str = __version__
SRC_REPO_URL: str = "https://github.com/baudneo/cync-lan"
CYNC_API_BASE: str = "https://api.gelighting.com/v2/"
DEVICE_LWT_MSG: bytes = b"offline"

CYNC_SRV_HOST = os.environ.get("CYNC_SRV_HOST", "0.0.0.0")
CYNC_ACCOUNT_LANGUAGE: str = os.environ.get("CYNC_ACCOUNT_LANGUAGE", "en-us").casefold()
CYNC_ACCOUNT_USERNAME: str = os.environ.get("CYNC_ACCOUNT_USERNAME", None)
CYNC_ACCOUNT_PASSWORD: str = os.environ.get("CYNC_ACCOUNT_PASSWORD", None)
CYNC_MQTT_CONN_DELAY: int = int(os.environ.get("CYNC_MQTT_CONN_DELAY", 10))
CYNC_CMD_BROADCASTS: int = int(os.environ.get("CYNC_CMD_BROADCASTS", 2))
CYNC_MAX_TCP_CONN: int = int(os.environ.get("CYNC_MAX_TCP_CONN", 8))
CYNC_TCP_WHITELIST: Optional[Union[str, List[Optional[str]]]] = os.environ.get("CYNC_TCP_WHITELIST")
CYNC_MQTT_HOST = os.environ.get("CYNC_MQTT_HOST", "homeassistant.local")
CYNC_MQTT_PORT = os.environ.get("CYNC_MQTT_PORT", 1883)
CYNC_MQTT_USER = os.environ.get("CYNC_MQTT_USER")
CYNC_MQTT_PASS = os.environ.get("CYNC_MQTT_PASS")
CYNC_TOPIC = os.environ.get("CYNC_TOPIC", "cync_lan_NEW")
CYNC_HASS_TOPIC = os.environ.get("CYNC_HASS_TOPIC", "homeassistant")
CYNC_HASS_STATUS_TOPIC = os.environ.get("CYNC_HASS_STATUS_TOPIC", "status")
CYNC_HASS_BIRTH_MSG = os.environ.get("CYNC_HASS_BIRTH_MSG", "online")
CYNC_HASS_WILL_MSG = os.environ.get("CYNC_HASS_WILL_MSG", "offline")
CYNC_RAW = os.environ.get("CYNC_RAW_DEBUG", "0").casefold() in YES_ANSWER
CYNC_DEBUG = os.environ.get("CYNC_DEBUG", "0").casefold() in YES_ANSWER

CYNC_BASE_DIR: str = "/root"
CYNC_STATIC_DIR: str = "/root/cync-lan/www"

PERSISTENT_BASE_DIR: str = "/homeassistant/.storage/cync-lan/config"
CYNC_CONFIG_FILE_PATH: str = f"{PERSISTENT_BASE_DIR}/cync_mesh.yaml"
CYNC_UUID_PATH: str = f"{PERSISTENT_BASE_DIR}/uuid.txt"

CYNC_CLOUD_AUTH_PATH: str = f"{CYNC_BASE_DIR}/cync-lan/.auth/.cloud_auth.yaml"
CYNC_SSL_CERT: str = os.environ.get("CYNC_DEVICE_CERT", f"{CYNC_BASE_DIR}/cync-lan/certs/cert.pem")
CYNC_SSL_KEY: str = os.environ.get("CYNC_DEVICE_KEY", f"{CYNC_BASE_DIR}/cync-lan/certs/key.pem")


CYNC_PORT = 23779
INGRESS_PORT = 23778
CYNC_CHUNK_SIZE = 2048
CYNC_ADDON_UUID: str = ""
CYNC_CORP_ID: str = "1007d2ad150c4000"
DATA_BOUNDARY = 0x7E
RAW_MSG = (
    " Set the CYNC_RAW_DEBUG env var to 1 to see the data" if CYNC_RAW is False else ""
)
ENABLE_EXPORTER: bool = False
if CYNC_TCP_WHITELIST:
    # split into a list using comma
    CYNC_TCP_WHITELIST = CYNC_TCP_WHITELIST.split(',')
    CYNC_TCP_WHITELIST = [x.strip() for x in CYNC_TCP_WHITELIST if x]

FACTORY_EFFECTS_BYTES: Dict[str, Tuple[int, int]] = {
            "candle": (int(0x01), int(0xF1)),
            "cyber": (int(0x43), int(0x9F)),
            "rainbow": (int(0x02), int(0x7A)),
            "fireworks": (int(0x3A), int(0xDA)),
            "volcanic": (int(0x04), int(0xF4)),
            "aurora": (int(0x05), int(0x1C)),
            "happy_holidays": (int(0x06), int(0x54)),
            "red_white_blue": (int(0x07), int(0x4F)),
            "vegas": (int(0x08), int(0xE3)),
            "party_time": (int(0x09), int(0x06)),
        }
