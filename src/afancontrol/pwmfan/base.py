import abc
from typing import NewType, Type

PWMValue = NewType("PWMValue", int)  # [0..255]
FanValue = NewType("FanValue", int)


class _SlotsReprMixin:
    def __eq__(self, other):
        if isinstance(other, type(self)):
            for attr in self.__slots__:
                if getattr(self, attr) != getattr(other, attr):
                    return False
            return True

        return NotImplemented

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        # repr assumes that the `__slots__` attrs match the `__init__` signature.

        return "%s(%s)" % (
            type(self).__name__,
            ", ".join(repr(getattr(self, attr)) for attr in self.__slots__),
        )


class BaseFanSpeed(abc.ABC, _SlotsReprMixin):
    @abc.abstractmethod
    def get_speed(self) -> FanValue:
        pass

    def __enter__(self):  # reusable
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        pass


class BaseFanPWMRead(abc.ABC, _SlotsReprMixin):
    max_pwm: PWMValue
    min_pwm: PWMValue

    def is_stopped(self) -> bool:
        return type(self).is_pwm_stopped(self.get())

    @staticmethod
    def is_pwm_stopped(pwm: PWMValue) -> bool:
        return pwm <= 0

    @abc.abstractmethod
    def get(self) -> PWMValue:
        pass

    def __enter__(self):  # reusable
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        pass


class BaseFanPWMWrite(abc.ABC, _SlotsReprMixin):
    read_cls: Type[BaseFanPWMRead]

    def set(self, pwm: PWMValue) -> None:
        if not (self.read_cls.min_pwm <= pwm <= self.read_cls.max_pwm):
            raise ValueError(
                "Invalid pwm value %s: it must be within [%s..%s]"
                % (pwm, self.read_cls.min_pwm, self.read_cls.max_pwm)
            )
        self._set_raw(pwm)

    def set_full_speed(self) -> None:
        self._set_raw(self.read_cls.max_pwm)

    @abc.abstractmethod
    def _set_raw(self, pwm: PWMValue) -> None:
        pass

    def __enter__(self):  # reusable
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        pass
