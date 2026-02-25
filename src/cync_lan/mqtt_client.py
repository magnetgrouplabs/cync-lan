import asyncio
import json
import logging
import random
import re
from json import JSONDecodeError
from typing import Optional, Union, List, Coroutine, Dict

import aiomqtt

from cync_lan.const import (
    CYNC_MINK,
    CYNC_MAXK,
    ORIGIN_STRUCT,
    CYNC_BRIDGE_OBJ_ID,
    CYNC_VERSION,
    FACTORY_EFFECTS_BYTES,
    CYNC_MANUFACTURER,
    CYNC_HASS_WILL_MSG,
    CYNC_HASS_BIRTH_MSG,
    CYNC_HASS_TOPIC,
    CYNC_HASS_STATUS_TOPIC,
    DEVICE_LWT_MSG,
    CYNC_MQTT_CONN_DELAY,
    CYNC_MQTT_HOST,
    CYNC_MQTT_PORT,
    CYNC_MQTT_USER,
    CYNC_MQTT_PASS,
    CYNC_BRIDGE_DEVICE_REGISTRY_CONF,
    CYNC_TOPIC,
    CYNC_LOG_NAME,
)
from cync_lan.devices import CyncDevice
from cync_lan.metadata.model_info import device_type_map
from cync_lan.structs import DeviceStatus, GlobalObject, FanSpeed
from cync_lan.utils import send_sigterm

logger = logging.getLogger(CYNC_LOG_NAME)
g = GlobalObject()
bridge_device_reg_struct = CYNC_BRIDGE_DEVICE_REGISTRY_CONF
# Log all loggers in the logger manager
# logging.getLogger().manager.loggerDict.keys()


