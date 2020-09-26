from pathlib import Path

from afancontrol.pwmfan.base import (
    BasePWMFan,
    FanInputDevice,
    FanValue,
    PWMDevice,
    PWMValue,
)


class LinuxPWMFan(BasePWMFan):
    def __init__(self, pwm: PWMDevice, fan_input: FanInputDevice) -> None:
        super().__init__()
        self._pwm = Path(pwm)
        self._pwm_enable = Path(pwm + "_enable")
        self._fan_input = Path(fan_input)

    def get(self) -> PWMValue:
        return PWMValue(int(self._pwm.read_text()))

    def _set_raw(self, pwm: PWMValue) -> None:
        self._pwm.write_text(str(int(pwm)))

    def get_speed(self) -> FanValue:
        return FanValue(int(self._fan_input.read_text()))

    def _enable_pwm(self) -> None:
        # fancontrol way of doing it
        if self._pwm_enable.is_file():
            self._pwm_enable.write_text("1")
        self.set_full_speed()

    def _disable_pwm(self) -> None:
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
            and self.get() >= type(self).max_pwm
        ):
            return

        raise RuntimeError("Couldn't disable PWM on the fan %r" % self)

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
