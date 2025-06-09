import datetime
import json
import logging
import pickle
import random
import string
from typing import Optional

import aiohttp
import yaml

from cync_lan.const import *
from cync_lan.devices import CyncDevice
from cync_lan.structs import GlobalObject, ComputedTokenData

logger = logging.getLogger(CYNC_LOG_NAME)
g = GlobalObject()


class CyncCloudAPI:
    api_timeout: int = 8
    lp: str = "CyncCloudAPI"
    auth_cache_file = CYNC_CLOUD_AUTH_PATH
    token_cache: Optional[ComputedTokenData]
    http_session: Optional[aiohttp.ClientSession] = None
    _instance: Optional['CyncCloudAPI'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, **kwargs):
        self.api_timeout = kwargs.get("api_timeout", 8)
        self.lp = kwargs.get("lp", self.lp)

    async def close(self):
        """
        Close the aiohttp session if it exists and is not closed.
        """
        lp = f"{self.lp}:close:"
        if self.http_session and not self.http_session.closed:
            logger.debug(f"{lp} Closing aiohttp ClientSession")
            await self.http_session.close()
            self.http_session = None
        else:
            logger.debug(f"{lp} No aiohttp ClientSession to close or already closed")

    async def _check_session(self):
        """
        Check if the aiohttp session is initialized.
        If not, create a new session.
        """
        if not self.http_session or self.http_session.closed:
            logger.debug(f"{self.lp}:_check_session: Creating new aiohttp ClientSession")
            self.http_session = aiohttp.ClientSession()
            await self.http_session.__aenter__()

    async def read_token_cache(self) -> Optional[ComputedTokenData]:
        """
        Read the token cache from the file.
        Returns:
            CloudTokenData: The cached token data if available, otherwise None.
        """
        lp = f"{self.lp}:read_token_cache:"
        try:
            with open(self.auth_cache_file, "r") as f:
                token_data: Optional[ComputedTokenData] = pickle.load(f)
        except FileNotFoundError:
            logger.debug(f"{lp} Token cache file not found: {self.auth_cache_file}")
            return None
        else:
            if not token_data:
                logger.debug(f"{lp} Cached token data is EMPTY!")
                return None
            logger.debug(f"{lp} Cached token data read successfully")
            return token_data
            # add issued_at to the token data for computing the expiration datetime
            # iat = datetime.datetime.now(datetime.UTC)
            # token_data["issued_at"] = iat
            # return ComputedTokenData(**token_data)

    async def check_token(self) -> bool:
        """Check if we need to request a new OTP code for 2FA authentication."""
        lp = f"{self.lp}:check_tkn:"
        # read the token cache
        self.token_cache = await self.read_token_cache()
        if not self.token_cache:
            logger.debug(f"{lp} No cached token found, requesting OTP...")
            return False
        # check if the token is expired
        if self.token_cache.expires_at < datetime.datetime.now(datetime.UTC):
            logger.debug(f"{lp} Token expired, requesting OTP...")
            # token expired, request OTP
            return False
        else:
            logger.debug(f"{lp} Token is valid, using cached token")
            # token is valid, return the token data
        return True

    async def request_otp(self) -> bool:
        """
        Request an OTP code for 2FA authentication.
        The username and password are defined in the hass_add-on 'configuration' page
        """
        lp = f"{self.lp}:request_otp:"
        await self._check_session()
        req_otp_url = f"{CYNC_API_BASE}two_factor/email/verifycode"
        if not CYNC_ACCOUNT_USERNAME or not CYNC_ACCOUNT_PASSWORD:
            logger.error(f"{lp} Cync account username or password not set, cannot request OTP!")
            return False
        auth_data = {"corp_id": CYNC_CORP_ID, "email": CYNC_ACCOUNT_USERNAME, "local_lang": CYNC_ACCOUNT_LANGUAGE}
        sesh = self.http_session
        try:
            otp_r = await sesh.post(req_otp_url, json=auth_data, timeout=aiohttp.ClientTimeout(total=self.api_timeout))
            otp_r.raise_for_status()
        except aiohttp.ClientResponseError as e:
            logger.error(f"{lp} Failed to request OTP code: {e}")
            return False
        else:
            return True

    async def send_otp(self, otp_code: int) -> bool:
        lp = f"{self.lp}:send_otp:"
        await self._check_session()
        if not otp_code:
            logger.error("OTP code must be provided")
            return False
        elif not isinstance(otp_code, int):
            try:
                otp_code = int(otp_code)
            except ValueError:
                logger.error(f"{lp} OTP code must be an integer, got {type(otp_code)}")
                return False

        api_auth_url = f"{CYNC_API_BASE}user_auth/two_factor"
        auth_data = {
            "corp_id": CYNC_CORP_ID,
            "email": CYNC_ACCOUNT_USERNAME,
            "password": CYNC_ACCOUNT_PASSWORD,
            "two_factor": otp_code,
            "resource": ''.join(random.choices(string.ascii_lowercase, k=16)),
        }
        logger.debug(f"{lp} Sending OTP code: {otp_code} to Cync Cloud API for authentication")

        sesh = self.http_session
        try:
            r = await sesh.post(api_auth_url, json=auth_data, timeout=aiohttp.ClientTimeout(total=self.api_timeout))
            r.raise_for_status()
            iat = datetime.datetime.now(datetime.UTC)
            token_data = await r.json()
        except aiohttp.ClientResponseError as e:
            logger.error(f"Failed to authenticate: {e}")
            return False
        except json.JSONDecodeError as je:
            logger.error(f"Failed to decode JSON: {je}")
            return False
        except KeyError as ke:
            logger.error(f"Failed to get key from JSON: {ke}")
            return False
        else:
            # add issued_at to the token data for computing the expiration datetime
            token_data["issued_at"] = iat
            computed_token = ComputedTokenData(**token_data)
            await self.write_token_cache(computed_token)
            return True

    async def write_token_cache(self, tkn: ComputedTokenData) -> bool:
        """
        Write the token cache to the file.
        Args:
            tkn (ComputedTokenData): The token data to write to the cache.
        Returns:
            bool: True if the write was successful, False otherwise.
        """
        lp = f"{self.lp}:write_token_cache:"
        try:
            with open(self.auth_cache_file, "wb") as f:
                pickle.dump(tkn, f)
        except Exception as e:
            logger.error(f"{lp} Failed to write token cache: {e}")
            return False
        else:
            logger.debug(f"{lp} Token cache written successfully to: {self.auth_cache_file}")
            self.token_cache = tkn
            return True

    async def request_devices(self):
        """Get a list of devices for a particular user."""
        lp = f"{self.lp}:get_devices:"
        await self._check_session()
        user_id = self.token_cache.user_id
        access_token = self.token_cache.access_token
        api_devices_url = f"{CYNC_API_BASE}user/{user_id}/subscribe/devices"
        headers = {"Access-Token": access_token}
        sesh = self.http_session
        try:
            r = await sesh.get(
                api_devices_url, headers=headers, timeout=aiohttp.ClientTimeout(total=self.api_timeout)
            )
        except aiohttp.ClientResponseError as e:
            logger.error(f"{lp} Failed to get devices: {e}")
            raise e
        except json.JSONDecodeError as je:
            logger.error(f"{lp} Failed to decode JSON: {je}")
            raise je
        except KeyError as ke:
            logger.error(f"{lp} Failed to get key from JSON: {ke}")
            raise ke
        else:
            ret = await r.json()

        # {'error': {'msg': 'Access-Token Expired', 'code': 4031021}}
        if "error" in ret:
            error_data = ret["error"]
            if (
                    "msg" in error_data
                    and error_data["msg"]
                    and error_data["msg"].lower() == "access-token expired"
            ):
                logger.error(f"{lp} Access-Token expired, you need to re-authenticate!")
                # logger.error(f"{lp} Access-Token expired, re-authenticating...")
                # return self.get_devices(*self.authenticate_2fa())
        return ret

    async def get_properties(self, product_id: str, device_id: str):
        """Get properties for a single device. Properties contain a device list (bulbsArray), groups (groupsArray), and saved light effects (lightShows)."""
        lp = f"{self.lp}:get_properties:"
        await self._check_session()
        access_token = self.token_cache.access_token
        api_device_prop_url = f"{CYNC_API_BASE}product/{product_id}/device/{device_id}/property"
        headers = {"Access-Token": access_token}
        sesh = self.http_session
        try:
            r = await sesh.get(
                api_device_prop_url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.api_timeout),
            )
            ret = await r.json()
        except aiohttp.ClientResponseError as e:
            logger.error(f"{lp} Failed to get device properties: {e}")
        except json.JSONDecodeError as je:
            logger.error(f"{lp} Failed to decode JSON: {je}")
            raise je
        except KeyError as ke:
            logger.error(f"{lp} Failed to get key from JSON: {ke}")
            raise ke

        # {'error': {'msg': 'Access-Token Expired', 'code': 4031021}}
        logit = False
        if "error" in ret:
            error_data = ret["error"]
            if (
                    "msg" in error_data
                    and error_data["msg"]
            ):
                if error_data["msg"].lower() == "access-token expired":
                    raise Exception(f"{lp} Access-Token expired, you need to re-authenticate!")
                    # logger.error("Access-Token expired, re-authenticating...")
                    # return self.get_devices(*self.authenticate_2fa())
                else:
                    logit = True

                if 'code' in error_data:
                    cync_err_code = error_data['code']
                    if cync_err_code == 4041009:
                        # no properties for this home ID
                        # I've noticed lots of empty homes in the returned data,
                        # we only parse homes with an assigned name and a 'bulbsArray'
                        logit = False
                    else:
                        logger.debug(f"{lp} DBG>>> error code != 4041009 (int) ---> {type(cync_err_code) = } -- {cync_err_code =} /// setting logit = True")
                        logit = True
                else:
                    logger.debug(f"{lp} DBG>>> no 'code' in error data, setting logit = True")
                    logit = True
            if logit is True:
                logger.warning(f"{lp} Cync Cloud API Error: {error_data}")
        return ret


    async def export_config_file(self) -> bool:
        """Get Cync devices from the cloud """
        mesh_networks = await self.request_devices()
        for mesh in mesh_networks:
            mesh["properties"] = await self.get_properties(
                mesh["product_id"], mesh["id"]
            )
        mesh_config = await self._mesh_to_config(mesh_networks)
        try:
            with open(CYNC_CONFIG_FILE_PATH, "w") as f:
                if CYNC_ADDON_UUID:
                    f.write("# DO NOT CHANGE THE UUID!!!\n")
                    f.write("# It is used for the CyncLAN Controller/Bridge device in HASS\n")
                    f.write(f"uuid: {CYNC_ADDON_UUID}\n")
                f.write(yaml.dump(mesh_config))
        except Exception as file_exc:
            logger.error(f"{self.lp} Failed to write mesh config to file: {CYNC_CONFIG_FILE_PATH} -> {file_exc}")
            return False
        else:
            return True

    async def _mesh_to_config(self, mesh_info):
        """Take exported cloud data and format it into a working config dict to be dumped in YAML format."""
        lp = f"{self.lp}:export config:"
        mesh_conf = {}
        # What we get from the Cync cloud API
        raw_file_out = f"{PERSISTENT_BASE_DIR}/raw_mesh.cync"
        try:
            with open(raw_file_out, "w") as _f:
                _f.write(yaml.dump(mesh_info))
        except Exception as file_exc:
            logger.error(f"{lp} Failed to write raw config from Cync account to file: '{raw_file_out}' -> {file_exc}")
        else:
            logger.debug(f"{lp} Dumped raw config from Cync account to file: {raw_file_out}")
        for mesh_ in mesh_info:
            if "name" not in mesh_ or len(mesh_["name"]) < 1:
                logger.debug(f"{lp} No name found for mesh, skipping...")
                continue
            if "properties" not in mesh_:
                logger.debug(
                    f"{lp} No properties found for mesh, skipping..."
                )
                continue
            elif "bulbsArray" not in mesh_["properties"]:
                logger.debug(
                    f"{lp} No 'bulbsArray' in properties, skipping..."
                )
                continue

            new_mesh = {
                kv: mesh_[kv] for kv in ("access_key", "id", "mac") if kv in mesh_
            }
            mesh_conf[mesh_["name"]] = new_mesh

            logger.debug(f"{lp} 'properties' and 'bulbsArray' found in exported config, processing...")
            new_mesh["devices"] = {}
            for cfg_bulb in mesh_["properties"]["bulbsArray"]:
                if any(
                        checkattr not in cfg_bulb
                        for checkattr in (
                                "deviceID",
                                "displayName",
                                "mac",
                                "deviceType",
                                "wifiMac",
                                "firmwareVersion"
                        )
                ):
                    logger.warning(
                        f"{lp} Missing required attribute in Cync bulb, skipping: {cfg_bulb}"
                    )
                    continue
                new_dev_dict = {}
                # last 3 digits of deviceID
                __id = int(str(cfg_bulb["deviceID"])[-3:])
                wifi_mac = str(cfg_bulb["wifiMac"])
                _mac = str(cfg_bulb["mac"])
                name = str(cfg_bulb["displayName"])
                _type = int(cfg_bulb["deviceType"])
                _fw_ver = str(cfg_bulb["firmwareVersion"])
                # data from: https://github.com/baudneo/cync-lan/issues/8
                # { "hvacSystem": { "changeoverMode": 0, "auxHeatStages": 1, "auxFurnaceType": 1, "stages": 1, "furnaceType": 1, "type": 2, "powerLines": 1 },
                # "thermostatSensors": [ { "pin": "025572", "name": "Living Room", "type": "savant" }, { "pin": "044604", "name": "Bedroom Sensor", "type": "savant" }, { "pin": "022724", "name": "Thermostat sensor 3", "type": "savant" } ] } ]
                hvac_cfg = None
                if 'hvacSystem' in cfg_bulb:
                    hvac_cfg = cfg_bulb["hvacSystem"]
                    if "thermostatSensors" in cfg_bulb:
                        hvac_cfg["thermostatSensors"] = cfg_bulb["thermostatSensors"]
                    logger.debug(f"{lp} Found HVAC device '{name}' (ID: {__id}): {hvac_cfg}")
                    new_dev_dict["hvac"] = hvac_cfg

                cync_device = CyncDevice(
                    name=name,
                    cync_id=__id,
                    cync_type=_type,
                    mac=_mac,
                    wifi_mac=wifi_mac,
                    fw_version=_fw_ver,
                    hvac=hvac_cfg,
                )
                for attr_set in (
                        "name",
                        "mac",
                        "wifi_mac",
                ):
                    value = getattr(cync_device, attr_set)
                    if value:
                        new_dev_dict[attr_set] = value
                    else:
                        logger.warning(f"{lp} Attribute not found for bulb: {attr_set}")
                new_dev_dict["type"] = _type
                new_dev_dict["is_plug"] = cync_device.is_plug
                new_dev_dict["supports_temperature"] = cync_device.supports_temperature
                new_dev_dict["supports_rgb"] = cync_device.supports_rgb
                new_dev_dict["fw"] = _fw_ver

                new_mesh["devices"][__id] = new_dev_dict

        config_dict = {
            "account data": mesh_conf
        }

        return config_dict
