import math
from pathlib import Path
from typing import NewType

PWMDevice = NewType("PWMDevice", str)
FanInputDevice = NewType("FanInputDevice", str)
PWMValue = NewType("PWMValue", int)  # [0..255]
PWMValueNorm = NewType("PWMValueNorm", float)  # [0..1]
FanValue = NewType("FanValue", int)


class PWMFan:
    max_pwm = 255  # type: PWMValue
    min_pwm = 0  # type: PWMValue

    def __init__(self, pwm: PWMDevice, fan_input: FanInputDevice):
        self._pwm = Path(pwm)
        self._pwm_enable = Path(pwm + "_enable")
        self._fan_input = Path(fan_input)

    def is_stopped(self) -> bool:
        return type(self).is_pwm_stopped(self._get_raw())

    @staticmethod
    def is_pwm_stopped(pwm: PWMValue) -> bool:
        return pwm <= 0

    def get(self) -> PWMValue:
        return self._get_raw()

    def _get_raw(self) -> PWMValue:
        return PWMValue(int(self._pwm.read_text()))

    def set(self, pwm: PWMValue) -> None:
        self._set_raw(pwm)

    def _set_raw(self, pwm: PWMValue) -> None:
        if not (PWMFan.min_pwm <= pwm <= PWMFan.max_pwm):
            raise ValueError(
                "Invalid pwm value %s: it must be within [%s..%s]"
                % (pwm, PWMFan.min_pwm, PWMFan.max_pwm)
            )
        self._pwm.write_text(str(int(pwm)))

    def set_full_speed(self) -> None:
        self._set_raw(PWMFan.max_pwm)

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

        if self._pwm_enable.read_text() == "1" and self._get_raw() >= PWMFan.max_pwm:
            return

        raise RuntimeError("Couldn't disable PWM on that fan")

    def get_speed(self) -> FanValue:
        """Get current RPM for this fan"""
        return FanValue(int(self._fan_input.read_text()))


class PWMFanNorm(PWMFan):
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
        if PWMFan.min_pwm > self.pwm_line_start:
            raise ValueError(
                "Invalid pwm_line_start. Expected: min_pwm <= pwm_line_start. "
                "Got: %s <= %s" % (PWMFan.min_pwm, self.pwm_line_start)
            )
        if self.pwm_line_end > PWMFan.max_pwm:
            raise ValueError(
                "Invalid pwm_line_end. Expected: pwm_line_end <= max_pwm. "
                "Got: %s <= %s" % (self.pwm_line_end, PWMFan.max_pwm)
            )

    def get(self) -> PWMValueNorm:
        return self._get_raw() / PWMFan.max_pwm

    def set(self, pwm_norm: PWMValueNorm) -> None:
        self.set_norm(pwm_norm)

    def set_norm(self, pwm_norm: PWMValueNorm) -> PWMValue:
        # TODO validate this formula
        pwm_norm = max(pwm_norm, 0.0)
        pwm_norm = min(pwm_norm, 1.0)
        pwm = pwm_norm * self.pwm_line_end
        if 0 < pwm < self.pwm_line_start:
            pwm = self.pwm_line_start
        if pwm <= 0 and self.never_stop:
            pwm = self.pwm_line_start

        pwm = int(math.ceil(pwm))
        self._set_raw(pwm)
        return pwm
