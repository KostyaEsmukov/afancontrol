import abc
from typing import NewType

PWMDevice = NewType("PWMDevice", str)
FanInputDevice = NewType("FanInputDevice", str)
PWMValue = NewType("PWMValue", int)  # [0..255]
FanValue = NewType("FanValue", int)


class BasePWMFan(abc.ABC):
    max_pwm = PWMValue(255)
    min_pwm = PWMValue(0)

    def is_stopped(self) -> bool:
        return type(self).is_pwm_stopped(self.get())

    @staticmethod
    def is_pwm_stopped(pwm: PWMValue) -> bool:
        return pwm <= 0

    @abc.abstractmethod
    def get(self) -> PWMValue:
        pass

    def set(self, pwm: PWMValue) -> None:
        if not (type(self).min_pwm <= pwm <= type(self).max_pwm):
            raise ValueError(
                "Invalid pwm value %s: it must be within [%s..%s]"
                % (pwm, type(self).min_pwm, type(self).max_pwm)
            )
        self._set_raw(pwm)

    @abc.abstractmethod
    def _set_raw(self, pwm: PWMValue) -> None:
        pass

    def set_full_speed(self) -> None:
        self._set_raw(type(self).max_pwm)

    @abc.abstractmethod
    def get_speed(self) -> FanValue:
        pass

    def __enter__(self):  # reusable
        """Enable PWM control for this fan"""
        self._enable_pwm()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        """Disable PWM control for this fan"""
        self._disable_pwm()

    @abc.abstractmethod
    def _enable_pwm(self) -> None:
        pass

    @abc.abstractmethod
    def _disable_pwm(self) -> None:
        pass
