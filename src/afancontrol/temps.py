import concurrent.futures
from contextlib import ExitStack
from typing import Mapping, NamedTuple, Optional

from afancontrol.config import FilteredTemp, TempName
from afancontrol.filters import TempFilter
from afancontrol.logger import logger
from afancontrol.temp import Temp, TempStatus


class ObservedTempStatus(NamedTuple):
    raw: Optional[TempStatus]
    filtered: Optional[TempStatus]


def filtered_temps(
    temps: Mapping[TempName, ObservedTempStatus]
) -> Mapping[TempName, Optional[TempStatus]]:
    return {
        temp_name: observed_temp_status.filtered
        for temp_name, observed_temp_status in temps.items()
    }


class Temps:
    def __init__(self, temps: Mapping[TempName, FilteredTemp]) -> None:
        self.temps = temps
        self._stack: Optional[ExitStack] = None
        self._executor: Optional[concurrent.futures.Executor] = None

    def __enter__(self):  # reusable
        self._stack = ExitStack()
        try:
            for filtered_temp in self.temps.values():
                self._stack.enter_context(filtered_temp.filter)
            self._executor = self._stack.enter_context(
                concurrent.futures.ThreadPoolExecutor()
            )
        except Exception:
            self._stack.close()
            raise
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        assert self._stack is not None
        self._stack.close()
        self._executor = None

    def get_temps(self) -> Mapping[TempName, ObservedTempStatus]:
        assert self._executor is not None
        futures = {
            temp_name: self._executor.submit(
                _get_temp_status,
                temp_name,
                temp=filtered_temp.temp,
                filter=filtered_temp.filter,
            )
            for temp_name, filtered_temp in self.temps.items()
        }
        return {temp_name: future.result() for temp_name, future in futures.items()}


def _get_temp_status(
    name: TempName, temp: Temp, filter: TempFilter
) -> ObservedTempStatus:
    try:
        sensor_value: Optional[TempStatus] = temp.get()
    except Exception as e:
        sensor_value = None
        logger.warning("Temp sensor [%s] has failed: %s", name, e, exc_info=True)

    filtered_value = filter.apply(sensor_value)
    logger.debug(
        "Temp status [%s]: actual=%s, filtered=%s", name, sensor_value, filtered_value
    )

    return ObservedTempStatus(raw=sensor_value, filtered=filtered_value)
