import math
from contextlib import ExitStack
from typing import Mapping, NewType, Optional

from afancontrol.arduino import ArduinoConnection, ArduinoName
from afancontrol.configparser import ConfigParserSection
from afancontrol.exec import Programs
from afancontrol.pwmfan import (
    BaseFanPWMRead,
    BaseFanPWMWrite,
    BaseFanSpeed,
    FanName,
    FanValue,
    PWMValue,
    ReadOnlyFan,
    ReadonlyFanName,
    ReadWriteFan,
)

PWMValueNorm = NewType("PWMValueNorm", float)  # [0..1]


class ReadonlyPWMFanNorm:
    def __init__(
        self, fan_speed: BaseFanSpeed, pwm_read: Optional[BaseFanPWMRead] = None
    ) -> None:
        self.fan_speed = fan_speed
        self.pwm_read = pwm_read
        self._stack: Optional[ExitStack] = None

    @classmethod
    def from_configparser(
        cls,
        section: ConfigParserSection[ReadonlyFanName],
        arduino_connections: Mapping[ArduinoName, ArduinoConnection],
        programs: Programs,
    ) -> "ReadonlyPWMFanNorm":
        readonly_fan = ReadOnlyFan.from_configparser(
            section, arduino_connections, programs
        )
        return cls(readonly_fan.fan_speed, readonly_fan.pwm_read)

    def __enter__(self):
        self._stack = ExitStack()
        try:
            self._stack.enter_context(self.fan_speed)
            if self.pwm_read is not None:
                self._stack.enter_context(self.pwm_read)
        except Exception:
            self._stack.close()
            raise
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        assert self._stack is not None
        self._stack.close()

    def get_speed(self) -> FanValue:
        return self.fan_speed.get_speed()

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self.fan_speed == other.fan_speed and self.pwm_read == other.pwm_read

        return NotImplemented

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return "%s(%r, %r)" % (type(self).__name__, self.fan_speed, self.pwm_read)

    def is_pwm_stopped(self, pwm: Optional[PWMValue]) -> Optional[bool]:
        if self.pwm_read is None:
            return None
        if pwm is None:
            return None
        return type(self.pwm_read).is_pwm_stopped(pwm)

    def get_raw(self) -> Optional[PWMValue]:
        if self.pwm_read is None:
            return None
        return self.pwm_read.get()

    def get(self) -> Optional[PWMValueNorm]:
        if self.pwm_read is None:
            return None
        raw = self.get_raw()
        assert raw is not None
        return PWMValueNorm(raw / self.pwm_read.max_pwm)


class PWMFanNorm:
    def __init__(
        self,
        fan_speed: BaseFanSpeed,
        pwm_read: BaseFanPWMRead,
        pwm_write: BaseFanPWMWrite,
        *,
        pwm_line_start: PWMValue,
        pwm_line_end: PWMValue,
        never_stop: bool = False
    ) -> None:
        self.fan_speed = fan_speed
        self.pwm_read = pwm_read
        self.pwm_write = pwm_write
        self.pwm_line_start = pwm_line_start
        self.pwm_line_end = pwm_line_end
        self.never_stop = never_stop
        if type(self.pwm_read).min_pwm > self.pwm_line_start:
            raise ValueError(
                "Invalid pwm_line_start. Expected: min_pwm <= pwm_line_start. "
                "Got: %s <= %s" % (type(self.pwm_read).min_pwm, self.pwm_line_start)
            )
        if self.pwm_line_end > type(self.pwm_read).max_pwm:
            raise ValueError(
                "Invalid pwm_line_end. Expected: pwm_line_end <= max_pwm. "
                "Got: %s <= %s" % (self.pwm_line_end, type(self.pwm_read).max_pwm)
            )
        self._stack: Optional[ExitStack] = None

    @classmethod
    def from_configparser(
        cls,
        section: ConfigParserSection[FanName],
        arduino_connections: Mapping[ArduinoName, ArduinoConnection],
    ) -> "PWMFanNorm":
        readwrite_fan = ReadWriteFan.from_configparser(section, arduino_connections)
        never_stop = section.getboolean("never_stop", fallback=True)
        pwm_line_start = PWMValue(section.getint("pwm_line_start", fallback=100))
        pwm_line_end = PWMValue(section.getint("pwm_line_end", fallback=240))

        for pwm_value in (pwm_line_start, pwm_line_end):
            if not (
                readwrite_fan.pwm_read.min_pwm
                <= pwm_value
                <= readwrite_fan.pwm_read.max_pwm
            ):
                raise RuntimeError(
                    "Incorrect PWM value '%s' for fan '%s': it must be within [%s;%s]"
                    % (
                        pwm_value,
                        section.name,
                        readwrite_fan.pwm_read.min_pwm,
                        readwrite_fan.pwm_read.max_pwm,
                    )
                )
        if pwm_line_start >= pwm_line_end:
            raise RuntimeError(
                "`pwm_line_start` PWM value must be less than `pwm_line_end` for fan '%s'"
                % (section.name,)
            )

        return cls(
            readwrite_fan.fan_speed,
            readwrite_fan.pwm_read,
            readwrite_fan.pwm_write,
            pwm_line_start=pwm_line_start,
            pwm_line_end=pwm_line_end,
            never_stop=never_stop,
        )

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return (
                self.fan_speed == other.fan_speed
                and self.pwm_read == other.pwm_read
                and self.pwm_write == other.pwm_write
                and self.pwm_line_start == other.pwm_line_start
                and self.pwm_line_end == other.pwm_line_end
                and self.never_stop == other.never_stop
            )

        return NotImplemented

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return "%s(%r, %r, %r, pwm_line_start=%r, pwm_line_end=%r, never_stop=%r)" % (
            type(self).__name__,
            self.fan_speed,
            self.pwm_read,
            self.pwm_write,
            self.pwm_line_start,
            self.pwm_line_end,
            self.never_stop,
        )

    def __enter__(self):
        self._stack = ExitStack()
        try:
            self._stack.enter_context(self.fan_speed)
            self._stack.enter_context(self.pwm_read)
            self._stack.enter_context(self.pwm_write)
        except Exception:
            self._stack.close()
            raise
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        assert self._stack is not None
        self._stack.close()

    def get_speed(self) -> FanValue:
        return self.fan_speed.get_speed()

    def is_pwm_stopped(self, pwm: PWMValue) -> bool:
        return type(self.pwm_read).is_pwm_stopped(pwm)

    def set_full_speed(self) -> None:
        self.pwm_write.set_full_speed()

    def get_raw(self) -> PWMValue:
        return self.pwm_read.get()

    def get(self) -> PWMValueNorm:
        return PWMValueNorm(self.get_raw() / self.pwm_read.max_pwm)

    def set(self, pwm_norm: PWMValueNorm) -> PWMValue:
        # TODO validate this formula
        pwm_norm = max(pwm_norm, PWMValueNorm(0.0))
        pwm_norm = min(pwm_norm, PWMValueNorm(1.0))
        pwm = pwm_norm * self.pwm_line_end
        if 0 < pwm < self.pwm_line_start:
            pwm = self.pwm_line_start
        if pwm <= 0 and self.never_stop:
            pwm = self.pwm_line_start
        if pwm_norm >= 1.0:
            pwm = self.pwm_read.max_pwm

        pwm = PWMValue(int(math.ceil(pwm)))
        self.pwm_write.set(pwm)
        return pwm
