import abc
import math
from pathlib import Path
from typing import NewType

PWMDevice = NewType("PWMDevice", str)
FanInputDevice = NewType("FanInputDevice", str)
PWMValue = NewType("PWMValue", int)  # [0..255]
PWMValueNorm = NewType("PWMValueNorm", float)  # [0..1]
FanValue = NewType("FanValue", int)


class BasePWMFan(abc.ABC):
    max_pwm = PWMValue(255)
    min_pwm = PWMValue(0)

    def __init__(self, pwm: PWMDevice, fan_input: FanInputDevice):
        self._pwm = Path(pwm)
        self._pwm_enable = Path(pwm + "_enable")
        self._fan_input = Path(fan_input)

    def is_stopped(self) -> bool:
        return type(self).is_pwm_stopped(self._get_raw())

    @staticmethod
    def is_pwm_stopped(pwm: PWMValue) -> bool:
        return pwm <= 0

    def _get_raw(self) -> PWMValue:
        return PWMValue(int(self._pwm.read_text()))

    def _set_raw(self, pwm: PWMValue) -> None:
        if not (BasePWMFan.min_pwm <= pwm <= BasePWMFan.max_pwm):
            raise ValueError(
                "Invalid pwm value %s: it must be within [%s..%s]"
                % (pwm, BasePWMFan.min_pwm, BasePWMFan.max_pwm)
            )
        self._pwm.write_text(str(int(pwm)))

    def set_full_speed(self) -> None:
        self._set_raw(BasePWMFan.max_pwm)

    def __enter__(self):  # reentrant
        """Enable PWM control for this fan"""
        # fancontrol way of doing it
        if self._pwm_enable.is_file():
            self._pwm_enable.write_text("1")
        self.set_full_speed()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        """Disable PWM control for this fan"""
        # fancontrol way of doing it
        if not self._pwm_enable.is_file():
            self.set_full_speed()
            return

        self._pwm_enable.write_text("0")
        if self._pwm_enable.read_text() == "0":
            return

        self._pwm_enable.write_text("1")
        self.set_full_speed()

        if (
            self._pwm_enable.read_text() == "1"
            and self._get_raw() >= BasePWMFan.max_pwm
        ):
            return

        raise RuntimeError("Couldn't disable PWM on that fan")

    def get_speed(self) -> FanValue:
        """Get current RPM for this fan"""
        return FanValue(int(self._fan_input.read_text()))


class PWMFan(BasePWMFan):  # Used by the afancontrol.fantest module
    def get(self) -> PWMValue:
        return self._get_raw()

    def set(self, pwm: PWMValue) -> None:
        self._set_raw(pwm)

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return (
                self._pwm == other._pwm
                and self._pwm_enable == other._pwm_enable
                and self._fan_input == other._fan_input
            )

        return NotImplemented

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return "%s(%r, %r)" % (
            type(self).__name__,
            str(self._pwm),
            str(self._fan_input),
        )


class PWMFanNorm(BasePWMFan):
    def __init__(
        self,
        pwm: PWMDevice,
        fan_input: FanInputDevice,
        *,
        pwm_line_start: PWMValue,
        pwm_line_end: PWMValue,
        never_stop: bool = False
    ) -> None:
        super().__init__(pwm, fan_input)
        self.pwm_line_start = pwm_line_start
        self.pwm_line_end = pwm_line_end
        self.never_stop = never_stop
        if BasePWMFan.min_pwm > self.pwm_line_start:
            raise ValueError(
                "Invalid pwm_line_start. Expected: min_pwm <= pwm_line_start. "
                "Got: %s <= %s" % (BasePWMFan.min_pwm, self.pwm_line_start)
            )
        if self.pwm_line_end > BasePWMFan.max_pwm:
            raise ValueError(
                "Invalid pwm_line_end. Expected: pwm_line_end <= max_pwm. "
                "Got: %s <= %s" % (self.pwm_line_end, BasePWMFan.max_pwm)
            )

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return (
                self._pwm == other._pwm
                and self._pwm_enable == other._pwm_enable
                and self._fan_input == other._fan_input
                and self.pwm_line_start == other.pwm_line_start
                and self.pwm_line_end == other.pwm_line_end
                and self.never_stop == other.never_stop
            )

        return NotImplemented

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return "%s(%r, %r, pwm_line_start=%r, pwm_line_end=%r, never_stop=%r)" % (
            type(self).__name__,
            str(self._pwm),
            str(self._fan_input),
            self.pwm_line_start,
            self.pwm_line_end,
            self.never_stop,
        )

    def get_raw(self) -> PWMValue:
        return self._get_raw()

    def get(self) -> PWMValueNorm:
        return PWMValueNorm(self._get_raw() / BasePWMFan.max_pwm)

    def set(self, pwm_norm: PWMValueNorm) -> PWMValue:
        # TODO validate this formula
        pwm_norm = max(pwm_norm, PWMValueNorm(0.0))
        pwm_norm = min(pwm_norm, PWMValueNorm(1.0))
        pwm = pwm_norm * self.pwm_line_end
        if 0 < pwm < self.pwm_line_start:
            pwm = self.pwm_line_start
        if pwm <= 0 and self.never_stop:
            pwm = self.pwm_line_start

        pwm = PWMValue(int(math.ceil(pwm)))
        self._set_raw(pwm)
        return pwm
