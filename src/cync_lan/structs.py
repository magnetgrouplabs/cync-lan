from __future__ import annotations

import asyncio
import logging
import time
from typing import Union, Optional, List, Coroutine, Dict, Tuple, TYPE_CHECKING

import aiohttp
import uvloop
from pydantic import BaseModel, ConfigDict
from pydantic.dataclasses import dataclass

from cync_lan.const import *

if TYPE_CHECKING:
    from cync_lan.exporter import ExportServer
    from cync_lan.mqtt_client import MQTTClient
    from cync_lan.server import CyncLanServer

logger = logging.getLogger(CYNC_LOG_NAME)

class GlobalObject:
    cync_lan_server: Optional[CyncLanServer] = None
    mqtt_client: Optional[MQTTClient] = None
    http_session: Optional[aiohttp.ClientSession] = None
    loop: Union[uvloop.Loop, asyncio.AbstractEventLoop, None] = None
    export_server: Optional[ExportServer] = None

    _instance: Optional['GlobalObject'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance


@dataclass(config=ConfigDict(arbitrary_types_allowed=True))
class Tasks:
    receive: Optional[asyncio.Task] = None
    send: Optional[asyncio.Task] = None
    callback_cleanup: Optional[asyncio.Task] = None

    def __iter__(self):
        return iter([self.receive, self.send, self.callback_cleanup])


class ControlMessageCallback:
    id: int
    message: Union[None, str, bytes, List[int]] = None
    sent_at: Optional[float] = None
    callback: Optional[Union[asyncio.Task, Coroutine]] = None

    def __init__(self, msg_id: int, message: Union[None, str, bytes, List[int]], sent_at: float, callback: Union[asyncio.Task, Coroutine]):
        self.id = msg_id
        self.message = message
        self.sent_at = sent_at
        self.callback = callback
        self.lp = f"CtrlMessageCallback:{self.id}:"

    @property
    def elapsed(self) -> float:
        return time.time() - self.sent_at

    def __str__(self):
        return f"CtrlMessageCallback ID: {self.id} elapsed: {self.elapsed:.5f}s"

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other: int):
        return self.id == other

    def __hash__(self):
        return hash(self.id)

    def __call__(self):
        if self.callback:
            return self.callback
        else:
            logger.debug(f"{self.lp} No callback set, skipping...")
            return None


class Messages:
    control: Dict[int, ControlMessageCallback]

    def __init__(self):
        self.control = dict()


@dataclass
class CacheData:
    all_data: bytes = b""
    timestamp: float = 0
    data: bytes = b""
    data_len: int = 0
    needed_len: int = 0


class DeviceStatus(BaseModel):
    """
    A class that represents a Cync devices status.
    This may need to be changed as new devices are bought and added.
    """
    state: Optional[int] = None
    brightness: Optional[int] = None
    temperature: Optional[int] = None
    red: Optional[int] = None
    green: Optional[int] = None
    blue: Optional[int] = None


@dataclass
class MeshInfo:
    status: List[Optional[List[Optional[int]]]]
    id_from: int


class PhoneAppStructs:
    def __iter__(self):
        return iter([self.requests, self.responses])
    @dataclass
    class AppRequests:
        auth_header: Tuple[int] = (0x13, 0x00, 0x00, 0x00)
        connect_header: Tuple[int] = (0xA3, 0x00, 0x00, 0x00)
        headers: Tuple[int] = (0x13, 0xA3)

        def __iter__(self):
            return iter(self.headers)

    @dataclass
    class AppResponses:
        auth_resp: Tuple[int] = (0x18, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00)
        headers: Tuple[int] = (0x18)

        def __iter__(self):
            return iter(self.headers)

    requests: AppRequests = AppRequests()
    responses: AppResponses = AppResponses()
    headers = (0x13, 0xA3, 0x18)


