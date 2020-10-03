from typing import Optional, Tuple

from afancontrol.configparser import ConfigParserSection
from afancontrol.exec import Programs, exec_shell_command
from afancontrol.temp.base import Temp, TempCelsius


def _is_float(s: str) -> bool:
    if not s:
        return False
    try:
        float(s)
    except (ValueError, TypeError):
        return False
    else:
        return True


class HDDTemp(Temp):
    def __init__(
        self,
        disk_path: str,
        *,
        min: TempCelsius,
        max: TempCelsius,
        panic: Optional[TempCelsius],
        threshold: Optional[TempCelsius],
        hddtemp_bin: str = "hddtemp"
    ) -> None:
        super().__init__(panic=panic, threshold=threshold)
        self._disk_path = disk_path
        self._min = min
        self._max = max
        self._hddtemp_bin = hddtemp_bin

    @classmethod
    def from_configparser(
        cls, section: ConfigParserSection, programs: Programs
    ) -> Temp:
        panic = TempCelsius(section.getfloat("panic", fallback=None))
        threshold = TempCelsius(section.getfloat("threshold", fallback=None))
        min = TempCelsius(section.getfloat("min"))
        max = TempCelsius(section.getfloat("max"))
        return cls(
            section["path"],
            min=min,
            max=max,
            panic=panic,
            threshold=threshold,
            hddtemp_bin=programs.hddtemp,
        )

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return (
                self._disk_path == other._disk_path
                and self._min == other._min
                and self._max == other._max
                and self._panic == other._panic
                and self._threshold == other._threshold
                and self._hddtemp_bin == other._hddtemp_bin
            )

        return NotImplemented

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return "%s(%r, min=%r, max=%r, panic=%r, threshold=%r, hddtemp_bin=%r)" % (
            type(self).__name__,
            self._disk_path,
            self._min,
            self._max,
            self._panic,
            self._threshold,
            self._hddtemp_bin,
        )

    def _get_temp(self) -> Tuple[TempCelsius, TempCelsius, TempCelsius]:
        temps = [
            float(line.strip())
            for line in self._call_hddtemp().split("\n")
            if _is_float(line.strip())
        ]
        if not temps:
            raise RuntimeError(
                "hddtemp returned empty list of valid temperature values"
            )
        temp = TempCelsius(max(temps))
        return temp, self._get_min(), self._get_max()

    def _get_min(self) -> TempCelsius:
        return TempCelsius(self._min)

    def _get_max(self) -> TempCelsius:
        return TempCelsius(self._max)

    def _call_hddtemp(self) -> str:
        # `disk_path` might be a glob, so it has to be executed with a shell.
        shell_command = "%s -n -u C -- %s" % (self._hddtemp_bin, self._disk_path)
        return exec_shell_command(shell_command, timeout=10)
