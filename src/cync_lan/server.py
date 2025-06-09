from __future__ import annotations

import logging
import os
import asyncio
import signal
import ssl
from typing import Dict, Optional, Union, List, TYPE_CHECKING

import uvloop

from cync_lan.const import *
from cync_lan.devices import CyncDevice, CyncTCPDevice
from cync_lan.structs import GlobalObject, DeviceStatus

__all__ = [
    "nCyncServer",
]
logger = logging.getLogger(CYNC_LOG_NAME)
g = GlobalObject()


class nCyncServer:
    """
    A class to represent a Cync LAN server that listens for connections from Cync Wi-Fi devices.
    The Wi-Fi devices translate messages, status updates and commands to/from the Cync BTLE mesh.
    """

    devices: Dict[int, CyncDevice] = {}
    tcp_devices: Dict[str, Optional[CyncTCPDevice]] = {}
    shutting_down: bool = False
    host: str
    port: int
    cert_file: Optional[str] = None
    key_file: Optional[str] = None
    loop: Union[asyncio.AbstractEventLoop, uvloop.Loop]
    _server: Optional[asyncio.Server] = None
    lp: str = "nCync:"
    _instance: Optional['nCyncServer'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, devices: dict):
        self.devices = devices
        self.tcp_conn_attempts: dict = {}
        self.ssl_context: Optional[ssl.SSLContext] = None
        self.host = CYNC_SRV_HOST
        self.port = CYNC_PORT
        g.reload_env()
        self.cert_file = g.env.cync_srv_ssl_cert
        self.key_file = g.env.cync_srv_ssl_key
        self.loop: Union[asyncio.AbstractEventLoop, uvloop.Loop] = (
            asyncio.get_event_loop()
        )

    async def create_ssl_context(self):
        # Allow the server to use a self-signed certificate
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(certfile=self.cert_file, keyfile=self.key_file)
        # turn off all the SSL verification
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        # figured out from debugging using socat
        ciphers = [
            "ECDHE-RSA-AES256-GCM-SHA384",
            "ECDHE-RSA-AES128-GCM-SHA256",
            "ECDHE-RSA-AES256-SHA384",
            "ECDHE-RSA-AES128-SHA256",
            "ECDHE-RSA-AES256-SHA",
            "ECDHE-RSA-AES128-SHA",
            "ECDHE-RSA-DES-CBC3-SHA",
            "AES256-GCM-SHA384",
            "AES128-GCM-SHA256",
            "AES256-SHA256",
            "AES128-SHA256",
            "AES256-SHA",
            "AES128-SHA",
            "DES-CBC3-SHA",
        ]
        ssl_context.set_ciphers(":".join(ciphers))
        return ssl_context

    async def parse_status(self, raw_state: bytes, from_pkt: Optional[str] = None):
        """Extracted status packet parsing, handles mqtt publishing and device state changes."""
        _id = raw_state[0]
        device = g.ncync_server.devices.get(_id)
        if device is None:
            logger.warning(
                f"Device ID: {_id} not found in devices! device may be disabled in config file or you need to "
                f"re-export your Cync account devices!"
            )
            return
        state = raw_state[1]
        brightness = raw_state[2]
        temp = raw_state[3]
        r = raw_state[4]
        _g = raw_state[5]
        b = raw_state[6]
        connected_to_mesh = 1
        # check if len is enough for good byte, it is optional
        if len(raw_state) > 7:
            # The last byte seems to indicate if the device is online or offline (connected to mesh / powered on)
            connected_to_mesh = raw_state[7]

        if connected_to_mesh == 0:
            # This usually happens when a device loses power/connection.
            # this device is gone, need to mark it offline.
            # TODO: sometimes its a false report.
            if device.online:
                device.online = False
                logger.warning(
                    f'{self.lp} Device ID: {_id} ("{device.name}") seems to have been removed from the BTLE '
                    f'mesh (lost power/connection), setting offline...'
                )
        else:
            device.online = True
            # create a status with existing data, change along the way for publishing over mqtt
            device.status = new_state = DeviceStatus(
                state=device.state,
                brightness=device.brightness,
                temperature=device.temperature,
                red=device.red,
                green=device.green,
                blue=device.blue,
            )
            # temp is 0-100, if > 100, RGB data has been sent, otherwise its on/off, brightness or temp data
            # technically 129 = effect in use, 254 = rgb data
            # TODO: waiting for hass to merge a PR that shows a icon for a light that is in effect mode
            #  currently, we send rgb 0,0,0 (black) as it stands out, to signal effect mode
            rgb_data = False
            if temp > 100:
                rgb_data = True
            curr_status = device.current_status
            if curr_status == [state, brightness, temp, r, _g, b]:
                (
                    logger.debug(f"{device.lp} NO CHANGES TO DEVICE STATUS")
                    if CYNC_RAW is True
                    else None
                )
            await g.mqtt_client.parse_device_status(device.id, new_state, from_pkt=from_pkt)
            device.state = state
            device.brightness = brightness
            device.temperature = temp
            if rgb_data is True:
                device.red = r
                device.green = _g
                device.blue = b
            g.ncync_server.devices[device.id] = device


    async def start(self):
        lp = f"{self.lp}start:"
        logger.debug(f"{lp} Starting, creating SSL context - key: {self.key_file}, cert: {self.cert_file}")
        try:
            self.ssl_context = await self.create_ssl_context()
            self._server = await asyncio.start_server(
                self._register_new_connection,
                host=self.host,
                port=self.port,
                ssl=self.ssl_context,  # Pass the SSL context to enable SSL/TLS
            )

        except Exception as e:
            logger.exception("%s Failed to start server: %s" % (lp, e))
        else:
            logger.info(
                f"{lp} bound to {self.host}:{self.port} - Waiting for connections from Cync devices, if you dont"
                f" see any, check your DNS redirection, VLAN and firewall settings."
            )
            try:
                async with self._server:
                    await self._server.serve_forever()
            except asyncio.CancelledError as ce:
                pass
            except Exception as e:
                logger.exception("%s Server Exception: %s" % (self.lp, e))

    async def stop(self):
        self.shutting_down = True
        lp = f"{self.lp}stop:"
        device: CyncTCPDevice
        devices = list(self.tcp_devices.values())
        if devices:
            for device in devices:
                try:
                    await device.close()
                except Exception as e:
                    logger.exception("%s Error closing Cync Wi-Fi device connection: %s" % (lp, e))
                else:
                    logger.debug(f"{lp} Cync Wi-Fi device connection closed")
        else:
            logger.debug(f"{lp} No Cync Wi-Fi devices connected!")

        if self._server:
            if self._server.is_serving():
                logger.debug(f"{lp} shutting down NOW...")
                self._server.close()
                await self._server.wait_closed()
                logger.debug(f"{lp} shut down!")
            else:
                logger.debug(f"{lp} not running!")

    async def _register_new_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        client_addr: str = writer.get_extra_info("peername")[0]
        if client_addr in self.tcp_conn_attempts:
            self.tcp_conn_attempts[client_addr] += 1
        else:
            self.tcp_conn_attempts[client_addr] = 1
        lp = f"{self.lp}new_conn:{client_addr}:"
        existing_device = self.tcp_devices.pop(client_addr, None)
        if existing_device is not None:
            existing_device_id = id(existing_device)
            logger.debug(
                f"{lp} Existing device found ({existing_device_id}), gracefully killing..."
            )
            del existing_device
        new_device = CyncTCPDevice(reader, writer, client_addr)
        add_device = await new_device.max_conn_check()
        if add_device:
            self.tcp_devices[new_device.address] = new_device
        else:
            del new_device