class MQTTClient:
    lp: str = "mqtt:"
    cync_topic: str
    start_task: Optional[asyncio.Task] = None

    _instance: Optional["MQTTClient"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._connected = False
        self.tasks: Optional[List[Union[asyncio.Task, Coroutine]]] = None
        lp = f"{self.lp}init:"
        if not CYNC_TOPIC:
            topic = "cync_lan"
            logger.warning("%s MQTT topic not set, using default: %s" % (lp, topic))
        else:
            topic = CYNC_TOPIC

        if not CYNC_HASS_TOPIC:
            ha_topic = "homeassistant"
            logger.warning(
                "%s HomeAssistant topic not set, using default: %s" % (lp, ha_topic)
            )
        else:
            ha_topic = CYNC_HASS_TOPIC

        self.broker_client_id = f"cync_lan_{g.uuid}"
        lwt = aiomqtt.Will(topic=f"{topic}/connected", payload=DEVICE_LWT_MSG)
        self.broker_host = CYNC_MQTT_HOST
        self.broker_port = CYNC_MQTT_PORT
        self.broker_username = CYNC_MQTT_USER
        self.broker_password = CYNC_MQTT_PASS
        self.client = aiomqtt.Client(
            hostname=self.broker_host,
            port=int(self.broker_port),
            username=self.broker_username,
            password=self.broker_password,
            identifier=self.broker_client_id,
            will=lwt,
            # logger=logger,
        )

        self.topic = topic
        self.ha_topic = ha_topic

    async def start(self):
        itr = 0
        lp = f"{self.lp}start:"
        try:
            while True:
                itr += 1
                self._connected = await self.connect()
                if self._connected:
                    # ["state_topic"] = f"{self.topic}/status/bridge/mqtt_client/connected"
                    # TODO: publish MQTT message indicating the MQTT client is connected
                    await self.publish(
                        f"{self.topic}/status/bridge/mqtt_client/connected",
                        "ON".encode(),
                    )

                    if itr == 1:
                        logger.debug(f"{lp} Seeding all devices: offline")
                        for device_id, device in g.ncync_server.devices.items():
                            # if device.is_fan_controller:
                            #     logger.debug(f"{lp} TESTING>>> Setting up fan controller for device: {device.name} (ID: {device.id})")
                            #     # set device online for testing
                            #     await self.pub_online(device.id, True)
                            #     await device.set_brightness(50)  # set brightness to 50% for testing
                            # else:
                            await self.pub_online(device_id, False)
                    elif itr > 1:
                        tasks = []
                        # set the device online/offline and set its status
                        for device in g.ncync_server.devices.values():
                            tasks.append(self.pub_online(device.id, device.online))
                            tasks.append(
                                self.parse_device_status(
                                    device.id,
                                    DeviceStatus(
                                        state=device.state,
                                        brightness=device.brightness,
                                        temperature=device.temperature,
                                        red=device.red,
                                        green=device.green,
                                        blue=device.blue,
                                    ),
                                    from_pkt="'re-connect'",
                                )
                            )
                        if tasks:
                            await asyncio.gather(*tasks)
                    logger.debug(f"{lp} Starting MQTT receiver...")
                    lp: str = f"{self.lp}rcv:"
                    topics = [
                        (f"{self.topic}/set/#", 0),
                        (f"{self.ha_topic}/status", 0),
                    ]
                    await self.client.subscribe(topics)
                    logger.debug(
                        f"{lp} Subscribed to MQTT topics: {[x[0] for x in topics]}. "
                        f"Waiting for MQTT messages..."
                    )
                    try:
                        await self.start_receiver_task()
                    except asyncio.CancelledError as ce:
                        logger.debug(
                            f"{lp} MQTT receiver task cancelled, propagating..."
                        )
                        raise ce
                    except (aiomqtt.MqttError, aiomqtt.MqttCodeError) as msg_err:
                        logger.warning(f"{lp} MQTT error: {msg_err}")
                        continue
                else:
                    await self.publish(
                        f"{self.topic}/status/bridge/mqtt_client/connected",
                        "OFF".encode(),
                    )
                    delay = CYNC_MQTT_CONN_DELAY
                    if delay is None:
                        delay = 5
                    elif delay <= 0:
                        logger.debug(
                            f"{lp} MQTT connection delay is less than or equal to 0, which is probably a typo, setting to 5..."
                        )
                        delay = 5

                    logger.info(
                        f"{lp} connecting to MQTT broker failed, sleeping for {delay} seconds before re-trying..."
                    )
                    await asyncio.sleep(delay)
        except asyncio.CancelledError as ce:
            raise ce
        except Exception as exc:
            logger.exception(f"{lp} MQTT start() EXCEPTION: {exc}")

    async def connect(self) -> bool:
        lp = f"{self.lp}connect:"
        self._connected = False
        logger.debug(f"{lp} Connecting to MQTT broker...")
        lwt = aiomqtt.Will(topic=f"{self.topic}/connected", payload=DEVICE_LWT_MSG)
        g.reload_env()
        self.broker_host = g.env.mqtt_host
        self.broker_port = g.env.mqtt_port
        self.broker_username = g.env.mqtt_user
        self.broker_password = g.env.mqtt_pass
        self.client = aiomqtt.Client(
            hostname=self.broker_host,
            port=int(self.broker_port),
            username=self.broker_username,
            password=self.broker_password,
            identifier=self.broker_client_id,
            will=lwt,
            # logger=logger,
        )
        try:
            await self.client.__aenter__()
        except aiomqtt.MqttError as mqtt_err_exc:
            # -> [Errno 111] Connection refused
            # [code:134] Bad user name or password
            logger.error(f"{lp} Connection failed [MqttError] -> {mqtt_err_exc}")
            if "code:134" in str(mqtt_err_exc):
                logger.error(
                    f"{lp} Bad username or password, check your MQTT credentials (username: {g.env.mqtt_user})"
                )
                send_sigterm()
        else:
            self._connected = True
            logger.info(
                f"{lp} Connected to MQTT broker: {self.broker_host} port: {self.broker_port}"
            )
            await self.send_birth_msg()
            await asyncio.sleep(1)
            await self.homeassistant_discovery()
            return True
        return False

    async def start_receiver_task(self):
        """Start listening for MQTT messages on subscribed topics"""
        lp = f"{self.lp}rcv:"
        async for message in self.client.messages:
            message: aiomqtt.message.Message
            topic = message.topic
            payload = message.payload
            if (payload is None) or (payload is not None and not payload):
                logger.debug(
                    f"{lp} Received empty/None payload ({payload}) for topic: {topic} , skipping..."
                )
                continue
            _topic = topic.value.split("/")
            tasks = []
            device = None
            # cync_topic/(set|status)/device_id(/extra_data)?
            if _topic[0] == CYNC_TOPIC:
                if _topic[1] == "set":
                    device_id = _topic[2]
                    if device_id == "bridge":
                        pass
                    else:
                        device_id = int(_topic[2].split("-")[1])
                        if device_id not in g.ncync_server.devices:
                            logger.warning(
                                f"{lp} Device ID {device_id} not found, device is disabled in config file or have you deleted / added any "
                                f"devices recently?"
                            )
                            continue
                        device = g.ncync_server.devices[device_id]
                    extra_data = _topic[3:] if len(_topic) > 3 else None
                    if extra_data:
                        norm_pl = payload.decode().casefold()
                        # logger.debug(f"{lp} Extra data found: {extra_data}")
                        if extra_data[0] == "restart":
                            if norm_pl == "press":
                                logger.info(
                                    f"{lp} Restart button pressed! Restarting Cync LAN bridge (NOT IMPLEMENTED)..."
                                )
                        elif extra_data[0] == "start_export":
                            if norm_pl == "press":
                                logger.info(
                                    f"{lp} Start Export button pressed! Starting Cync Export (NOT IMPLEMENTED)..."
                                )
                        elif extra_data[0] == "otp":
                            if extra_data[1] == "submit":
                                logger.info(
                                    f"{lp} OTP submit button pressed! (NOT IMPLEMENTED)..."
                                )
                            elif extra_data[1] == "input":
                                logger.info(
                                    f"{lp} OTP input received: {norm_pl} (NOT IMPLEMENTED)..."
                                )
                        elif device and device.is_fan_controller:
                            if extra_data[0] == "percentage":
                                percentage = int(norm_pl)
                                if percentage == 0:
                                    tasks.append(device.set_brightness(0))
                                elif percentage <= 25:
                                    logger.debug(
                                        f"{lp} Fan percentage received: {percentage}, translated to: 'low' preset"
                                    )
                                    tasks.append(device.set_brightness(50))
                                elif percentage <= 50:
                                    logger.debug(
                                        f"{lp} Fan percentage received: {percentage}, translated to: 'medium' preset"
                                    )
                                    tasks.append(device.set_brightness(128))
                                elif percentage <= 75:
                                    logger.debug(
                                        f"{lp} Fan percentage received: {percentage}, translated to: 'high' preset"
                                    )
                                    tasks.append(device.set_brightness(191))
                                elif percentage <= 100:
                                    logger.debug(
                                        f"{lp} Fan percentage received: {percentage}, translated to: 'max' preset"
                                    )
                                    tasks.append(device.set_brightness(255))
                                else:
                                    logger.warning(
                                        f"{lp} Fan percentage received: {percentage} is out of range (0-100), skipping..."
                                    )
                            elif extra_data[0] == "preset":
                                preset_mode = norm_pl
                                if preset_mode == "off":
                                    tasks.append(device.set_fan_speed(FanSpeed.OFF))
                                elif preset_mode == "low":
                                    tasks.append(device.set_fan_speed(FanSpeed.LOW))
                                elif preset_mode == "medium":
                                    tasks.append(device.set_fan_speed(FanSpeed.MEDIUM))
                                elif preset_mode == "high":
                                    tasks.append(device.set_fan_speed(FanSpeed.HIGH))
                                elif preset_mode == "max":
                                    tasks.append(device.set_fan_speed(FanSpeed.MAX))
                                else:
                                    logger.warning(
                                        f"{lp} Unknown preset mode: {preset_mode}, skipping..."
                                    )

                    if payload.startswith(b"{"):
                        try:
                            json_data = json.loads(payload)
                        except JSONDecodeError as e:
                            logger.error(
                                "%s bad json message: {%s} EXCEPTION => %s"
                                % (lp, payload, e)
                            )
                            continue
                        except Exception as e:
                            logger.error(
                                "%s error will decoding a string into JSON: '%s' EXCEPTION => %s"
                                % (lp, payload, e)
                            )
                            continue

                        if "state" in json_data and "brightness" not in json_data:
                            if "effect" in json_data:
                                effect = json_data["effect"]
                                tasks.append(device.set_lightshow(effect))
                            else:
                                if json_data["state"].upper() == "ON":
                                    tasks.append(device.set_power(1))
                                else:
                                    tasks.append(device.set_power(0))
                        if "brightness" in json_data:
                            lum = int(json_data["brightness"])
                            tasks.append(device.set_brightness(lum))

                        if "color_temp" in json_data:
                            tasks.append(
                                device.set_temperature(
                                    self.kelvin2cync(int(json_data["color_temp"]))
                                )
                            )
                        elif "color" in json_data:
                            color = []
                            for rgb in ("r", "g", "b"):
                                if rgb in json_data["color"]:
                                    color.append(int(json_data["color"][rgb]))
                                else:
                                    color.append(0)
                            tasks.append(device.set_rgb(*color))
                    # binary payload does not start with a '{', so it is not JSON
                    else:
                        str_payload = payload.decode("utf-8").strip()
                        #  use a regex pattern to determine if it is a single word
                        pattern = re.compile(r"^\w+$")
                        if pattern.match(str_payload):
                            # handle non-JSON payloads
                            if str_payload.casefold() == "on":
                                logger.debug(f"{lp} setting power to ON (non-JSON)")
                                tasks.append(device.set_power(1))
                            elif str_payload.casefold() == "off":
                                logger.debug(f"{lp} setting power to OFF (non-JSON)")
                                tasks.append(device.set_power(0))
                        else:
                            logger.warning(
                                f"{lp} Unknown payload: {payload}, skipping..."
                            )
                else:
                    logger.warning(f"{lp} Unknown command: {topic} => {payload}")
                if tasks:
                    await asyncio.gather(*tasks)

            # messages sent to the hass mqtt topic
            elif _topic[0] == self.ha_topic:
                # birth / will
                if _topic[1] == CYNC_HASS_STATUS_TOPIC:
                    if payload.decode().casefold() == CYNC_HASS_BIRTH_MSG.casefold():
                        birth_delay = random.randint(5, 15)
                        logger.info(
                            f"{lp} HASS has sent MQTT BIRTH message, re-announcing device discovery, availability and status after a random delay of {birth_delay} seconds..."
                        )
                        # Give HASS some time to start up, from docs:
                        # To avoid high IO loads on the MQTT broker, adding some random delay in sending the discovery payload is recommended.
                        await asyncio.sleep(birth_delay)
                        # register devices
                        await self.homeassistant_discovery()
                        # give HASS a moment (to register devices)
                        await asyncio.sleep(2)
                        # set the device online/offline and set its status
                        for device in g.ncync_server.devices.values():
                            await self.pub_online(device.id, device.online)
                            await self.parse_device_status(
                                device.id,
                                DeviceStatus(
                                    state=device.state,
                                    brightness=device.brightness,
                                    temperature=device.temperature,
                                    red=device.red,
                                    green=device.green,
                                    blue=device.blue,
                                ),
                                from_pkt="'hass_birth'",
                            )

                    elif payload.decode().casefold() == CYNC_HASS_WILL_MSG.casefold():
                        logger.info(
                            f"{lp} received Last Will msg from Home Assistant, HASS is offline!"
                        )
                    else:
                        logger.warning(f"{lp} Unknown HASS status message: {payload}")

    async def stop(self):
        lp = f"{self.lp}stop:"
        # set all devices offline
        if self._connected:
            logger.debug(f"{lp} Setting all Cync devices offline...")
            for device_id, device in g.ncync_server.devices.items():
                await self.pub_online(device_id, False)
            # ["state_topic"] = f"{self.topic}/status/bridge/mqtt_client/connected"
            # TODO: publish MQTT message indicating the MQTT client is connected
            await self.publish(
                f"{self.topic}/status/bridge/mqtt_client/connected",
                "OFF".encode(),
            )
            await self.publish(f"{self.topic}/availability/bridge", "offline".encode())
            await self.send_will_msg()
        try:
            logger.debug(f"{lp} Disconnecting from broker...")
            await self.client.__aexit__(None, None, None)
        except aiomqtt.MqttError as ce:
            logger.warning("%s MQTT disconnect failed: %s" % (lp, ce))
        except Exception as e:
            logger.warning("%s MQTT disconnect failed: %s" % (lp, e), exc_info=True)
        else:
            logger.info(f"{lp} Disconnected from MQTT broker")
        finally:
            self._connected = False
            if self.start_task and not self.start_task.done():
                logger.debug(f"{lp} FINISHING: Cancelling start task")
                self.start_task.cancel()

    async def pub_online(self, device_id: int, status: bool) -> bool:
        lp = f"{self.lp}pub_online:"
        if self._connected:
            if device_id not in g.ncync_server.devices:
                logger.error(
                    f"{lp} Device ID {device_id} not found?! Have you deleted or added any devices recently? "
                    f"You may need to re-export devices from your Cync account!"
                )
                return False
            availability = b"online" if status else b"offline"
            device: CyncDevice = g.ncync_server.devices[device_id]
            device_uuid = f"{device.home_id}-{device_id}"
            # logger.debug(f"{lp} Publishing availability: {availability}")
            try:
                _ = await self.client.publish(
                    f"{self.topic}/availability/{device_uuid}", availability, qos=0
                )
            except aiomqtt.MqttError as mqtt_code_exc:
                logger.warning(f"{lp} [MqttError] -> {mqtt_code_exc}")
                self._connected = False
            else:
                return True
        return False

    async def update_device_state(self, device: CyncDevice, state: int) -> bool:
        """Update the device state and publish to MQTT for HASS devices to update."""
        device.online = True
        device.state = state
        power_status = "OFF" if state == 0 else "ON"
        mqtt_dev_state = {"state": power_status}
        if device.is_plug or device.is_switch:
            mqtt_dev_state = power_status.encode()  # send ON or OFF if plug
        else:
            mqtt_dev_state = json.dumps(mqtt_dev_state).encode()  # send JSON
        return await self.send_device_status(device, mqtt_dev_state)

    async def update_brightness(self, device: CyncDevice, bri: int) -> bool:
        """Update the device brightness and publish to MQTT for HASS devices to update."""
        device.online = True
        device.brightness = bri
        state = "ON"
        if bri == 0:
            state = "OFF"
        mqtt_dev_state = {"state": state, "brightness": bri}
        return await self.send_device_status(
            device, json.dumps(mqtt_dev_state).encode()
        )

    async def update_temperature(self, device: CyncDevice, temp: int) -> bool:
        """Update the device temperature and publish to MQTT for HASS devices to update."""
        device.online = True
        if device.supports_temperature:
            mqtt_dev_state = {
                "state": "ON",
                "color_mode": "color_temp",
                "color_temp": self.cync2kelvin(temp),
            }
            device.temperature = temp
            device.red = 0
            device.green = 0
            device.blue = 0
            return await self.send_device_status(
                device, json.dumps(mqtt_dev_state).encode()
            )
        return False

    async def update_rgb(self, device: CyncDevice, rgb: tuple[int, int, int]) -> bool:
        """Update the device RGB and publish to MQTT for HASS devices to update. Intended for callbacks"""
        device.online = True
        if device.supports_rgb and (
            any(
                [
                    rgb[0] is not None,
                    rgb[1] is not None,
                    rgb[2] is not None,
                ]
            )
        ):
            mqtt_dev_state = {
                "state": "ON",
                "color_mode": "rgb",
                "color": {"r": rgb[0], "g": rgb[1], "b": rgb[2]},
            }
            device.red = rgb[0]
            device.green = rgb[1]
            device.blue = rgb[2]
            device.temperature = 254
            return await self.send_device_status(
                device, json.dumps(mqtt_dev_state).encode()
            )
        return False

    async def send_device_status(
        self, device: CyncDevice, msg: bytes, from_pkt: Optional[str] = None
    ) -> bool:

        lp = f"{self.lp}device_status:"
        if from_pkt:
            lp = f"{lp}{from_pkt}:"
        if self._connected:
            tpc = f"{self.topic}/status/{device.hass_id}"
            logger.debug(
                f"{lp} Sending {msg} for device: '{device.name}' (ID: {device.id})"
            )
            try:
                await self.client.publish(
                    tpc,
                    msg,
                    qos=0,
                    timeout=3.0,
                )
            except aiomqtt.MqttError as mqtt_code_exc:
                logger.warning(f"{lp} [MqttError] -> {mqtt_code_exc}")
                self._connected = False
            except asyncio.CancelledError as can_exc:
                logger.debug(f"{lp} [Task Cancelled] -> {can_exc}")
            else:
                return True
        return False

    async def parse_device_status(
        self, device_id: int, device_status: DeviceStatus, *args, **kwargs
    ) -> bool:
        """Parse device status and publish to MQTT for HASS devices to update. Useful for device status packets that report the complete device state"""
        lp = f"{self.lp}parse status:"
        from_pkt = kwargs.get("from_pkt")
        if from_pkt:
            lp = f"{lp}{from_pkt}:"
        if device_id not in g.ncync_server.devices:
            logger.error(
                f"{lp} Device ID {device_id} not found! Device may be disabled in config file or "
                f"you may need to re-export devices from your Cync account"
            )
            return False
        device: CyncDevice = g.ncync_server.devices[device_id]
        # if device.build_status() == device_status:
        #     # logger.debug(f"{lp} Device status unchanged, skipping...")
        #     return
        power_status = "OFF" if device_status.state == 0 else "ON"
        mqtt_dev_state: Union[Dict[str, Union[int, str, bytes, dict, list]], bytes] = {
            "state": power_status
        }

        if device.is_plug or device.is_switch:
            mqtt_dev_state = power_status.encode()

        else:
            if device_status.brightness is not None:
                mqtt_dev_state["brightness"] = device_status.brightness

            if device_status.temperature is not None:
                if device.supports_rgb and (
                    any(
                        [
                            device_status.red is not None,
                            device_status.green is not None,
                            device_status.blue is not None,
                        ]
                    )
                    and device_status.temperature > 100
                ):
                    mqtt_dev_state["color_mode"] = "rgb"
                    mqtt_dev_state["color"] = {
                        "r": device_status.red,
                        "g": device_status.green,
                        "b": device_status.blue,
                    }
                elif device.supports_temperature and (
                    0 <= device_status.temperature <= 100
                ):
                    mqtt_dev_state["color_mode"] = "color_temp"
                    mqtt_dev_state["color_temp"] = self.cync2kelvin(
                        device_status.temperature
                    )
            mqtt_dev_state = json.dumps(mqtt_dev_state).encode()

        return await self.send_device_status(device, mqtt_dev_state, from_pkt=from_pkt)

    async def send_birth_msg(self) -> bool:
        lp = f"{self.lp}send_birth_msg:"
        if self._connected:
            logger.debug(
                f"{lp} Sending birth message ({CYNC_HASS_BIRTH_MSG}) to {self.topic}/status"
            )
            try:
                await self.client.publish(
                    f"{self.topic}/status",
                    CYNC_HASS_BIRTH_MSG.encode(),
                    qos=0,
                    retain=True,
                )
            except aiomqtt.MqttCodeError as mqtt_code_exc:
                logger.warning(
                    f"{lp} [MqttError] (rc: {mqtt_code_exc.rc}) -> {mqtt_code_exc}"
                )
            except asyncio.CancelledError as can_exc:
                logger.warning(f"{lp} [Task Cancelled] -> {can_exc}")
            else:
                return True
        return False

    async def send_will_msg(self) -> bool:
        lp = f"{self.lp}send_will_msg:"
        if self._connected:
            logger.debug(
                f"{lp} Sending will message ({CYNC_HASS_WILL_MSG}) to {self.topic}/status"
            )
            try:
                await self.client.publish(
                    f"{self.topic}/status",
                    CYNC_HASS_WILL_MSG.encode(),
                    qos=0,
                    retain=True,
                )
            except aiomqtt.MqttError as mqtt_code_exc:
                logger.warning(f"{lp} [MqttError] -> {mqtt_code_exc}")
                self._connected = False
            except Exception as e:
                logger.warning(f"{lp} [Exception] -> {e}")
            else:
                return True
        return False

    async def homeassistant_discovery(self) -> bool:
        """Build each configured Cync device for HASS device registry"""
        lp = f"{self.lp}hass:"
        ret = False
        if self._connected:
            logger.info(f"{lp} Starting device discovery...")
            await self.create_bridge_device()
            try:
                for device in g.ncync_server.devices.values():
                    device_uuid = device.hass_id
                    supported = device.metadata.supported
                    if not supported:
                        logger.warning(
                            f"{lp} Device '{device.name}' (ID: {device.id} / Type: {device.type}) is not supported, skipping HASS discovery..."
                        )
                        continue

                    unique_id = f"{device.home_id}_{device.id}"
                    obj_id = f"cync_lan_{unique_id}"
                    dev_fw_version = str(device.version)
                    ver_str = "Unknown"
                    fw_len = len(dev_fw_version)
                    if fw_len == 5:
                        if dev_fw_version != 00000:
                            ver_str = f"{dev_fw_version[0]}.{dev_fw_version[1]}.{dev_fw_version[2:]}"
                    elif fw_len == 2:
                        ver_str = f"{dev_fw_version[0]}.{dev_fw_version[1]}"
                    model_str = "Unknown"
                    if device.type in device_type_map:
                        model_str = device_type_map[device.type].model_string
                    dev_connections = [("bluetooth", device.mac.casefold())]
                    if not device.bt_only:
                        dev_connections.append(("mac", device.wifi_mac.casefold()))

                    device_registry_struct = {
                        "identifiers": [unique_id],
                        "manufacturer": CYNC_MANUFACTURER,
                        "connections": dev_connections,
                        "name": device.name,
                        "sw_version": ver_str,
                        "model": model_str,
                        "via_device": str(g.uuid),
                    }

                    entity_registry_struct = {
                        # retain for older HASS versions
                        "object_id": obj_id,
                        "default_entity_id": obj_id,
                        # set to None if only device name is relevant, this sets entity name
                        "name": None,
                        "command_topic": "{0}/set/{1}".format(self.topic, device_uuid),
                        "state_topic": "{0}/status/{1}".format(self.topic, device_uuid),
                        "avty_t": "{0}/availability/{1}".format(
                            self.topic, device_uuid
                        ),
                        "pl_avail": "online",
                        "pl_not_avail": "offline",
                        "state_on": "ON",
                        "state_off": "OFF",
                        "unique_id": unique_id,
                        "schema": "json",
                        "origin": ORIGIN_STRUCT,
                        "device": device_registry_struct,
                        "optimistic": False,
                    }
                    dev_type = "light"
                    if device.is_light:
                        pass
                    elif device.is_switch:
                        dev_type = "switch"
                        if device.metadata.capabilities.fan:
                            dev_type = "fan"

                    tpc_str_template = "{0}/{1}/{2}/config"

                    if dev_type == "light":
                        entity_registry_struct["supported_color_modes"] = []
                        entity_registry_struct.update({"brightness_scale": 100})
                        if device.supports_temperature or device.supports_rgb:
                            if device.supports_temperature:
                                entity_registry_struct["supported_color_modes"].append(
                                    "color_temp"
                                )
                                entity_registry_struct["color_temp_kelvin"] = True
                                entity_registry_struct["min_kelvin"] = CYNC_MINK
                                entity_registry_struct["max_kelvin"] = CYNC_MAXK
                            if device.supports_rgb:
                                entity_registry_struct["supported_color_modes"].append(
                                    "rgb"
                                )
                                entity_registry_struct["effect"] = True
                                entity_registry_struct["effect_list"] = list(
                                    FACTORY_EFFECTS_BYTES.keys()
                                )
                            # add brightness : True only when supported_color_modes are present
                            entity_registry_struct.update({"brightness": True})
                        if not entity_registry_struct["supported_color_modes"]:
                            entity_registry_struct["supported_color_modes"].append(
                                "brightness"
                            )

                    elif dev_type == "fan":
                        entity_registry_struct["platform"] = "fan"
                        # fan can be controlled via light control structs: brightness -> max=255, high=191, medium=128, low=50, off=0
                        entity_registry_struct["percentage_command_topic"] = (
                            "{0}/set/{1}/percentage".format(self.topic, device_uuid)
                        )
                        entity_registry_struct["percentage_state_topic"] = (
                            "{0}/status/{1}/percentage".format(self.topic, device_uuid)
                        )
                        entity_registry_struct["preset_modes"] = [
                            "off",
                            "low",
                            "medium",
                            "high",
                            "max",
                        ]
                        entity_registry_struct["preset_mode_command_topic"] = (
                            "{0}/set/{1}/preset".format(self.topic, device_uuid)
                        )
                        entity_registry_struct["preset_mode_state_topic"] = (
                            "{0}/status/{1}/preset".format(self.topic, device_uuid)
                        )

                    tpc = tpc_str_template.format(self.ha_topic, dev_type, device_uuid)
                    try:
                        _ = await self.client.publish(
                            tpc,
                            json.dumps(entity_registry_struct).encode(),
                            qos=0,
                            retain=False,
                        )

                    except Exception as e:
                        logger.error(
                            "%s - Unable to publish mqtt message... skipped -> %s"
                            % (lp, e)
                        )
            except aiomqtt.MqttCodeError as mqtt_code_exc:
                logger.warning(
                    f"{lp} [MqttError] (rc: {mqtt_code_exc.rc}) -> {mqtt_code_exc}"
                )
                self._connected = False
            except asyncio.CancelledError as can_exc:
                logger.warning(f"{lp} [Task Cancelled] -> {can_exc}")
                raise can_exc
            except Exception as e:
                logger.exception(f"{lp} [Exception] -> {e}")
            else:
                ret = True
        logger.debug(f"{lp} Discovery complete (success: {ret})")
        return ret

    async def create_bridge_device(self) -> bool:
        """Create the device / entity registry config for the CyncLAN bridge itself."""
        global bridge_device_reg_struct
        # want to expose buttons (restart, start export, submit otp)
        # want to expose some sensors that show the number of devices, number of online devices, etc.
        # sensors to show if MQTT is connected, if the CyncLAN server is running, etc.
        # input_number to submit OTP for export
        lp = f"{self.lp}create_bridge_device:"
        ret = False

        logger.debug(f"{lp} Creating CyncLAN bridge device...")
        bridge_base_unique_id = "cync_lan_bridge"
        ver_str = CYNC_VERSION
        pub_tasks: List[asyncio.Task] = []
        # Bridge device config
        bridge_device_reg_struct = {
            "identifiers": [str(g.uuid)],
            "manufacturer": "baudneo",
            "name": "CyncLAN Bridge",
            "sw_version": ver_str,
            "model": "Local Push Controller",
        }
        # Entities for the bridge device
        entity_type = "button"
        template_tpc = "{0}/{1}/{2}/config"
        pub_tasks.append(
            self.publish(f"{self.topic}/availability/bridge", "online".encode())
        )

        entity_unique_id = f"{bridge_base_unique_id}_restart"
        restart_btn_entity_struct = {
            "platform": "button",
            # obj_id is to link back to the bridge device
            "object_id": CYNC_BRIDGE_OBJ_ID + "_restart",
            "default_entity_id": CYNC_BRIDGE_OBJ_ID + "_restart",
            "command_topic": f"{self.topic}/set/bridge/restart",
            "state_topic": f"{self.topic}/status/bridge/restart",
            "avty_t": f"{self.topic}/availability/bridge",
            "name": "Restart CyncLAN Bridge",
            "unique_id": entity_unique_id,
            "schema": "json",
            "origin": ORIGIN_STRUCT,
            "device": bridge_device_reg_struct,
        }
        ret = await self.publish_json_msg(
            template_tpc.format(self.ha_topic, entity_type, entity_unique_id),
            restart_btn_entity_struct,
        )
        if ret is False:
            logger.error(f"{lp} Failed to publish restart button entity config")

        entity_unique_id = f"{bridge_base_unique_id}_start_export"
        xport_btn_entity_conf = restart_btn_entity_struct.copy()
        xport_btn_entity_conf["default_entity_id"] = entity_unique_id
        xport_btn_entity_conf["command_topic"] = f"{self.topic}/set/bridge/export/start"
        xport_btn_entity_conf["state_topic"] = (
            f"{self.topic}/status/bridge/export/start"
        )
        xport_btn_entity_conf["name"] = "Start Export"
        xport_btn_entity_conf["unique_id"] = entity_unique_id
        ret = await self.publish_json_msg(
            template_tpc.format(self.ha_topic, entity_type, entity_unique_id),
            xport_btn_entity_conf,
        )
        if ret is False:
            logger.error(f"{lp} Failed to publish start export button entity config")

        entity_unique_id = f"{bridge_base_unique_id}_submit_otp"
        submit_otp_btn_entity_conf = restart_btn_entity_struct.copy()
        submit_otp_btn_entity_conf["default_entity_id"] = (
            CYNC_BRIDGE_OBJ_ID + "_submit_otp"
        )
        submit_otp_btn_entity_conf["command_topic"] = (
            f"{self.topic}/set/bridge/otp/submit"
        )
        submit_otp_btn_entity_conf["state_topic"] = (
            f"{self.topic}/status/bridge/otp/submit"
        )
        submit_otp_btn_entity_conf["name"] = "Submit OTP"
        submit_otp_btn_entity_conf["unique_id"] = entity_unique_id
        ret = await self.publish_json_msg(
            template_tpc.format(self.ha_topic, entity_type, entity_unique_id),
            submit_otp_btn_entity_conf,
        )
        if ret is False:
            logger.error(f"{lp} Failed to publish submit OTP button entity config")

        # binary sensor for if the TCP server is running
        # binary sensor for if the export server is running
        # binary sensor for if the MQTT client is connected
        entity_type = "binary_sensor"
        entity_unique_id = f"{bridge_base_unique_id}_tcp_server_running"
        tcp_server_entity_conf = {
            "object_id": entity_unique_id,
            "default_entity_id": entity_unique_id,
            "name": "nCync TCP Server Running",
            "state_topic": f"{self.topic}/status/bridge/tcp_server/running",
            "unique_id": entity_unique_id,
            "device_class": "running",
            "icon": "mdi:server-network",
            "avty_t": f"{self.topic}/availability/bridge",
            "schema": "json",
            "origin": ORIGIN_STRUCT,
            "device": bridge_device_reg_struct,
        }
        ret = await self.publish_json_msg(
            template_tpc.format(self.ha_topic, entity_type, entity_unique_id),
            tcp_server_entity_conf,
        )
        if ret is False:
            logger.error(f"{lp} Failed to publish TCP server running entity config")
        status = "ON" if g.ncync_server.running is True else "OFF"
        pub_tasks.append(
            self.publish(
                f"{self.topic}/status/bridge/tcp_server/running", status.encode()
            )
        )

        entity_unique_id = f"{bridge_base_unique_id}_export_server_running"
        export_server_entity_conf = tcp_server_entity_conf.copy()
        export_server_entity_conf["default_entity_id"] = entity_unique_id
        export_server_entity_conf["name"] = "Cync Export Server Running"
        export_server_entity_conf["state_topic"] = (
            f"{self.topic}/status/bridge/export_server/running"
        )
        export_server_entity_conf["unique_id"] = entity_unique_id
        export_server_entity_conf["icon"] = "mdi:export-variant"
        ret = await self.publish_json_msg(
            template_tpc.format(self.ha_topic, entity_type, entity_unique_id),
            export_server_entity_conf,
        )
        if ret is False:
            logger.error(f"{lp} Failed to publish export server running entity config")
        status = "ON" if g.export_server.running is True else "OFF"
        pub_tasks.append(
            self.publish(
                f"{self.topic}/status/bridge/export_server/running", status.encode()
            )
        )

        entity_unique_id = f"{bridge_base_unique_id}_mqtt_client_connected"
        mqtt_client_entity_conf = tcp_server_entity_conf.copy()
        mqtt_client_entity_conf["default_entity_id"] = entity_unique_id
        mqtt_client_entity_conf["name"] = "Cync MQTT Client Connected"
        mqtt_client_entity_conf["state_topic"] = (
            f"{self.topic}/status/bridge/mqtt_client/connected"
        )
        mqtt_client_entity_conf["unique_id"] = entity_unique_id
        mqtt_client_entity_conf["icon"] = "mdi:connection"
        mqtt_client_entity_conf["device_class"] = "connectivity"
        ret = await self.publish_json_msg(
            template_tpc.format(self.ha_topic, entity_type, entity_unique_id),
            mqtt_client_entity_conf,
        )
        if ret is False:
            logger.error(f"{lp} Failed to publish MQTT client connected entity config")

        # input number for OTP input
        entity_type = "number"
        entity_unique_id = f"{bridge_base_unique_id}_otp_input"
        otp_num_entity_cfg = {
            "platform": "number",
            "object_id": entity_unique_id,
            "default_entity_id": entity_unique_id,
            "icon": "mdi:lock",
            "command_topic": f"{self.topic}/set/bridge/otp/input",
            "state_topic": f"{self.topic}/status/bridge/otp/input",
            "avty_t": f"{self.topic}/availability/bridge",
            "schema": "json",
            "origin": ORIGIN_STRUCT,
            "device": bridge_device_reg_struct,
            "min": 000000,
            "max": 999999,
            "mode": "box",
            "name": "Cync emailed OTP",
            "unique_id": entity_unique_id,
        }
        ret = await self.publish_json_msg(
            template_tpc.format(self.ha_topic, entity_type, entity_unique_id),
            otp_num_entity_cfg,
        )
        if ret is False:
            logger.error(f"{lp} Failed to publish OTP input number entity config")

        # Sensors
        entity_type = "sensor"
        entity_unique_id = f"{bridge_base_unique_id}_connected_tcp_devices"
        num_tcp_devices_entity_conf = {
            "platform": "sensor",
            "object_id": entity_unique_id,
            "default_entity_id": entity_unique_id,
            "name": "TCP Devices Connected",
            "state_topic": f"{self.topic}/status/bridge/tcp_devices/connected",
            "unique_id": entity_unique_id,
            "icon": "mdi:counter",
            "avty_t": f"{self.topic}/availability/bridge",
            # "unit_of_measurement": "TCP device(s)",
            "schema": "json",
            "origin": ORIGIN_STRUCT,
            "device": bridge_device_reg_struct,
        }
        ret = await self.publish_json_msg(
            template_tpc.format(self.ha_topic, entity_type, entity_unique_id),
            num_tcp_devices_entity_conf,
        )
        if ret is False:
            logger.warning(
                f"{lp} Failed to publish number of TCP devices connected entity config"
            )
        pub_tasks.append(
            self.publish(
                f"{self.topic}/status/bridge/tcp_devices/connected",
                str(len(g.ncync_server.tcp_devices)).encode(),
            )
        )
        # total cync devices managed
        total_cync_devs = len(g.ncync_server.devices)
        entity_unique_id = f"{bridge_base_unique_id}_total_cync_devices"
        total_cync_devs_entity_conf = num_tcp_devices_entity_conf.copy()
        total_cync_devs_entity_conf["default_entity_id"] = entity_unique_id
        total_cync_devs_entity_conf["name"] = "Cync Devices Managed"
        total_cync_devs_entity_conf["state_topic"] = (
            f"{self.topic}/status/bridge/cync_devices/total"
        )
        total_cync_devs_entity_conf["unique_id"] = entity_unique_id
        # total_cync_devs_entity_conf["unit_of_measurement"] = "Cync device(s)"
        ret = await self.publish_json_msg(
            template_tpc.format(self.ha_topic, entity_type, entity_unique_id),
            total_cync_devs_entity_conf,
        )
        if ret is False:
            logger.warning(
                f"{lp} Failed to publish total Cync devices managed entity config"
            )
        pub_tasks.append(
            self.publish(
                f"{self.topic}/status/bridge/cync_devices/total",
                str(total_cync_devs).encode(),
            )
        )

        await asyncio.gather(*pub_tasks, return_exceptions=True)
        logger.debug(f"{lp} Bridge device config published and seeded")
        return ret

    async def publish(self, topic: str, msg_data: bytes):
        """Publish a message to the MQTT broker."""
        lp = f"{self.lp}publish:"
        if not self._connected:
            return False
        try:
            _ = await self.client.publish(topic, msg_data, qos=0, retain=False)
        except aiomqtt.MqttError as mqtt_code_exc:
            logger.warning(
                f"{lp} [MqttError] (rc: {mqtt_code_exc.rc}) -> {mqtt_code_exc}"
            )
            self._connected = False
        except asyncio.CancelledError as can_exc:
            logger.warning(f"{lp} [Task Cancelled] -> {can_exc}")
        except Exception as e:
            logger.warning(f"{lp} [Exception] -> {e}")
        else:
            return True
        return False

    async def publish_json_msg(self, topic: str, msg_data: dict) -> bool:
        lp = f"{self.lp}publish_msg:"
        try:
            _ = await self.client.publish(
                topic, json.dumps(msg_data).encode(), qos=0, retain=False
            )
        except aiomqtt.MqttError as mqtt_code_exc:
            logger.warning(
                f"{lp} [MqttError] (rc: {mqtt_code_exc.rc}) -> {mqtt_code_exc}"
            )
        except asyncio.CancelledError as can_exc:
            logger.warning(f"{lp} [Task Cancelled] -> {can_exc}")
        except Exception as e:
            logger.warning(f"{lp} [Exception] -> {e}")
        else:
            return True
        return False

    def kelvin2cync(self, k):
        """Convert Kelvin value to Cync white temp (0-100) with step size: 1"""
        max_k = CYNC_MAXK
        min_k = CYNC_MINK
        if k < min_k:
            return 0
        elif k > max_k:
            return 100
        scale = 100 / (max_k - min_k)
        ret = int(scale * (k - min_k))
        # logger.debug(f"{self.lp} Converting Kelvin: {k} using scale: {scale} (max_k={max_k}, min_k={min_k}) -> return value: {ret}")
        return ret

    def cync2kelvin(self, ct):
        """Convert Cync white temp (0-100) to Kelvin value"""
        max_k = CYNC_MAXK
        min_k = CYNC_MINK
        if ct <= 0:
            return min_k
        elif ct >= 100:
            return max_k
        scale = (max_k - min_k) / 100
        ret = min_k + int(scale * ct)
        # logger.debug(f"{self.lp} Converting Cync temp: {ct} using scale: {scale} (max_k={max_k}, min_k={min_k}) -> return value: {ret}")
        return ret
