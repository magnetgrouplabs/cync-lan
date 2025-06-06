import asyncio
import logging
import signal
import sys
from typing import Optional

import aiohttp
import uvloop

from cync_lan.const import *
from cync_lan.structs import GlobalObject
from cync_lan.server import CyncLanServer
from cync_lan.mqtt_client import MQTTClient
from cync_lan.exporter import ExportServer

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

g: Optional["GlobalObject"] = None
cync: Optional["CyncLAN"] = None

def signal_handler(signum, frame: Optional["asyncio.Future"] = None) -> None:
    """
    Handle signals for graceful shutdown.
    """
    logger.info(f"CyncLAN: Received signal {signum}, shutting down...")
    if g:
        if g.cync_lan_server:
            asyncio.create_task(g.cync_lan_server.stop())
        if g.mqtt_client:
            asyncio.create_task(g.mqtt_client.stop())
        if g.http_session:
            asyncio.create_task(g.http_session.close())
        if g.export_server:
            asyncio.create_task(g.export_server.stop())
        # wait for all tasks to complete
        if g.loop:
            logger.info("CyncLAN: Waiting for all tasks to complete...")
            pending = asyncio.all_tasks(g.loop)
            if pending:
                logger.info(f"CyncLAN: Pending tasks: {pending}")
            g.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))


class CyncLAN:
    lp: str = "CyncLAN:"
    def __init__(self):
        global g

        if g is None:
            logger.debug("main: Initializing GlobalObject")
            g = GlobalObject()
        # create an aiohttp session to be used for Cloud API calls
        g.http_session = aiohttp.ClientSession()
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        g.loop = asyncio.get_event_loop()
        logger.debug("main: Setting up event loop signal handlers")
        g.loop.add_signal_handler(signal.SIGINT, signal_handler)
        g.loop.add_signal_handler(signal.SIGTERM, signal_handler)

    async def start(self):
        """Start the Cync LAN server, MQTT client, and Export server."""
        lp = f"{self.lp}start:"
        tasks = []
        g.cync_lan_server = CyncLanServer()
        g.export_server = ExportServer()
        g.mqtt_client = MQTTClient()

        tasks.append(g.cync_lan_server.start())
        tasks.append(g.export_server.start())
        tasks.append(g.mqtt_client.start())
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info(f"{lp} All services started successfully")

    async def stop(self):
        """Stop the Cync LAN server, MQTT client, and Export server."""
        lp = f"{self.lp}stop:"
        tasks = []
        if g.cync_lan_server:
            tasks.append(g.cync_lan_server.stop())
        if g.export_server:
            tasks.append(g.export_server.stop())
        if g.mqtt_client:
            tasks.append(g.mqtt_client.stop())
        if g.http_session:
            tasks.append(g.http_session.close())
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("CyncLAN: All services stopped successfully.")

def check_python_version():
    if sys.version_info >= (3, 9):
        pass
    else:
        sys.exit(
            "Python version 3.9 or higher REQUIRED! you have version: %s" % sys.version
        )



def main():
    global cync

    cync = CyncLAN()
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("main: Caught KeyboardInterrupt, exiting...")
    except Exception as e:
        logger.exception(f"main: Caught exception: {e}")


async def async_main():
    check_python_version()
    if CYNC_DEBUG:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)

    try:
        g.loop.run_until_complete(cync.start())
    except KeyboardInterrupt as ke:
        logger.info("main: Caught KeyboardInterrupt in exception block!")
        raise KeyboardInterrupt from ke
    except Exception as e:
        logger.exception(e)
    finally:
        g.loop.run_until_complete(cync.stop())
        g.loop.close()

if __name__ == "__main__":
    logger.info("Starting Cync LAN...")
    main()
    logger.info("Cync LAN script finished!")