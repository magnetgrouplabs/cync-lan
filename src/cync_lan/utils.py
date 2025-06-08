from __future__ import annotations

import hashlib
import logging
import os
import signal
import struct
from pathlib import Path
from typing import Optional, List, Tuple

from cync_lan.const import *

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
