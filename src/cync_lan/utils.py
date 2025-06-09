from __future__ import annotations

import argparse
import asyncio
import datetime
import hashlib
import logging
import os
import signal
import struct
import sys
import uuid
from pathlib import Path
from typing import Optional, List, Tuple

import yaml

from cync_lan.const import *
from cync_lan.const import CYNC_UUID_PATH, LOCAL_TZ
from cync_lan.devices import CyncDevice
from cync_lan.main import logger, g

logger = logging.getLogger(CYNC_LOG_NAME)

def send_signal(signal_num: int):
    """
    Send a signal to the current process.

    Args:
        signal_num (int): The signal number to send.
    """
    try:
        os.kill(os.getpid(), signal_num)
    except OSError as e:
        logger.error(f"Failed to send signal {signal_num}: {e}")
        raise e

def send_sigint():
    """
    Send a SIGINT signal to the current process.
    This is typically used to gracefully shut down the application.
    """
    send_signal(signal.SIGINT)

def send_sigterm():
    """
    Send a SIGTERM signal to the current process.
    This is typically used to request termination of the application.
    """
    send_signal(signal.SIGTERM)

def bytes2list(byte_string: bytes) -> List[int]:
    """Convert a byte string to a list of integers"""
    # Interpret the byte string as a sequence of unsigned integers (little-endian)
    int_list = struct.unpack("<" + "B" * (len(byte_string)), byte_string)
    return list(int_list)


def hex2list(hex_string: str) -> List[int]:
    """Convert a hex string to a list of integers"""
    x = bytes().fromhex(hex_string)
    return bytes2list(x)


def ints2hex(ints: List[int]) -> str:
    """Convert a list of integers to a hex string"""
    return bytes(ints).hex(" ")


def ints2bytes(ints: List[int]) -> bytes:
    """Convert a list of integers to a byte string"""
    return bytes(ints)


def parse_unbound_firmware_version(
    data_struct: bytes, lp: str
) -> Optional[Tuple[str, int, str]]:
    """Parse the firmware version from binary hex data. Unbound means not bound by 0x7E boundaries"""
    # LED controller sends this data after cync app connects via BTLE
    # 1f 00 00 00 fa 8e 14 00 50 22 33 08 00 ff ff ea 11 02 08 a1 [01 03 01 00 00 00 00 00 f8
    lp = f"{lp}firmware_version:"
    if data_struct[0] != 0x00:
        logger.error(
            f"{lp} Invalid first byte value: {data_struct[0]} should be 0x00 for firmware version data"
        )

    n_idx = 20  # Starting index for firmware information
    firmware_type = "device" if data_struct[n_idx + 2] == 0x01 else "network"
    n_idx += 3

    firmware_version = []
    try:
        while len(firmware_version) < 5 and data_struct[n_idx] != 0x00:
            firmware_version.append(int(chr(data_struct[n_idx])))
            n_idx += 1
        if not firmware_version:
            logger.warning(
                f"{lp} No firmware version found in packet: {data_struct.hex(' ')}"
            )
            return None
            # network firmware (this one is set to ascii 0 (0x30))
            # 00 00 00 00 00 fa 00 20 00 00 00 00 00 00 00 00
            # ea 00 00 00 86 01 00 30 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 c1 7e

    except (IndexError, ValueError) as e:
        logger.error(f"{lp} Exception occurred while parsing firmware version: {e}")
        return None

    else:
        if firmware_type == "device":
            firmware_str = f"{firmware_version[0]}.{firmware_version[1]}.{''.join(map(str, firmware_version[2:]))}"
        else:
            firmware_str = "".join(map(str, firmware_version))
        firmware_version_int = int("".join(map(str, firmware_version)))
        logger.debug(
            f"{lp} {firmware_type} firmware VERSION: {firmware_version_int} ({firmware_str})"
        )

    return firmware_type, firmware_version_int, firmware_str


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


