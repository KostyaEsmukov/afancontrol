from contextlib import ExitStack
from typing import Mapping, MutableSet

from afancontrol.config import FanName
from afancontrol.logger import logger
from afancontrol.pwmfan import PWMFanNorm, PWMValueNorm
from afancontrol.report import Report


class Fans:
    def __init__(self, fans: Mapping[FanName, PWMFanNorm], *, report: Report) -> None:
        self.fans = fans
        self.report = report
        self._stack = None

        # Set of fans marked as failing (which speed is 0)
        self._failed_fans = set()  # type: MutableSet[FanName]

        # Set of fans that will be skipped on speed check
        self._stopped_fans = set()  # type: MutableSet[FanName]

    def is_fan_failing(self, fan_name: FanName) -> bool:
        return fan_name in self._failed_fans

    def is_fan_stopped(self, fan_name: FanName) -> bool:
        return fan_name in self._stopped_fans

    def __enter__(self):  # reusable
        self._stack = ExitStack()
        logger.info("Enabling PWM on fans...")
        try:
            for pwmfan in self.fans.values():
                self._stack.enter_context(pwmfan)
        except Exception:
            self._stack.close()
            raise
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        logger.info("Disabling PWM on fans...")
        self._stack.close()
        logger.info("Done. Fans should be returned to full speed")
        return None

    def check_speeds(self) -> None:
        for name, fan in self.fans.items():
            if name in self._stopped_fans:
                continue
            try:
                if fan.get_speed() <= 0:
                    raise RuntimeError("Fan speed is 0")
            except Exception as e:
                self._ensure_fan_is_failing(name, e)
            else:
                self._ensure_fan_is_not_failing(name)

    def set_all_to_full_speed(self) -> None:
        for name, fan in self.fans.items():
            if name in self._failed_fans:
                continue
            try:
                fan.set_full_speed()
            except Exception as e:
                logger.warning("Unable to set the fan '%s' to full speed:\n%s", name, e)

    def set_fan_speeds(self, speeds: Mapping[FanName, PWMValueNorm]) -> None:
        assert speeds.keys() == self.fans.keys()
        self._stopped_fans.clear()
        for name, pwm_norm in speeds.items():
            fan = self.fans[name]
            assert 0.0 <= pwm_norm <= 1.0

            if name in self._failed_fans:
                continue

            try:
                pwm = fan.set(pwm_norm)
            except Exception as e:
                logger.warning(
                    "Unable to set the fan '%s' to speed %s:\n%s", name, pwm_norm, e
                )
            else:
                logger.debug(
                    "Fan status [%s]: speed: %.3f, pwm: %s", name, pwm_norm, pwm
                )
                if fan.is_pwm_stopped(pwm):
                    self._stopped_fans.add(name)

    def _ensure_fan_is_failing(self, name: FanName, get_speed_exc: Exception) -> None:
        if name in self._failed_fans:
            return
        self._failed_fans.add(name)
        fan = self.fans[name]
        try:
            # Perhaps it had jammed, so setting it to full speed might
            # recover it?
            fan.set_full_speed()
        except Exception as e:
            full_speed_result = "Setting fan speed to full has failed:\n%s" % e
        else:
            full_speed_result = "Fan has been set to full speed"

        self.report.report(
            "fan stopped: %s" % name,
            "Looks like the fan '%s' is failing:\n%s\n\n%s"
            % (name, get_speed_exc, full_speed_result),
        )

    def _ensure_fan_is_not_failing(self, name: FanName) -> None:
        if name not in self._failed_fans:
            return
        self.report.report(
            "fan started: %s" % name,
            "Fan '%s' which had previously been reported as failing has just started."
            % name,
        )
        self._failed_fans.remove(name)
