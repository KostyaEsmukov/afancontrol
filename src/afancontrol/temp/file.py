import glob
from pathlib import Path
from typing import Optional, Tuple

from afancontrol.configparser import ConfigParserSection
from afancontrol.temp.base import Temp, TempCelsius, aggregate, validate_aggregation


class FileTemp(Temp):
    def __init__(
        self,
        temp_path: str,
        *,
        min: Optional[TempCelsius],
        max: Optional[TempCelsius],
        panic: Optional[TempCelsius],
        threshold: Optional[TempCelsius],
        aggregation: str = "max",
    ) -> None:
        """
        `temp_path` is a literal path or glob pattern for temperature files
        containing integer values in millidegrees Celsius. It accepts hwmon
        input paths such as `/sys/class/hwmon/hwmon*/temp1_input` and shorthand
        such as `/sys/class/hwmon/hwmon*/temp1`.

        Paths that lack the _min/_max sibling files require explicit
        `min` and `max` bounds.

        Multiple matches are combined using `aggregation`.
        """
        super().__init__(panic=panic, threshold=threshold)
        self._temp_path = temp_path
        self._aggregation = validate_aggregation(aggregation)

        input_path = temp_path if temp_path.endswith("_input") else temp_path + "_input"
        matches = [path for path in glob.glob(input_path) if not Path(path).is_dir()]
        # Preserve hwmon shorthand when both forms match.
        if not matches and temp_path != input_path:  # non-`_input` path
            matches = [path for path in glob.glob(temp_path) if not Path(path).is_dir()]

        self._inputs = [Path(path) for path in sorted(matches or [input_path])]
        derive_bounds = all(path.name.endswith("_input") for path in self._inputs)
        self._min, self._max = self._resolve_bounds(min, max, derive_bounds)

    @classmethod
    def from_configparser(cls, section: ConfigParserSection) -> Temp:
        panic = TempCelsius(section.getfloat("panic", fallback=None))
        threshold = TempCelsius(section.getfloat("threshold", fallback=None))
        min = TempCelsius(section.getfloat("min", fallback=None))
        max = TempCelsius(section.getfloat("max", fallback=None))
        aggregation = section.get("aggregation", fallback="max")
        return cls(
            section["path"],
            min=min,
            max=max,
            panic=panic,
            threshold=threshold,
            aggregation=aggregation,
        )

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return (
                self._aggregation == other._aggregation
                and self._inputs == other._inputs
                and self._min == other._min
                and self._max == other._max
                and self._panic == other._panic
                and self._threshold == other._threshold
            )

        return NotImplemented

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return "%s(%s, min=%r, max=%r, panic=%r, threshold=%r, aggregation=%r)" % (
            type(self).__name__,
            self._temp_path,
            self._min,
            self._max,
            self._panic,
            self._threshold,
            self._aggregation,
        )

    def _get_temp(self) -> Tuple[TempCelsius, TempCelsius, TempCelsius]:
        temps = [self._read_temp_from_path(path) for path in self._inputs]
        temp = TempCelsius(aggregate(temps, self._aggregation))
        return temp, self._min, self._max

    def _resolve_bounds(
        self,
        min_temp: Optional[TempCelsius],
        max_temp: Optional[TempCelsius],
        derive_bounds: bool,
    ) -> Tuple[TempCelsius, TempCelsius]:
        if not derive_bounds and (min_temp is None or max_temp is None):
            raise RuntimeError(
                "The %s sensor requires explicit `min` and `max` temperatures"
                % self._temp_path
            )
        if min_temp is None:
            min_temp = max(self._read_bounds("min"))
        if max_temp is None:
            max_temp = min(self._read_bounds("max"))
        if not min_temp < max_temp:
            raise ValueError(
                "Min temperature must be less than max for %s (min=%s, max=%s)"
                % (self._temp_path, min_temp, max_temp)
            )
        return min_temp, max_temp

    def _read_bounds(self, bound: str) -> list[TempCelsius]:
        try:
            bounds = [
                self._read_temp_from_path(
                    Path(str(path).removesuffix("_input") + "_" + bound)
                )
                for path in self._inputs
            ]
        except FileNotFoundError:
            raise RuntimeError(
                "Please specify `min` and `max` temperatures for "
                "the %s sensor" % self._temp_path
            )
        return bounds

    def _read_temp_from_path(self, path: Path) -> TempCelsius:
        return TempCelsius(int(path.read_text().strip()) / 1000)