def signal_handler(signum) -> None:
    """
    Handle signals for graceful shutdown.
    """
    global SHUTTING_DOWN

    _msg = "shutting down..." if SHUTTING_DOWN is False else "already shutting down!"
    logger.info(f"CyncLAN: Intercepted signal: {signal.Signals(signum).name} ({signum}), {_msg}")
    if SHUTTING_DOWN is False:
        SHUTTING_DOWN = True
        if g:
            # instead of calling self.close(), which would add the close tasks to global_tasks
            # we call stop() on the services directly, and cancel the self.start() tasks
            # crucial to stop the MQTT connection retry loop
            tasks = []
            if g.ncync_server:
                tasks.append(g.ncync_server.stop())
            if g.mqtt_client:
                tasks.append(g.mqtt_client.stop())
            if g.export_server:
                tasks.append(g.export_server.stop())
            if g.cloud_api:
                tasks.append(g.cloud_api.close())
            if tasks:
                asyncio.gather(*tasks, return_exceptions=True)
            # cancel all not-done global_tasks (start and stop tasks)
            if g.loop:
                for task in g.tasks:
                    if not task.done():
                        # logger.debug(f"CyncLAN: Cancelling task: {task.get_name()}")
                        task.cancel()
            g.tasks.clear()


async def parse_config(cfg_file: Path):
    """Parse the exported Cync config file and create devices from it.

    Exported config created by scraping cloud API. Devices must already be added to your Cync account.
    If you add new or delete existing devices, you will need to re-export the config.
    """
    lp = f"parse_config:"
    logger.debug(f"{lp} reading devices from Cync config file: {cfg_file.as_posix()}")
    try:
        # wrap synchronous yaml reading in an async function to avoid blocking the event loop
        # raw_config = yaml.safe_load(cfg_file.read_text())
        # get an executor
        raw_config = await asyncio.get_event_loop().run_in_executor(
            None, yaml.safe_load, cfg_file.read_text(encoding="utf-8")
        )

    except Exception as e:
        logger.error(f"{lp} Error reading config file: {e}", exc_info=True)
        raise e

    devices = {}
    # parse homes and devices
    for cync_home_name, home_cfg in raw_config["account data"].items():
        home_id = home_cfg["id"]
        if "devices" not in home_cfg:
            logger.warning(
                f"{lp} No devices found in config for: {cync_home_name} (ID: {home_id}), skipping..."
            )
            continue
        # Create devices
        for cync_id, cync_device in home_cfg["devices"].items():
            cync_device: dict
            device_name = (
                cync_device["name"]
                if "name" in cync_device
                else f"device_{cync_id}"
            )
            if "enabled" in cync_device:
                if cync_device["enabled"] is False:
                    logger.debug(
                        f"{lp} Device '{device_name}' (ID: {cync_id}) is disabled in config, skipping..."
                    )
                    continue
            fw_version = cync_device["fw"] if "fw" in cync_device else None
            wmac = None
            btmac = None
            # 'mac': 26616350814, 'wifi_mac': 26616350815
            if 'mac' in cync_device:
                btmac = cync_device['mac']
                if btmac:
                    if isinstance(btmac, int):
                        logger.warning(f"IMPORTANT>>> cync device '{device_name}' (ID: {cync_id}) 'mac' is somehow an int -> {btmac}, please quote the mac address to force it to a string in the config file")

            if 'wifi_mac' in cync_device:
                wmac = cync_device['wifi_mac']
                if wmac:
                    if isinstance(wmac, int):
                        logger.debug(f"IMPORTANT>>> cync device '{device_name}' (ID: {cync_id}) 'wifi_mac' is somehow an int -> {wmac}, please quote the mac address to force it to a string in the config file")

            new_device = CyncDevice(
                name=device_name,
                cync_id=cync_id,
                fw_version=fw_version,
                home_id=home_id,
                mac=btmac,
                wifi_mac=wmac,
            )
            for attrset in (
                "is_plug",
                "supports_temperature",
                "supports_rgb",
                "ip",
                "type",
            ):
                if attrset in cync_device:
                    setattr(new_device, attrset, cync_device[attrset])
            devices[cync_id] = new_device
            # logger.debug(f"{lp} Created device (hass_id: {new_device.hass_id}) (home_id: {new_device.home_id}) (device_id: {new_device.id}): {new_device}")

    return devices


