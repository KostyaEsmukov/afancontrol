from collections import defaultdict
from contextlib import ExitStack
from typing import Dict, Mapping, Optional

from afancontrol.arduino import ArduinoConnection, ArduinoName
from afancontrol.config import (
    FanName,
    FansTempsRelation,
    MappingName,
    ReadonlyFanName,
    TempName,
    TriggerConfig,
)
from afancontrol.fans import Fans
from afancontrol.logger import logger
from afancontrol.metrics import Metrics
from afancontrol.pwmfannorm import PWMFanNorm, PWMValueNorm, ReadonlyPWMFanNorm
from afancontrol.report import Report
from afancontrol.temp import TempStatus
from afancontrol.temps import FilteredTemp, Temps, filtered_temps
from afancontrol.trigger import Triggers


class Manager:
    def __init__(
        self,
        *,
        arduino_connections: Mapping[ArduinoName, ArduinoConnection],
        fans: Mapping[FanName, PWMFanNorm],
        readonly_fans: Mapping[ReadonlyFanName, ReadonlyPWMFanNorm],
        temps: Mapping[TempName, FilteredTemp],
        mappings: Mapping[MappingName, FansTempsRelation],
        report: Report,
        triggers_config: TriggerConfig,
        metrics: Metrics
    ) -> None:
        self.report = report
        self.arduino_connections = arduino_connections
        self.fans = Fans(fans=fans, readonly_fans=readonly_fans, report=report)
        self.temps = Temps(temps)
        self.mappings = mappings
        self.triggers = Triggers(triggers_config, report)
        self.metrics = metrics
        self._stack: Optional[ExitStack] = None

    def __enter__(self):  # reusable
        self._stack = ExitStack()
        try:
            self._stack.enter_context(self.fans)
            self._stack.enter_context(self.temps)
            self._stack.enter_context(self.triggers)
            self._stack.enter_context(self.metrics)
        except Exception:
            self._stack.close()
            raise
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        assert self._stack is not None
        self._stack.close()
        return None

    def tick(self) -> None:
        with self.metrics.measure_tick():
            temps = self.temps.get_temps()
            _filtered_temps = filtered_temps(temps)
            self.fans.check_speeds()

            self.triggers.check(_filtered_temps)

            if self.triggers.is_alerting:
                self.fans.set_all_to_full_speed()
            else:
                speeds = self._map_temps_to_fan_speeds(_filtered_temps)
                self.fans.set_fan_speeds(speeds)

        try:
            self.metrics.tick(temps, self.fans, self.triggers, self.arduino_connections)
        except Exception:
            logger.warning("Failed to collect metrics", exc_info=True)

    def _map_temps_to_fan_speeds(
        self, temps: Mapping[TempName, Optional[TempStatus]]
    ) -> Mapping[FanName, PWMValueNorm]:

        temp_speeds = {
            temp_name: self._temp_speed(temp_status)
            for temp_name, temp_status in temps.items()
        }

        fan_speeds: Dict[FanName, PWMValueNorm] = defaultdict(lambda: PWMValueNorm(0.0))

        for mapping_name, relation in self.mappings.items():
            mapping_speed = max(temp_speeds[temp_name] for temp_name in relation.temps)
            for fan_modifier in relation.fans:
                pwm_norm = PWMValueNorm(mapping_speed * fan_modifier.modifier)
                pwm_norm = max(pwm_norm, PWMValueNorm(0.0))
                pwm_norm = min(pwm_norm, PWMValueNorm(1.0))
                fan_speeds[fan_modifier.fan] = max(
                    pwm_norm, fan_speeds[fan_modifier.fan]
                )

        # Ensure that all fans have been referenced through the mappings.
        # This is also enforced in the `config.py` module.
        assert len(fan_speeds) == len(self.fans.fans)

        return fan_speeds

    def _temp_speed(self, temp: Optional[TempStatus]) -> PWMValueNorm:
        if temp is None:
            # Failing sensor -- this is the panic mode.
            return PWMValueNorm(1.0)
        speed = PWMValueNorm((temp.temp - temp.min) / (temp.max - temp.min))
        speed = max(speed, PWMValueNorm(0.0))
        speed = min(speed, PWMValueNorm(1.0))
        return speed
