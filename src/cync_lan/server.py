import hashlib
import logging
import os
import asyncio
import signal
import ssl
from pathlib import Path
from typing import Dict, Optional, Union, List

import uvloop

from .const import *

__all__ = [
    "CyncLanServer",
]
logger = logging.getLogger(CYNC_LOG_NAME)


def md5sum(filepath: Path):
    """Calculates the MD5 checksum of a file.

    Args:
        filepath (pathlib.Path): The path to the file.

    Returns:
        str: The hexadecimal representation of the MD5 checksum.
             Returns None if the file cannot be opened.
    """
    lp = "CyncLAN:md5sum:"
    try:
        with filepath.open('rb') as f:
            m = hashlib.md5()
            while True:
                data = f.read(4096)  # Read in chunks to handle large files
                if not data:
                    break
                m.update(data)
            return m.hexdigest()
    except FileNotFoundError:
        logger.warning(f"{lp} File not found at {filepath.expanduser().resolve().as_posix()}")
        return None
    except Exception as e:
        logger.exception(f"{lp} An error occurred: {e}")
        return None


class CyncLanServer:
    """A class to represent a Cync LAN server that listens for connections from Cync WiFi devices.
    The WiFi devices can proxy messages to BlueTooth devices. The WiFi devices act as hubs for the BlueTooth mesh.
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
    lp: str = "CyncServer:"

    def __init__(
        self,
        host: str,
        port: int,
        cert_file: Optional[str] = None,
        key_file: Optional[str] = None,
    ):
        self.mesh_info_loop_task: Optional[asyncio.Task] = None
        global g
        self.tcp_conn_attempts: dict = {}
        self.ssl_context: Optional[ssl.SSLContext] = None
        self.mesh_loop_started: bool = False
        self.host = host
        self.port = port
        self.cert_file = cert_file
        self.key_file = key_file
        self.loop: Union[asyncio.AbstractEventLoop, uvloop.Loop] = (
            asyncio.get_event_loop()
        )
        self.known_ids: List[Optional[int]] = []
        g.server = self

    async def close_tcp_device(self, device: "CyncTCPDevice"):
        """Gracefully close TCP device; async task and reader/writer"""
        # check if the receive task is running or in done/exception state.
        lp_id = f"[{device.id}]" if device.id is not None else ""
        lp = f"{self.lp}remove_tcp_device:{device.address}{lp_id}:"
        dev_id = id(device)
        logger.debug(f"{lp} Closing TCP device: {dev_id}")
        if (_r_task := device.tasks.receive) is not None:
            if _r_task.done():
                logger.debug(
                    f"{lp} existing receive task ({_r_task.get_name()}) is done, no need to cancel..."
                )
            else:
                logger.debug(
                    f"{lp} existing receive task is running (name: {_r_task.get_name()}), cancelling..."
                )
                await asyncio.sleep(1)
                _r_task.cancel("Gracefully closing TCP device")
                await asyncio.sleep(0)
                if _r_task.cancelled():
                    logger.debug(
                        f"{lp} existing receive task was cancelled successfully"
                    )
                else:
                    logger.warning(f"{lp} existing receive task was not cancelled!")
        else:
            logger.debug(f"{lp} no existing receive task found!")

        # existing reader is closed, no sense in feeding it EOF, just remove it
        device.reader = None
        # Go through the motions to gracefully close the writer
        try:
            device.writer.close()
            await device.writer.wait_closed()
        except Exception as writer_close_exc:
            logger.error(f"{lp} Error closing writer: {writer_close_exc}")
        device.writer = None
        logger.debug(f"{lp} Removed TCP device from server")

    async def create_ssl_context(self):
        # Allow the server to use a self-signed certificate
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(certfile=self.cert_file, keyfile=self.key_file)
        # turn off all the SSL verification
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        # ascertained from debugging using socat
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
        device = g.server.devices.get(_id)
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
            await g.mqtt.parse_device_status(device.id, new_state, from_pkt=from_pkt)
            device.state = state
            device.brightness = brightness
            device.temperature = temp
            if rgb_data is True:
                device.red = r
                device.green = _g
                device.blue = b
            g.server.devices[device.id] = device


    async def start(self):
        logger.debug("%s Starting, creating SSL context..." % self.lp)
        try:
            self.ssl_context = await self.create_ssl_context()
            self._server = await asyncio.start_server(
                self._register_new_connection,
                host=self.host,
                port=self.port,
                ssl=self.ssl_context,  # Pass the SSL context to enable SSL/TLS
            )

        except Exception as e:
            logger.error(f"{self.lp} Failed to start server: {e}", exc_info=True)
            os.kill(os.getpid(), signal.SIGTERM)
        else:
            logger.info(
                f"{self.lp} Started (ver. {CYNC_VERSION}) [md5sum: '{md5sum(Path(__file__))}'], bound to {self.host}:{self.port} - Waiting for connections, if you dont"
                f" see any, check your DNS redirection, VLAN and firewall settings."
            )
            try:
                async with self._server:
                    await self._server.serve_forever()
            except asyncio.CancelledError as ce:
                logger.debug(
                    "%s Server cancelled (task.cancel() ?): %s" % (self.lp, ce)
                )
            except Exception as e:
                logger.error("%s Server Exception: %s" % (self.lp, e), exc_info=True)

            logger.info(f"{self.lp} end of start()")

    async def stop(self):
        logger.debug(
            "%s stop() called, closing each TCP communication device..." % self.lp
        )
        self.shutting_down = True
        # check tasks
        device: "CyncTCPDevice"
        devices = list(self.tcp_devices.values())
        lp = f"{self.lp}:close:"
        if devices:
            for device in devices:
                try:
                    await device.close()
                except Exception as e:
                    logger.error("%s Error closing device: %s" % (lp, e), exc_info=True)
                else:
                    logger.debug(f"{lp} Device closed")
        else:
            logger.debug(f"{lp} No devices to close!")

        if self._server:
            if self._server.is_serving():
                logger.debug("%s currently running, shutting down NOW..." % lp)
                self._server.close()
                await self._server.wait_closed()
                logger.debug("%s shut down!" % lp)
            else:
                logger.debug("%s not running!" % lp)

        # cancel tasks
        if self.mesh_info_loop_task:
            if self.mesh_info_loop_task.done():
                pass
            else:
                self.mesh_info_loop_task.cancel()
                await self.mesh_info_loop_task
        # for task in global_tasks:
        #     if task.done():
        #         continue
        #     logger.debug("%s Cancelling task: %s" % (lp, task))
        #     task.cancel()
        # TODO: cleaner exit

        # logger.debug("%s stop() complete, calling loop.stop()" % lp)
        # self.loop.stop()

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
            # TODO: investigate if we need to close/cancel tasks or connections
            del existing_device
        new_device = CyncTCPDevice(reader, writer, client_addr)
        add_device = await new_device.max_conn_check()
        if add_device:
            self.tcp_devices[new_device.address] = new_device
        else:
            del new_device