def check_python_version():
    if sys.version_info >= (3, 9):
        pass
    else:
        sys.exit(
            "Python version 3.9 or higher REQUIRED! you have version: %s" % sys.version
        )


def parse_cli():

    parser = argparse.ArgumentParser(description="Cync LAN Server")
    parser.add_argument(
    "--export-server",
        "--enable-export-server",
        action="store_true",
        dest="export_server",
        help="Enable the Cync Export Server",
    )

    parser.add_argument(
        "-D",
        "--debug",
        action="store_true",
        help="Enable debug mode",
    )
    parser.add_argument(
    "--env",
        help="Path to the environment file",
        default=None,
        type=Path
    )
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled via CLI argument")
    if args.export_server:
        global ENABLE_EXPORTER

        logger.info("Export server enabled via CLI argument")
        ENABLE_EXPORTER = True
    if args.env:
        env_path = args.env
        env_path = env_path.expanduser().resolve()
        try:
            import dotenv
            loaded_any = dotenv.load_dotenv(env_path, override=True)
        except ImportError:
            logger.error("dotenv module is not installed. Please install it with 'pip install python-dotenv'")
        except Exception as e:
            logger.error(f"Failed to read environment file {env_path}: {e}")
        else:
            if not env_path.exists():
                logger.error(f"Environment file {env_path} does not exist")
            if loaded_any:
                logger.info(f"Environment variables loaded from {env_path}")
                g.reload_env()
            else:
                logger.warning(f"No environment variables were loaded from {env_path}")


def is_first_run():
    """Check if this is the first run of the Cync LAN server, if so, create the CYNC_ADDON_UUID (UUID4)"""
    lp = f"is_first_run:"
    uuid_file = Path(CYNC_UUID_PATH).expanduser().resolve()

    def write_uuid_to_disk(uuid_str: str):
        with open(uuid_file, "w") as f:
            f.write(uuid_str)
        logger.info(f"{lp} UUID ({uuid_str}) written to disk: {uuid_file.as_posix()}")

    uuid_from_disk = ""
    create_uuid = False
    try:
        if uuid_file.exists():
            with uuid_file.open("r") as f:
                uuid_from_disk = f.read().strip()
            if not uuid_from_disk:
                create_uuid = True
            else:
                # check that it is a valid uuid4
                uuid_obj = uuid.UUID(uuid_from_disk)
                if uuid_obj.version != 4:
                    logger.warning(f"{lp} Invalid UUID version in uuid.txt: {uuid_from_disk}")
                    create_uuid = True
        else:
            logger.info(f"{lp} No uuid.txt found in {uuid_file.parent.as_posix()}")
            create_uuid = True
    except PermissionError:
        logger.error(f"{lp} PermissionError: Unable to read/write {CYNC_UUID_PATH}. Please check permissions.")
        create_uuid = True
    if create_uuid:
        global CYNC_ADDON_UUID

        logger.debug(f"{lp} Creating a new UUID to be used for the 'CyncLAN Controller/Bridge' device")
        CYNC_ADDON_UUID = str(uuid.uuid4())
        write_uuid_to_disk(CYNC_ADDON_UUID)


def utc_to_local(utc_dt: datetime.datetime) -> datetime.datetime:
    # local_tz = zoneinfo.ZoneInfo(str(tzlocal.get_localzone()))
    # utc_time = datetime.datetime.now(datetime.UTC)
    local_time = utc_dt.astimezone(LOCAL_TZ)
    return local_time
