import abc
from contextlib import ExitStack
from typing import Mapping, Optional, Set

from afancontrol.config import AlertCommands, TempName, TriggerConfig
from afancontrol.exec import exec_shell_command
from afancontrol.logger import logger
from afancontrol.report import Report
from afancontrol.temp import TempStatus


class Trigger(abc.ABC):
    def __init__(
        self,
        *,
        global_commands: AlertCommands,
        temp_commands: Mapping[TempName, AlertCommands],
        report: Report
    ) -> None:
        self.global_commands = global_commands
        self.temp_commands = temp_commands
        self.report = report
        self._alerting_temps: Set[TempName] = set()

    @property
    @abc.abstractmethod
    def trigger_name(self):
        pass

    def __enter__(self):  # reusable
        assert not self._alerting_temps
        self._alerting_temps.clear()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        if self.is_alerting:
            # Although the exceptional situation is not yet resolved,
            # we call the corresponding leave callbacks, because
            # if this is a reload, then we might get the enter callbacks
            # being executed twice.
            # Perhaps we should somehow tell the `leave_cmd` that it's
            # being called not because the issue is resolved,
            # but because this program is restarting or is shutting down.
            self.report.report(
                "Leaving %s MODE" % self.trigger_name.upper(),
                "Leaving %s MODE because of shutting down or restarting."
                % self.trigger_name.upper(),
            )
            for name in self._alerting_temps:
                self._alert_cmd(self.temp_commands[name].leave_cmd)
            self._alert_cmd(self.global_commands.leave_cmd)

        self._alerting_temps.clear()
        return None

    @property
    def is_alerting(self) -> bool:
        return bool(self._alerting_temps)

    def check(self, temps: Mapping[TempName, Optional[TempStatus]]) -> None:
        was_alerting = self.is_alerting
        self._update_alerting_temps(temps)
        self._process_global_alerting_commands(temps, was_alerting, self.is_alerting)

    def _update_alerting_temps(
        self, temps: Mapping[TempName, Optional[TempStatus]]
    ) -> None:
        stopped_alerting_temps = self._alerting_temps.copy()
        for name, status in temps.items():
            temp_alerting_reason = self._temp_alerting_reason(status)
            if not temp_alerting_reason:
                continue
            if name in self._alerting_temps:
                # Still alerting
                stopped_alerting_temps.discard(name)
                continue

            # Just started alerting
            self._alerting_temps.add(name)
            logger.warning(
                "%s started on temp. name: %s, status: %s, reason: %s",
                self.trigger_name.upper(),
                name,
                status,
                temp_alerting_reason,
            )
            self._alert_cmd(self.temp_commands[name].enter_cmd)

        for name in stopped_alerting_temps:
            self._alerting_temps.discard(name)
            status = temps[name]

            logger.warning(
                "%s ended on temp: name: %s, status: %s",
                self.trigger_name.upper(),
                name,
                status,
            )
            self._alert_cmd(self.temp_commands[name].leave_cmd)

    def _process_global_alerting_commands(
        self,
        temps: Mapping[TempName, Optional[TempStatus]],
        was_alerting: bool,
        is_alerting: bool,
    ) -> None:
        is_entered = not was_alerting and is_alerting
        is_left = was_alerting and not is_alerting
        if is_entered or is_left:
            temps_debug = "\n".join(
                "[%s]: %s" % (name, status)
                for name, status in sorted(temps.items(), key=lambda kv: kv[0])
            )
            if is_entered:
                self.report.report(
                    "Entered %s MODE" % self.trigger_name.upper(),
                    "Entered %s MODE. Take a look as soon as possible!!!\nSensors:\n%s"
                    % (self.trigger_name.upper(), temps_debug),
                )
                self._alert_cmd(self.global_commands.enter_cmd)
            if is_left:
                self.report.report(
                    "Leaving %s MODE" % self.trigger_name.upper(),
                    "Leaving %s MODE.\nSensors:\n%s"
                    % (self.trigger_name.upper(), temps_debug),
                )
                self._alert_cmd(self.global_commands.leave_cmd)

    @abc.abstractmethod
    def _temp_alerting_reason(self, temp: Optional[TempStatus]) -> Optional[str]:
        pass

    def _alert_cmd(self, shell_cmd):
        if not shell_cmd:
            return
        try:
            exec_shell_command(shell_cmd)
        except Exception as e:
            logger.warning(
                "Enable to execute %s trigger command %s:\n%s",
                self.trigger_name,
                shell_cmd,
                e,
            )


class PanicTrigger(Trigger):
    trigger_name = "panic"

    def _temp_alerting_reason(self, temp: Optional[TempStatus]) -> Optional[str]:
        if temp is None:
            return "Sensor failed"
        if not temp.is_panic:
            return None
        return "Panic temp reached"


class ThresholdTrigger(Trigger):
    trigger_name = "threshold"

    def _temp_alerting_reason(self, temp: Optional[TempStatus]) -> Optional[str]:
        if temp is None:
            return None
        if not temp.is_threshold:
            return None
        return "Threshold temp reached"


class Triggers:
    def __init__(self, triggers_config: TriggerConfig, report: Report) -> None:
        self.panic_trigger = PanicTrigger(
            global_commands=triggers_config.global_commands.panic,
            temp_commands={
                temp_name: actions.panic
                for temp_name, actions in triggers_config.temp_commands.items()
            },
            report=report,
        )
        self.threshold_trigger = ThresholdTrigger(
            global_commands=triggers_config.global_commands.threshold,
            temp_commands={
                temp_name: actions.threshold
                for temp_name, actions in triggers_config.temp_commands.items()
            },
            report=report,
        )
        self._stack: Optional[ExitStack] = None

    def __enter__(self):  # reusable
        self._stack = ExitStack()
        try:
            self._stack.enter_context(self.panic_trigger)
            self._stack.enter_context(self.threshold_trigger)
        except Exception:
            self._stack.close()
            raise
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        assert self._stack is not None
        self._stack.close()
        return None

    @property
    def is_alerting(self) -> bool:
        return self.panic_trigger.is_alerting or self.threshold_trigger.is_alerting

    def check(self, temps: Mapping[TempName, Optional[TempStatus]]) -> None:
        self.panic_trigger.check(temps)
        self.threshold_trigger.check(temps)
