from typing import Optional, Tuple

from afancontrol.configparser import ConfigParserSection
from afancontrol.exec import exec_shell_command
from afancontrol.temp.base import Temp, TempCelsius


class CommandTemp(Temp):
    def __init__(
        self,
        shell_command: str,
        *,
        min: Optional[TempCelsius],
        max: Optional[TempCelsius],
        panic: Optional[TempCelsius],
        threshold: Optional[TempCelsius]
    ) -> None:
        super().__init__(panic=panic, threshold=threshold)
        self._shell_command = shell_command
        self._min = min
        self._max = max

    @classmethod
    def from_configparser(cls, section: ConfigParserSection) -> Temp:
        panic = TempCelsius(section.getfloat("panic", fallback=None))
        threshold = TempCelsius(section.getfloat("threshold", fallback=None))
        min = TempCelsius(section.getfloat("min", fallback=None))
        max = TempCelsius(section.getfloat("max", fallback=None))
        return cls(
            section["command"], min=min, max=max, panic=panic, threshold=threshold
        )

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return (
                self._shell_command == other._shell_command
                and self._min == other._min
                and self._max == other._max
                and self._panic == other._panic
                and self._threshold == other._threshold
            )

        return NotImplemented

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return "%s(%r, min=%r, max=%r, panic=%r, threshold=%r)" % (
            type(self).__name__,
            self._shell_command,
            self._min,
            self._max,
            self._panic,
            self._threshold,
        )

    def _get_temp(self) -> Tuple[TempCelsius, TempCelsius, TempCelsius]:
        temps = [
            float(line.strip())
            for line in exec_shell_command(self._shell_command).split("\n")
            if line.strip()
        ]
        temp = TempCelsius(temps[0])

        if self._min is not None:
            min_t = self._min
        else:
            min_t = TempCelsius(temps[1])

        if self._max is not None:
            max_t = self._max
        else:
            max_t = TempCelsius(temps[2])

        return temp, min_t, max_t
