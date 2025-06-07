from enum import StrEnum
from typing import Annotated, Optional, Union

from pydantic.dataclasses import dataclass
from pydantic import Field

class DeviceClassification(StrEnum):
    LIGHT = "light"
    SWITCH = "switch"
    THERMOSTAT = "thermostat"
    CONTROLLER = "controller"
    UNKNOWN = "unknown"

@dataclass
class SwitchCapabilities:
    power: bool = True
    dimmable: bool = False

@dataclass
class LightCapabilities:
    power: bool = True
    dimmable: bool = False
    tunable_white: bool = False
    dynamic: bool = False
    color: bool = False
    colour: Annotated[bool, Field(alias="color")] = False


@dataclass
class DeviceProtocol:
    BTLE: bool = True
    TCP: bool = False
    MATTER: bool = False

@dataclass
class DeviceTypeInfo:
    type: DeviceClassification
    model_name: Optional[str] = None
    model_id: Optional[str] = None
    lumens: Optional[int] = None
    protocol: DeviceProtocol = Field(default_factory=DeviceProtocol)
    Capabilities: Union[LightCapabilities, SwitchCapabilities, None] = None

# device_type_map = {
#     # deviceType|int : info|DeviceTypeInfo
#     5:
#         DeviceTypeInfo(**{
#         "type": DeviceClassification.LIGHT,
#         "model_name": "Tunable White A19 Bulb",
#         "model_id": None,
#         "lumens": 800,
#         "protocol": DeviceProtocol(TCP=True, BTLE=True, MATTER=False),
#         "Capabilities": LightCapabilities(power=True, dimmable=True, tunable_white=True),
#         }),
#
#     19: "Tunable White A19 Bulb",
#     21: "C by GE Full Color A19 Bulb (BTLE only) [CLEDA1911C2 760 lum]",
#     22: "C by GE Full Color BR30 Bulb (BTLE only) [CLEDR3010C2 700 lum]",
#     26: "C by GE BR30 (BTLE only) Tunable White 2000-7000K [CLEDR309S2 800 lum]",
#     30: "C by GE Full Color A19 Bulb (BTLE only) [CLEDA1911C2 760 lum]",
#     31: "C by GE Full Color A19 Bulb (BTLE only) [CLEDA1911C2 800 lum]",
#
#     37: "Dimmer Switch with Motion and Ambient Light [CSWDMOCBWF1]",
#
#     42: "Reveal HD+ Full Color Under Cabinet Light - 18 Inch",
#     43: "Reveal HD+ Full Color Under Cabinet Light - 24 Inch",
#
#     48: {
#         "type": DeviceClassification.SWITCH,
#         "model_name": "C by GE (C Start Smart) Switch",
#         "model_id": "CSWDMBLBWF1",
#         "protocol": DeviceProtocol(TCP=True),
#         "Capabilities": SwitchCapabilities(),
#     },
#     49: {
#         "type": DeviceClassification.SWITCH,
#         "model_name": "C by GE (C Start Smart) Dimmer Switch with Motion and Ambient Light",
#         "model_id": "CSWDMOCBWF1",
#         "protocol": DeviceProtocol(TCP=True, BTLE=True),
#         "Capabilities": SwitchCapabilities(dimmable=True),
#     },
#     52: "Switch",
#     55: "Dimmer Switch - No Neutral",
#     58: "Switch - No Neutral",
#     59: "Switch",
#     64: "Indoor Plug",
#     68: "Indoor Plug",
#
#     113: "Wire-Free Dimmer with White Temperature Switch (BTLE only)",
#
#     131: "Full Color A19 Bulb",
#     133: "Full Color LED Light Strip Controller",
#     137: "Full Color A19 Bulb",
#     138: "Full Color BR30 Floodlight [CLEDR309CD1 750 lum]",
#     140: "Full Color Outdoor PAR38 Floodlight [CLEDP3815CD1 1300 lum]",
#     146: "Full Color Edison ST19 Bulb [CLEDST196CDGS 500 lum]",
#     147: "Full Color Edison G25 Bulb [CLEDG256CDGS 500 lum]",
#     148: "White (2700K) Edison ST19 Bulb",
#     152: "Reveal HD+ White (2700K) A19 Bulb",
#
#     169: "Reveal HD+ Full Color 4 Inch Wafer Downlight [CFIXCNLR4CRVD 760 lum]",
#
#     224: "Thermostat",
# }