class DeviceStructs:
    def __iter__(self):
        return iter([self.requests, self.responses])

    @dataclass
    class DeviceRequests:
        """These are packets devices send to the server"""

        x23: Tuple[int] = tuple([0x23])
        xc3: Tuple[int] = tuple([0xC3])
        xd3: Tuple[int] = tuple([0xD3])
        x83: Tuple[int] = tuple([0x83])
        x73: Tuple[int] = tuple([0x73])
        x7b: Tuple[int] = tuple([0x7B])
        x43: Tuple[int] = tuple([0x43])
        xa3: Tuple[int] = tuple([0xA3])
        xab: Tuple[int] = tuple([0xAB])
        headers: Tuple[int] = (0x23, 0xC3, 0xD3, 0x83, 0x73, 0x7B, 0x43, 0xA3, 0xAB)

        def __iter__(self):
            return iter(self.headers)

    @dataclass
    class DeviceResponses:
        """These are the packets the server sends to the device"""

        auth_ack: Tuple[int] = (0x28, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00)
        # TODO: figure out correct bytes for this
        connection_ack: Tuple[int] = (
            0xC8,
            0x00,
            0x00,
            0x00,
            0x0B,
            0x0D,
            0x07,
            0xE8,
            0x03,
            0x0A,
            0x01,
            0x0C,
            0x04,
            0x1F,
            0xFE,
            0x0C,
        )
        x48_ack: Tuple[int] = (0x48, 0x00, 0x00, 0x00, 0x03, 0x01, 0x01, 0x00)
        x88_ack: Tuple[int] = (0x88, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00)
        ping_ack: Tuple[int] = (0xD8, 0x00, 0x00, 0x00, 0x00)
        x78_base: Tuple[int] = (0x78, 0x00, 0x00, 0x00)
        x7b_base: Tuple[int] = (0x7B, 0x00, 0x00, 0x00, 0x07)

    requests: DeviceRequests = DeviceRequests()
    responses: DeviceResponses = DeviceResponses()
    headers: Tuple[int] = (0x23, 0xC3, 0xD3, 0x83, 0x73, 0x7B, 0x43, 0xA3, 0xAB)

    @staticmethod
    def xab_generate_ack(queue_id: bytes, msg_id: bytes):
        """
        Respond to a 0xAB packet from the device, needs queue_id and msg_id to reply with.
        Has ascii 'xlink_dev' in reply
        """
        _x = bytes([0xAB, 0x00, 0x00, 0x03])
        hex_str = (
            "78 6c 69 6e 6b 5f 64 65 76 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "e3 4f 02 10"
        )
        dlen = (
            len(queue_id) + len(msg_id) + len(bytes.fromhex(hex_str.replace(" ", "")))
        )
        _x += bytes([dlen])
        _x += queue_id
        _x += msg_id
        _x += bytes().fromhex(hex_str)
        return _x

    @staticmethod
    def x88_generate_ack(msg_id: bytes):
        """Respond to a 0x83 packet from the device, needs a msg_id to reply with"""
        _x = bytes([0x88, 0x00, 0x00, 0x00, 0x03])
        _x += msg_id
        return _x

    @staticmethod
    def x48_generate_ack(msg_id: bytes):
        """Respond to a 0x43 packet from the device, needs a queue and msg id to reply with"""
        # set last msg_id digit to 0
        msg_id = msg_id[:-1] + b"\x00"
        _x = bytes([0x48, 0x00, 0x00, 0x00, 0x03])
        _x += msg_id
        return _x

    @staticmethod
    def x7b_generate_ack(queue_id: bytes, msg_id: bytes):
        """
        Respond to a 0x73 packet from the device, needs a queue and msg id to reply with.
        This is also called for 0x83 packets AFTER seeing a 0x73 packet.
        Not sure of the intricacies yet, seems to be bound to certain queue ids.
        """
        _x = bytes([0x7B, 0x00, 0x00, 0x00, 0x07])
        _x += queue_id
        _x += msg_id
        return _x


APP_HEADERS = PhoneAppStructs()
DEVICE_STRUCTS = DeviceStructs()
ALL_HEADERS = list(DEVICE_STRUCTS.headers) + list(APP_HEADERS.headers)
