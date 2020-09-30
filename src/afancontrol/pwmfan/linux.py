from pathlib import Path
from typing import NewType

from afancontrol.configparser import ConfigParserSection
from afancontrol.pwmfan.base import (
    BaseFanPWMRead,
    BaseFanPWMWrite,
    BaseFanSpeed,
    FanValue,
    PWMValue,
)

PWMDevice = NewType("PWMDevice", str)
FanInputDevice = NewType("FanInputDevice", str)


class LinuxFanSpeed(BaseFanSpeed):
    __slots__ = ("_fan_input",)

    def __init__(self, fan_input: FanInputDevice) -> None:
        self._fan_input = Path(fan_input)

    @classmethod
    def from_configparser(cls, section: ConfigParserSection) -> BaseFanSpeed:
        return cls(FanInputDevice(section["fan_input"]))

    def get_speed(self) -> FanValue:
        return FanValue(int(self._fan_input.read_text()))


class LinuxFanPWMRead(BaseFanPWMRead):
    __slots__ = ("_pwm",)

    max_pwm = PWMValue(255)
    min_pwm = PWMValue(0)

    def __init__(self, pwm: PWMDevice) -> None:
        self._pwm = Path(pwm)

    @classmethod
    def from_configparser(cls, section: ConfigParserSection) -> BaseFanPWMRead:
        return cls(PWMDevice(section["pwm"]))

    def get(self) -> PWMValue:
        return PWMValue(int(self._pwm.read_text()))


class LinuxFanPWMWrite(BaseFanPWMWrite):
    __slots__ = "_pwm", "_pwm_enable"

    read_cls = LinuxFanPWMRead

    def __init__(self, pwm: PWMDevice) -> None:
        self._pwm = Path(pwm)
        self._pwm_enable = Path(pwm + "_enable")

    @classmethod
    def from_configparser(cls, section: ConfigParserSection) -> BaseFanPWMWrite:
        return cls(PWMDevice(section["pwm"]))

    def _set_raw(self, pwm: PWMValue) -> None:
        self._pwm.write_text(str(int(pwm)))

    def __enter__(self):  # reusable
        # fancontrol way of doing it
        if self._pwm_enable.is_file():
            self._pwm_enable.write_text("1")
        self.set_full_speed()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        # fancontrol way of doing it
        if not self._pwm_enable.is_file():
            self.set_full_speed()
            return

        self._pwm_enable.write_text("0")
        if self._pwm_enable.read_text().strip() == "0":
            return

        self._pwm_enable.write_text("1")
        self.set_full_speed()

        if (
            self._pwm_enable.read_text().strip() == "1"
            and int(self._pwm.read_text()) >= self.read_cls.max_pwm
        ):
            return

        raise RuntimeError("Couldn't disable PWM on the fan %r" % self)
