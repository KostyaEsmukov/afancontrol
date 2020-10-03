from typing import Mapping, NamedTuple, NewType, Optional, Union

from afancontrol.arduino import ArduinoConnection, ArduinoName
from afancontrol.configparser import ConfigParserSection
from afancontrol.exec import Programs
from afancontrol.pwmfan.arduino import (
    ArduinoFanPWMRead,
    ArduinoFanPWMWrite,
    ArduinoFanSpeed,
)
from afancontrol.pwmfan.base import (
    BaseFanPWMRead,
    BaseFanPWMWrite,
    BaseFanSpeed,
    FanValue,
    PWMValue,
)
from afancontrol.pwmfan.ipmi import FreeIPMIFanSpeed
from afancontrol.pwmfan.linux import (
    FanInputDevice,
    LinuxFanPWMRead,
    LinuxFanPWMWrite,
    LinuxFanSpeed,
    PWMDevice,
)

__all__ = (
    "ArduinoFanPWMRead",
    "ArduinoFanPWMWrite",
    "ArduinoFanSpeed",
    "BaseFanPWMRead",
    "BaseFanPWMWrite",
    "BaseFanSpeed",
    "FanInputDevice",
    "FanValue",
    "FreeIPMIFanSpeed",
    "LinuxFanPWMRead",
    "LinuxFanPWMWrite",
    "LinuxFanSpeed",
    "PWMDevice",
    "PWMValue",
)

DEFAULT_FAN_TYPE = "linux"

FanName = NewType("FanName", str)
ReadonlyFanName = NewType("ReadonlyFanName", str)
AnyFanName = Union[FanName, ReadonlyFanName]


class ReadOnlyFan(NamedTuple):
    fan_speed: BaseFanSpeed
    pwm_read: Optional[BaseFanPWMRead]

    @classmethod
    def from_configparser(
        cls,
        section: ConfigParserSection[ReadonlyFanName],
        arduino_connections: Mapping[ArduinoName, ArduinoConnection],
        programs: Programs,
    ) -> "ReadOnlyFan":
        fan_type = section.get("type", fallback=DEFAULT_FAN_TYPE)

        if fan_type == "linux":
            return cls(
                fan_speed=LinuxFanSpeed.from_configparser(section),
                pwm_read=(
                    LinuxFanPWMRead.from_configparser(section)
                    if "pwm" in section
                    else None
                ),
            )
        elif fan_type == "arduino":
            return cls(
                fan_speed=ArduinoFanSpeed.from_configparser(
                    section, arduino_connections
                ),
                pwm_read=(
                    ArduinoFanPWMRead.from_configparser(section, arduino_connections)
                    if "pwm_pin" in section
                    else None
                ),
            )
        elif fan_type == "freeipmi":
            return cls(
                fan_speed=FreeIPMIFanSpeed.from_configparser(section, programs),
                pwm_read=None,
            )
        else:
            raise ValueError(
                "Unsupported FAN type %s. Supported ones are "
                "`linux`, `arduino`, `freeipmi`." % fan_type
            )


class ReadWriteFan(NamedTuple):
    fan_speed: BaseFanSpeed
    pwm_read: BaseFanPWMRead
    pwm_write: BaseFanPWMWrite

    @classmethod
    def from_configparser(
        cls,
        section: ConfigParserSection[FanName],
        arduino_connections: Mapping[ArduinoName, ArduinoConnection],
    ) -> "ReadWriteFan":
        fan_type = section.get("type", fallback=DEFAULT_FAN_TYPE)

        if fan_type == "linux":
            return cls(
                fan_speed=LinuxFanSpeed.from_configparser(section),
                pwm_read=LinuxFanPWMRead.from_configparser(section),
                pwm_write=LinuxFanPWMWrite.from_configparser(section),
            )
        elif fan_type == "arduino":
            return cls(
                fan_speed=ArduinoFanSpeed.from_configparser(
                    section, arduino_connections
                ),
                pwm_read=ArduinoFanPWMRead.from_configparser(
                    section, arduino_connections
                ),
                pwm_write=ArduinoFanPWMWrite.from_configparser(
                    section, arduino_connections
                ),
            )
        else:
            raise ValueError(
                "Unsupported FAN type %s. Supported ones are "
                "`linux` and `arduino`." % fan_type
            )
