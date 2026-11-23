from typing import Optional
from unittest.mock import patch

import pytest

from afancontrol.temp import Temp, TempCelsius, TempStatus
from afancontrol.temp.base import aggregate


@pytest.mark.parametrize(
    "mode, expected",
    [("max", 50.0), ("min", 10.0), ("avg", 27.5), ("median", 25.0)],
)
def test_aggregate(mode, expected):
    temps = [float("nan"), 50.0, 10.0, float("inf"), 30.0, 20.0, float("-inf")]
    assert aggregate(temps, mode) == expected


@pytest.mark.parametrize("mode", ["max", "min", "avg", "median"])
@pytest.mark.parametrize("temps", [[], [float("nan"), float("inf"), float("-inf")]])
def test_aggregate_without_finite_readings(temps, mode):
    with pytest.raises(RuntimeError, match="empty list of valid temperature values"):
        aggregate(temps, mode)


def test_aggregate_unknown_mode():
    with pytest.raises(ValueError, match="Unsupported aggregation 'sum'"):
        aggregate([10.0], "sum")


class DummyTemp(Temp):
    def _get_temp(self):
        pass


@pytest.mark.parametrize(
    "temp, threshold, panic, is_threshold, is_panic",
    [
        (34.0, None, 60.0, False, False),
        (42.0, None, 60.0, False, False),
        (57.0, 55.0, 60.0, True, False),
        (61.0, 55.0, 61.0, True, True),
        (61.0, None, 61.0, False, True),
    ],
)
def test_temp(
    temp: TempCelsius,
    threshold: Optional[TempCelsius],
    panic: TempCelsius,
    is_threshold,
    is_panic,
):
    min = TempCelsius(40.0)
    max = TempCelsius(50.0)

    with patch.object(DummyTemp, "_get_temp") as mock_get_temp:
        t = DummyTemp(panic=panic, threshold=threshold)
        mock_get_temp.return_value = [temp, min, max]

        assert t.get() == TempStatus(
            temp=temp,
            min=min,
            max=max,
            panic=panic,
            threshold=threshold,
            is_panic=is_panic,
            is_threshold=is_threshold,
        )