device_type_map = {
    # deviceType|int : info|DeviceTypeInfo
    5: DeviceTypeInfo(
        type=DeviceClassification.LIGHT,
        model_name="Tunable White A19 Bulb",
        model_id=None,
        lumens=800,
        protocol=DeviceProtocol(TCP=True, BTLE=True, MATTER=False),
        Capabilities=LightCapabilities(power=True, dimmable=True, tunable_white=True),
    ),
    19: DeviceTypeInfo(
        type=DeviceClassification.LIGHT,
        model_name="Tunable White A19 Bulb",
    ),
    21: DeviceTypeInfo(
        type=DeviceClassification.LIGHT,
        model_name="C by GE Full Color A19 Bulb (BTLE only) [CLEDA1911C2 760 lum]",
        model_id="CLEDA1911C2",
        lumens=760,
    ),
    22: DeviceTypeInfo(
        type=DeviceClassification.LIGHT,
        model_name="C by GE Full Color BR30 Bulb (BTLE only) [CLEDR3010C2 700 lum]",
        model_id="CLEDR3010C2",
        lumens=700,
    ),
    26: DeviceTypeInfo(
        type=DeviceClassification.LIGHT,
        model_name="C by GE BR30 (BTLE only) Tunable White 2000-7000K [CLEDR309S2 800 lum]",
        model_id="CLEDR309S2",
        lumens=800,
    ),
    30: DeviceTypeInfo(
        type=DeviceClassification.LIGHT,
        model_name="C by GE Full Color A19 Bulb (BTLE only) [CLEDA1911C2 760 lum]",
        model_id="CLEDA1911C2",
        lumens=760,
    ),
    31: DeviceTypeInfo(
        type=DeviceClassification.LIGHT,
        model_name="C by GE Full Color A19 Bulb (BTLE only) [CLEDA1911C2 800 lum]",
        model_id="CLEDA1911C2",
        lumens=800,
    ),
    37: DeviceTypeInfo(
        type=DeviceClassification.SWITCH,
        model_name="Dimmer Switch with Motion and Ambient Light [CSWDMOCBWF1]",
        model_id="CSWDMOCBWF1",
    ),
    42: DeviceTypeInfo(
        type=DeviceClassification.LIGHT,
        model_name="Reveal HD+ Full Color Under Cabinet Light - 18 Inch",
    ),
    43: DeviceTypeInfo(
        type=DeviceClassification.LIGHT,
        model_name="Reveal HD+ Full Color Under Cabinet Light - 24 Inch",
    ),
    48: DeviceTypeInfo(
        type=DeviceClassification.SWITCH,
        model_name="C by GE (C Start Smart) Switch",
        model_id="CSWDMBLBWF1",
        protocol=DeviceProtocol(TCP=True),
        Capabilities=SwitchCapabilities(),
    ),
    49: DeviceTypeInfo(
        type=DeviceClassification.SWITCH,
        model_name="C by GE (C Start Smart) Dimmer Switch with Motion and Ambient Light",
        model_id="CSWDMOCBWF1",
        protocol=DeviceProtocol(TCP=True, BTLE=True),
        Capabilities=SwitchCapabilities(dimmable=True),
    ),
    52: DeviceTypeInfo(
        type=DeviceClassification.SWITCH,
        model_name="Switch",
    ),
    55: DeviceTypeInfo(
        type=DeviceClassification.SWITCH,
        model_name="Dimmer Switch - No Neutral",
    ),
    58: DeviceTypeInfo(
        type=DeviceClassification.SWITCH,
        model_name="Switch - No Neutral",
    ),
    59: DeviceTypeInfo(
        type=DeviceClassification.SWITCH,
        model_name="Switch",
    ),
    64: DeviceTypeInfo(
        type=DeviceClassification.CONTROLLER,
        model_name="Indoor Plug",
    ),
    68: DeviceTypeInfo(
        type=DeviceClassification.CONTROLLER,
        model_name="Indoor Plug",
    ),
    113: DeviceTypeInfo(
        type=DeviceClassification.SWITCH,
        model_name="Wire-Free Dimmer with White Temperature Switch (BTLE only)",
    ),
    131: DeviceTypeInfo(
        type=DeviceClassification.LIGHT,
        model_name="Full Color A19 Bulb",
    ),
    133: DeviceTypeInfo(
        type=DeviceClassification.CONTROLLER,
        model_name="Full Color LED Light Strip Controller",
    ),
    137: DeviceTypeInfo(
        type=DeviceClassification.LIGHT,
        model_name="Full Color A19 Bulb",
    ),
    138: DeviceTypeInfo(
        type=DeviceClassification.LIGHT,
        model_name="Full Color BR30 Floodlight [CLEDR309CD1 750 lum]",
        lumens=750,
        model_id="CLEDR309CD1",
    ),
    140: DeviceTypeInfo(
        type=DeviceClassification.LIGHT,
        model_name="Full Color Outdoor PAR38 Floodlight [CLEDP3815CD1 1300 lum]",
        lumens=1300,
        model_id="CLEDP3815CD1",
    ),
    146: DeviceTypeInfo(
        type=DeviceClassification.LIGHT,
        model_name="Full Color Edison ST19 Bulb [CLEDST196CDGS 500 lum]",
        lumens=500,
        model_id="CLEDST196CDGS",
    ),
    147: DeviceTypeInfo(
        type=DeviceClassification.LIGHT,
        model_name="Full Color Edison G25 Bulb [CLEDG256CDGS 500 lum]",
        lumens=500,
        model_id="CLEDG256CDGS",
    ),
    148: DeviceTypeInfo(
        type=DeviceClassification.LIGHT,
        model_name="White (2700K) Edison ST19 Bulb",
    ),
    152: DeviceTypeInfo(
        type=DeviceClassification.LIGHT,
        model_name="Reveal HD+ White (2700K) A19 Bulb",
    ),
    169: DeviceTypeInfo(
        type=DeviceClassification.LIGHT,
        lumens=760,
        model_id="CFIXCNLR4CRVD",
        model_name="Reveal HD+ Full Color 4 Inch Wafer Downlight [CFIXCNLR4CRVD 760 lum]",
    ),
    224: DeviceTypeInfo(
        type=DeviceClassification.THERMOSTAT,
        model_name="Thermostat",
    ),
}