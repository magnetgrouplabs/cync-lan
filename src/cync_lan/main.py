import argparse
import asyncio
import logging
import signal
import sys
import uuid
from functools import partial
from pathlib import Path
from typing import Optional, Union

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
SHUTTING_DOWN: bool = False
global_tasks = []

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
            # cruicial to stop the MQTT connection retry loop
            tasks = []
            if g.cync_lan_server:
                tasks.append(g.cync_lan_server.stop())
            if g.mqtt_client:
                tasks.append(g.mqtt_client.stop())
            if g.http_session:
                tasks.append(g.http_session.close())
            if g.export_server:
                tasks.append(g.export_server.stop())
            if tasks:
                asyncio.gather(*tasks, return_exceptions=True)
            # cancel all not-done global_tasks (start and stop tasks)
            if g.loop:
                for task in global_tasks:
                    if not task.done():
                        # logger.debug(f"CyncLAN: Cancelling task: {task.get_name()}")
                        task.cancel()
            global_tasks.clear()



class CyncLAN:
    lp: str = "CyncLAN:"
    def __init__(self):
        global g

        if g is None:
            logger.debug("main: Initializing GlobalObject")
            g = GlobalObject()
        self._is_first_run()
        # create an aiohttp session to be used for Cloud API calls
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        g.loop = asyncio.get_event_loop()
        logger.debug("main: Setting up event loop signal handlers")
        g.loop.add_signal_handler(signal.SIGINT, partial(signal_handler, signal.SIGINT))
        g.loop.add_signal_handler(signal.SIGTERM, partial(signal_handler, signal.SIGTERM))

    def _is_first_run(self):
        """Check if this is the first run of the Cync LAN server, if so, create the CYNC_ADDON_UUID (UUID4)"""
        def write_uuid_to_disk(uuid_str: str):
            uuid_file = Path(CYNC_UUID_PATH)
            with open(uuid_file, "w") as f:
                f.write(uuid_str)
            logger.info(f"{self.lp} UUID written to disk: {uuid_str}")
        uuid_file = Path(CYNC_UUID_PATH)
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
                        logger.warning(f"{self.lp} Invalid UUID version in uuid.txt: {uuid_from_disk}")
                        create_uuid = True
            else:
                logger.info(f"{self.lp} No uuid.txt found")
                create_uuid = True
        except PermissionError:
            logger.error(f"{self.lp} PermissionError: Unable to read/write {CYNC_UUID_PATH}. Please check permissions.")
            create_uuid = True
        if create_uuid:
            global CYNC_ADDON_UUID

            logger.debug(f"{self.lp} Creating a new UUID to be used for the 'CyncLAN Controller/Bridge' device")
            CYNC_ADDON_UUID = str(uuid.uuid4())
            write_uuid_to_disk(CYNC_ADDON_UUID)

    async def start(self):
        """Start the Cync LAN server, MQTT client, and Export server."""
        global global_tasks

        lp = f"{self.lp}start:"
        g.http_session = aiohttp.ClientSession()
        g.cync_lan_server = CyncLanServer()
        g.export_server = ExportServer()
        g.mqtt_client = MQTTClient()

        global_tasks.append(asyncio.Task(g.cync_lan_server.start(), name="CyncLanServer_START"))
        global_tasks.append(asyncio.Task(g.export_server.start(), name="ExportServer_START"))
        global_tasks.append(asyncio.Task(g.mqtt_client.start(), name="MQTTClient_START"))
        try:
            await asyncio.gather(*global_tasks, return_exceptions=True)
        except Exception as e:
            logger.exception(f"{lp} Exception occurred while starting services: {e}")
            # Stop all services if any service fails to start
            await self.stop()
            raise e


    async def stop(self):
        """Stop the Cync LAN server, MQTT client, and Export server."""
        global global_tasks

        lp = f"{self.lp}stop:"
        tasks = []
        if g.cync_lan_server:
            tasks.append(asyncio.Task(g.cync_lan_server.stop(), name="CyncLanServer_STOP"))
        if g.export_server:
            tasks.append(asyncio.Task(g.export_server.stop(), name="ExportServer_STOP"))
        if g.mqtt_client:
            tasks.append(asyncio.Task(g.mqtt_client.stop(), name="MQTTClient_STOP"))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if g.http_session:
            await g.http_session.close()
        global_tasks.extend(tasks)
        logger.info(f"{lp} All services stopped successfully.")

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

    global CYNC_DEBUG

    CYNC_DEBUG = args.debug
    if CYNC_DEBUG:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
    if args.env:
        env_path = args.env
        env_path = env_path.expanduser().resolve()
        if not env_path.exists():
            logger.error(f"Environment file {env_path} does not exist")
        try:
            import dotenv
            loaded_any = dotenv.load_dotenv(env_path, override=True)
        except ImportError:
            logger.error("dotenv module is not installed. Please install it with 'pip install python-dotenv'")
        except Exception as e:
            logger.error(f"Failed to read environment file {env_path}: {e}")
        else:
            if loaded_any:
                logger.info(f"Environment variables loaded from {env_path}")
                g.reload_env()
            else:
                logger.warning(f"No environment variables were loaded from {env_path}")


def main():
    global cync
    parse_cli()
    cync = CyncLAN()
    try:
        asyncio.get_event_loop().run_until_complete(async_main())
    except KeyboardInterrupt:
        logger.info("main: Caught KeyboardInterrupt, exiting...")
    except Exception as e:
        logger.exception(f"main: Caught exception: {e}")
    else:
        logger.info("main: CyncLAN stack stopped gracefully, bye!")


async def async_main():
    check_python_version()
    if CYNC_DEBUG:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)

    try:
        await cync.start()
    except KeyboardInterrupt as ke:
        logger.info("main: Caught KeyboardInterrupt in exception block!")
        raise KeyboardInterrupt from ke
    except Exception as e:
        logger.exception(e)
    finally:
        g.loop.stop()

if __name__ == "__main__":
    logger.info("Starting Cync LAN...")
    main()
    logger.info("Cync LAN script finished!")