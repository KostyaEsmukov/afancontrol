import math
from typing import NewType

from afancontrol.pwmfan import BasePWMFan, FanValue, PWMValue

PWMValueNorm = NewType("PWMValueNorm", float)  # [0..1]


class PWMFanNorm:
    def __init__(
        self,
        pwmfan: BasePWMFan,
        *,
        pwm_line_start: PWMValue,
        pwm_line_end: PWMValue,
        never_stop: bool = False
    ) -> None:
        self.pwmfan = pwmfan
        self.pwm_line_start = pwm_line_start
        self.pwm_line_end = pwm_line_end
        self.never_stop = never_stop
        if type(self.pwmfan).min_pwm > self.pwm_line_start:
            raise ValueError(
                "Invalid pwm_line_start. Expected: min_pwm <= pwm_line_start. "
                "Got: %s <= %s" % (type(self.pwmfan).min_pwm, self.pwm_line_start)
            )
        if self.pwm_line_end > type(self.pwmfan).max_pwm:
            raise ValueError(
                "Invalid pwm_line_end. Expected: pwm_line_end <= max_pwm. "
                "Got: %s <= %s" % (self.pwm_line_end, type(self.pwmfan).max_pwm)
            )

    def __enter__(self):
        self.pwmfan.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        return self.pwmfan.__exit__(exc_type, exc_value, exc_tb)

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return (
                self.pwmfan == other.pwmfan
                and self.pwm_line_start == other.pwm_line_start
                and self.pwm_line_end == other.pwm_line_end
                and self.never_stop == other.never_stop
            )

        return NotImplemented

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return "%s(%r, pwm_line_start=%r, pwm_line_end=%r, never_stop=%r)" % (
            type(self).__name__,
            self.pwmfan,
            self.pwm_line_start,
            self.pwm_line_end,
            self.never_stop,
        )

    def is_pwm_stopped(self, pwm: PWMValue) -> bool:
        return type(self.pwmfan).is_pwm_stopped(pwm)

    def set_full_speed(self) -> None:
        self.pwmfan.set_full_speed()

    def get_speed(self) -> FanValue:
        return self.pwmfan.get_speed()

    def get_raw(self) -> PWMValue:
        return self.pwmfan.get()

    def get(self) -> PWMValueNorm:
        return PWMValueNorm(self.get_raw() / self.pwmfan.max_pwm)

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
            pwm = self.pwmfan.max_pwm

        pwm = PWMValue(int(math.ceil(pwm)))
        self.pwmfan.set(pwm)
        return pwm
