import os
from typing import Optional, List, Union
import zoneinfo

import tzlocal

from . import __version__

__all__ = [
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
    "CYNC_MQTT_URL",
    "CYNC_MQTT_HOST",
    "CYNC_MQTT_PORT",
    "CYNC_MQTT_USER",
    "CYNC_MQTT_PASS",
    "CYNC_CERT",
    "CYNC_KEY",
    "CYNC_TOPIC",
    "CYNC_HASS_TOPIC",
    "CYNC_HASS_STATUS_TOPIC",
    "CYNC_HASS_BIRTH_MSG",
    "CYNC_HASS_WILL_MSG",
    "CYNC_PORT",
    "CYNC_HOST",
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
CYNC_ACCOUNT_LANGUAGE: str = os.environ.get("CYNC_ACCOUNT_LANGUAGE", "en-us").casefold()
CYNC_ACCOUNT_USERNAME: str = os.environ.get("CYNC_ACCOUNT_USERNAME", None)
CYNC_ACCOUNT_PASSWORD: str = os.environ.get("CYNC_ACCOUNT_PASSWORD", None)
LOCAL_TZ = zoneinfo.ZoneInfo(str(tzlocal.get_localzone()))
CYNC_LOG_NAME: str = "cync_lan"
CYNC_VERSION: str = __version__
SRC_REPO_URL: str = "https://github.com/baudneo/cync-lan"
DEVICE_LWT_MSG: bytes = b"offline"
CYNC_MQTT_CONN_DELAY: int = int(os.environ.get("CYNC_MQTT_CONN_DELAY", 10))
CYNC_CMD_BROADCASTS: int = int(os.environ.get("CYNC_CMD_BROADCASTS", 2))
CYNC_MAX_TCP_CONN: int = int(os.environ.get("CYNC_MAX_TCP_CONN", 8))
CYNC_TCP_WHITELIST: Optional[Union[str, List[Optional[str]]]] = os.environ.get("CYNC_TCP_WHITELIST")
CYNC_API_BASE: str = "https://api.gelighting.com/v2/"
CYNC_MQTT_URL = os.environ.get("CYNC_MQTT_URL")
CYNC_MQTT_HOST = os.environ.get("CYNC_MQTT_HOST", "homeassistant.local")
CYNC_MQTT_PORT = os.environ.get("CYNC_MQTT_PORT", 1883)
CYNC_MQTT_USER = os.environ.get("CYNC_MQTT_USER")
CYNC_MQTT_PASS = os.environ.get("CYNC_MQTT_PASS")
CYNC_CERT = os.environ.get("CYNC_CERT", "certs/cert.pem")
CYNC_KEY = os.environ.get("CYNC_KEY", "certs/key.pem")
CYNC_TOPIC = os.environ.get("CYNC_TOPIC", "cync_lan")
CYNC_HASS_TOPIC = os.environ.get("CYNC_HASS_TOPIC", "homeassistant")
CYNC_HASS_STATUS_TOPIC = os.environ.get("CYNC_HASS_STATUS_TOPIC", "status")
CYNC_HASS_BIRTH_MSG = os.environ.get("CYNC_HASS_BIRTH_MSG", "online")
CYNC_HASS_WILL_MSG = os.environ.get("CYNC_HASS_WILL_MSG", "offline")
CYNC_PORT = os.environ.get("CYNC_PORT", 23779)
CYNC_HOST = os.environ.get("CYNC_HOST", "0.0.0.0")
CYNC_CHUNK_SIZE = os.environ.get("CYNC_CHUNK_SIZE", 2048)
YES_ANSWER = ("true", "1", "yes", "y", "t", 1)
CYNC_RAW = os.environ.get("CYNC_RAW_DEBUG", "0").casefold() in YES_ANSWER
CYNC_DEBUG = os.environ.get("CYNC_DEBUG", "0").casefold() in YES_ANSWER
CYNC_ADDON_UUID: str = ""
if CYNC_TCP_WHITELIST:
    # split into a list using comma
    CYNC_TCP_WHITELIST = CYNC_TCP_WHITELIST.split(',')
    CYNC_TCP_WHITELIST = [x.strip() for x in CYNC_TCP_WHITELIST if x]

CYNC_CORP_ID: str = "1007d2ad150c4000"
DATA_BOUNDARY = 0x7E
RAW_MSG = (
    " Set the CYNC_RAW_DEBUG env var to 1 to see the data" if CYNC_RAW is False else ""
)

CYNC_CONFIG_FILE_PATH: str = "/root/cync-lan/config/cync_mesh.yaml"
CYNC_CLOUD_AUTH_PATH: str = "/root/cync-lan/var/.cloud_auth.yaml"

FACTORY_EFFECTS_BYTES = {
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