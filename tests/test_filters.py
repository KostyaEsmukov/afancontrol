import pytest

from afancontrol.filters import MovingMedianFilter, MovingQuantileFilter, NullFilter
from afancontrol.temp import TempCelsius, TempStatus


def make_temp_status(temp):
    return TempStatus(
        min=TempCelsius(30),
        max=TempCelsius(50),
        temp=TempCelsius(temp),
        panic=None,
        threshold=None,
        is_panic=False,
        is_threshold=False,
    )


@pytest.mark.parametrize(
    "filter",
    [
        NullFilter(),
        MovingMedianFilter(window_size=3),
        MovingQuantileFilter(0.5, window_size=3),
    ],
)
def test_none(filter):
    with filter:
        assert filter.apply(None) is None


@pytest.mark.parametrize(
    "filter",
    [
        NullFilter(),
        MovingMedianFilter(window_size=3),
        MovingQuantileFilter(0.5, window_size=3),
    ],
)
def test_single_point(filter):
    with filter:
        assert filter.apply(make_temp_status(42.0)) == make_temp_status(42.0)


def test_moving_quantile():
    f = MovingQuantileFilter(0.8, window_size=10)
    with f:
        assert f.apply(make_temp_status(42.0)) == make_temp_status(42.0)
        assert f.apply(make_temp_status(45.0)) == make_temp_status(45.0)
        assert f.apply(make_temp_status(47.0)) == make_temp_status(47.0)
        assert f.apply(make_temp_status(123.0)) == make_temp_status(123.0)
        assert f.apply(make_temp_status(46.0)) == make_temp_status(123.0)
        assert f.apply(make_temp_status(49.0)) == make_temp_status(49.0)
        assert f.apply(make_temp_status(51.0)) == make_temp_status(51.0)
        assert f.apply(None) == make_temp_status(123.0)
        assert f.apply(None) is None
        assert f.apply(make_temp_status(51.0)) is None
        assert f.apply(make_temp_status(53.0)) is None


def test_moving_median():
    f = MovingMedianFilter(window_size=3)
    with f:
        assert f.apply(make_temp_status(42.0)) == make_temp_status(42.0)
        assert f.apply(make_temp_status(45.0)) == make_temp_status(45.0)
        assert f.apply(make_temp_status(47.0)) == make_temp_status(45.0)
        assert f.apply(make_temp_status(123.0)) == make_temp_status(47.0)
        assert f.apply(make_temp_status(46.0)) == make_temp_status(47.0)
        assert f.apply(make_temp_status(49.0)) == make_temp_status(49.0)
        assert f.apply(make_temp_status(51.0)) == make_temp_status(49.0)
        assert f.apply(None) == make_temp_status(51.0)
        assert f.apply(None) is None
        assert f.apply(make_temp_status(51.0)) is None
        assert f.apply(make_temp_status(53.0)) == make_temp_status(53.0)
