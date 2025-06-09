import asyncio
import logging
import os
import signal
import sys
from functools import partial
from pathlib import Path
from typing import Optional

import uvloop

from cync_lan.cloud_api import CyncCloudAPI
from cync_lan.const import *
from cync_lan.exporter import ExportServer
from cync_lan.mqtt_client import MQTTClient
from cync_lan.server import nCyncServer
from cync_lan.structs import GlobalObject
from cync_lan.utils import signal_handler, parse_config, check_python_version, parse_cli, is_first_run

logger = logging.getLogger(CYNC_LOG_NAME)
formatter = logging.Formatter(
    "%(asctime)s.%(msecs)d %(levelname)s [%(module)s:%(lineno)d] > %(message)s",
    "%m/%d/%y %H:%M:%S",
)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

g = GlobalObject()

class CyncLAN:
    lp: str = "CyncLAN:"
    _instance: Optional['CyncLAN'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        lp = f"{self.lp}init:"
        is_first_run()
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        g.loop = asyncio.get_event_loop()
        logger.debug(f"{lp} CyncLAN (version: {CYNC_VERSION}) stack initializing, setting up event loop signal handlers...")
        g.loop.add_signal_handler(signal.SIGINT, partial(signal_handler, signal.SIGINT))
        g.loop.add_signal_handler(signal.SIGTERM, partial(signal_handler, signal.SIGTERM))

    async def start(self):
        """Start the Cync LAN server, MQTT client, and Export server."""
        lp = f"{self.lp}start:"
        cfg_file = Path(CYNC_CONFIG_FILE_PATH).expanduser().resolve()
        tasks = []
        if cfg_file.exists():
            g.ncync_server = nCyncServer(await parse_config(cfg_file))
            tasks.append(asyncio.Task(g.ncync_server.start(), name="CyncLanServer_START"))
        else:
            logger.error(f"{lp} Cync config file not found at {cfg_file.as_posix()}. Please visit the ingress page and perform a device export.")
            raise FileNotFoundError(f"Cync config file not found at {cfg_file.as_posix()}")
        if ENABLE_EXPORTER is True:
            g.cloud_api = CyncCloudAPI()
            g.export_server = ExportServer()
            tasks.append(asyncio.Task(g.export_server.start(), name="ExportServer_START"))
        g.mqtt_client = MQTTClient()
        tasks.append(asyncio.Task(g.mqtt_client.start(), name="MQTTClient_START"))
        g.tasks.extend(tasks)
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.exception(f"{lp} Exception occurred while starting services: {e}")
            # Stop all services if any service fails to start
            await self.stop()
            raise e

    async def stop(self):
        """Stop the nCync server, MQTT client, and Export server."""
        lp = f"{self.lp}stop:"
        # send sigterm
        logger.info(f"{lp} Bringing software stack down using SIGTERM...")
        os.kill(os.getpid(), signal.SIGTERM)


def main():

    lp = "main:"
    parse_cli()
    if CYNC_DEBUG:
        logger.info(f"{lp} Add-on config has set logging level to: Debug")
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
    check_python_version()

    # create dir for cync_mesh.yaml and uuid.txt if it does not exist
    persistent_dir = Path(PERSISTENT_BASE_DIR).expanduser().resolve()
    if not persistent_dir.exists():
        try:
            persistent_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"{lp} Created persistent directory: {persistent_dir.as_posix()}")
        except Exception as e:
            logger.error(f"{lp} Failed to create persistent directory: {e}")
            sys.exit(1)

    g.cync_lan = CyncLAN()
    try:
        asyncio.get_event_loop().run_until_complete(g.cync_lan.start())
    except KeyboardInterrupt:
        logger.info(f"{lp} Caught KeyboardInterrupt, exiting...")
    except Exception as e:
        logger.exception(f"{lp} Caught exception: {e}")
    else:
        logger.info(f"{lp} CyncLAN stack stopped gracefully, bye!")
    finally:
        if not g.loop.is_closed():
            g.loop.close()
