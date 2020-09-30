import glob
import re
from pathlib import Path
from typing import Optional, Tuple

from afancontrol.configparser import ConfigParserSection
from afancontrol.temp.base import Temp, TempCelsius


def _expand_glob(path: str):
    matches = glob.glob(path)
    if not matches:
        return path  # a FileNotFoundError will be raised on a first read attempt
    if len(matches) == 1:
        return matches[0]
    raise ValueError("Expected glob to expand to a single path, got %r" % (matches,))


class FileTemp(Temp):
    def __init__(
        self,
        temp_path: str,  # /sys/class/hwmon/hwmon0/temp1
        *,
        min: Optional[TempCelsius],
        max: Optional[TempCelsius],
        panic: Optional[TempCelsius],
        threshold: Optional[TempCelsius]
    ) -> None:
        super().__init__(panic=panic, threshold=threshold)
        temp_path = re.sub(r"_input$", "", temp_path)

        # Allow paths looking like this (this one is from an nvme drive):
        #  /sys/devices/pci0000:00/0000:00:01.3/[...]/hwmon/hwmon*/temp1_input
        # The `hwmon*` might change after reboot, but it is always a single
        # directory within the device.
        temp_path = _expand_glob(temp_path + "_input")
        temp_path = re.sub(r"_input$", "", temp_path)

        self._temp_input = Path(temp_path + "_input")
        self._temp_min = Path(temp_path + "_min")
        self._temp_max = Path(temp_path + "_max")
        self._min = min
        self._max = max

    @classmethod
    def from_configparser(cls, section: ConfigParserSection) -> Temp:
        panic = TempCelsius(section.getfloat("panic", fallback=None))
        threshold = TempCelsius(section.getfloat("threshold", fallback=None))
        min = TempCelsius(section.getfloat("min", fallback=None))
        max = TempCelsius(section.getfloat("max", fallback=None))
        return cls(section["path"], min=min, max=max, panic=panic, threshold=threshold)

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return (
                self._temp_input == other._temp_input
                and self._temp_min == other._temp_min
                and self._temp_max == other._temp_max
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
            str(self._temp_input),
            self._min,
            self._max,
            self._panic,
            self._threshold,
        )

    def _get_temp(self) -> Tuple[TempCelsius, TempCelsius, TempCelsius]:
        temp = self._read_temp_from_path(self._temp_input)
        return temp, self._get_min(), self._get_max()

    def _get_min(self) -> TempCelsius:
        if self._min is not None:
            return self._min
        try:
            min_t = self._read_temp_from_path(self._temp_min)
        except FileNotFoundError:
            raise RuntimeError(
                "Please specify `min` and `max` temperatures for "
                "the %s sensor" % self._temp_input
            )
        return min_t

    def _get_max(self) -> TempCelsius:
        if self._max is not None:
            return self._max
        try:
            max_t = self._read_temp_from_path(self._temp_max)
        except FileNotFoundError:
            raise RuntimeError(
                "Please specify `min` and `max` temperatures for "
                "the %s sensor" % self._temp_input
            )
        return max_t

    def _read_temp_from_path(self, path: Path) -> TempCelsius:
        return TempCelsius(int(path.read_text().strip()) / 1000)
