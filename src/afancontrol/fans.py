import itertools
from contextlib import ExitStack
from typing import Iterator, Mapping, MutableSet, Optional, Tuple, Union, cast

from afancontrol.logger import logger
from afancontrol.pwmfan import AnyFanName, FanName, ReadonlyFanName
from afancontrol.pwmfannorm import PWMFanNorm, PWMValueNorm, ReadonlyPWMFanNorm
from afancontrol.report import Report


class Fans:
    def __init__(
        self,
        *,
        fans: Mapping[FanName, PWMFanNorm],
        readonly_fans: Mapping[ReadonlyFanName, ReadonlyPWMFanNorm],
        report: Report
    ) -> None:
        self.fans = fans
        self.readonly_fans = readonly_fans
        self.report = report
        self._stack: Optional[ExitStack] = None

        # Set of fans marked as failing (which speed is 0)
        self._failed_fans: MutableSet[AnyFanName] = set()

        # Set of fans that will be skipped on speed check
        self._stopped_fans: MutableSet[AnyFanName] = set()

    def is_fan_failing(self, fan_name: AnyFanName) -> bool:
        return fan_name in self._failed_fans

    def is_fan_stopped(self, fan_name: AnyFanName) -> bool:
        return fan_name in self._stopped_fans

    def __enter__(self):  # reusable
        self._stack = ExitStack()
        logger.info("Enabling PWM on fans...")
        try:
            for pwmfan in cast(
                Iterator[Union[PWMFanNorm, ReadonlyPWMFanNorm]],
                itertools.chain(self.fans.values(), self.readonly_fans.values()),
            ):
                self._stack.enter_context(pwmfan)
        except Exception:
            self._stack.close()
            raise
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        assert self._stack is not None
        logger.info("Disabling PWM on fans...")
        self._stack.close()
        logger.info("Done. Fans should be returned to full speed")
        return None

    def check_speeds(self) -> None:
        for name, fan in cast(
            Iterator[Tuple[AnyFanName, Union[PWMFanNorm, ReadonlyPWMFanNorm]]],
            itertools.chain(self.fans.items(), self.readonly_fans.items()),
        ):
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
        for readonly_name, readonly_fan in self.readonly_fans.items():
            readonly_pwm_norm = readonly_fan.get()
            readonly_pwm = readonly_fan.get_raw()
            logger.debug(
                "Readonly Fan status [%s]: speed: %.3f, pwm: %s",
                readonly_name,
                readonly_pwm_norm,
                readonly_pwm,
            )
            if readonly_fan.is_pwm_stopped(readonly_pwm):
                self._stopped_fans.add(readonly_name)

    def _ensure_fan_is_failing(
        self, name: AnyFanName, get_speed_exc: Exception
    ) -> None:
        if name in self._failed_fans:
            return
        self._failed_fans.add(name)
        try:
            fan = self.fans[cast(FanName, name)]
        except KeyError:
            self.readonly_fans[cast(ReadonlyFanName, name)]  # assert
            full_speed_result = "The fan is in the readonly mode"
        else:
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

    def _ensure_fan_is_not_failing(self, name: AnyFanName) -> None:
        if name not in self._failed_fans:
            return
        self.report.report(
            "fan started: %s" % name,
            "Fan '%s' which had previously been reported as failing has just started."
            % name,
        )
        self._failed_fans.remove(name)
