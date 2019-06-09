import abc
import re
from pathlib import Path
from typing import NamedTuple, NewType, Optional, Tuple

from afancontrol.exec import exec_shell_command

TempCelsius = NewType("TempCelsius", float)

TempStatus = NamedTuple(
    "TempStatus",
    [
        ("temp", TempCelsius),
        ("min", TempCelsius),
        ("max", TempCelsius),
        ("panic", Optional[TempCelsius]),
        ("threshold", Optional[TempCelsius]),
        ("is_panic", bool),
        ("is_threshold", bool),
    ],
)


class Temp(abc.ABC):
    def __init__(
        self, *, panic: Optional[TempCelsius], threshold: Optional[TempCelsius]
    ) -> None:
        self._panic = panic
        self._threshold = threshold

    def get(self) -> TempStatus:
        temp, min_t, max_t = self._get_temp()

        if not (min_t < max_t):
            raise RuntimeError(
                "Min temperature must be less than max. %s < %s" % (min_t, max_t)
            )

        return TempStatus(
            temp=temp,
            min=min_t,
            max=max_t,
            panic=self._panic,
            threshold=self._threshold,
            is_panic=self._panic is not None and temp >= self._panic,
            is_threshold=self._threshold is not None and temp >= self._threshold,
        )

    @abc.abstractmethod
    def _get_temp(self) -> Tuple[TempCelsius, TempCelsius, TempCelsius]:
        pass


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
        self._temp_input = Path(temp_path + "_input")
        self._temp_min = Path(temp_path + "_min")
        self._temp_max = Path(temp_path + "_max")
        self._min = min
        self._max = max

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

    @staticmethod
    def _read_temp_from_path(path: Path) -> TempCelsius:
        return TempCelsius(int(path.read_text().strip()) / 1000)


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
            if self._is_float(line.strip())
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

    @staticmethod
    def _is_float(s: str) -> bool:
        if not s:
            return False
        try:
            float(s)
        except (ValueError, TypeError):
            return False
        else:
            return True


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
