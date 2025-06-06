import logging
import struct
from typing import Optional, List, Tuple

from .const import *


logger = logging.getLogger(CYNC_LOG_NAME)

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
