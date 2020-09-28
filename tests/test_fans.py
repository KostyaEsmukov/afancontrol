from collections import OrderedDict
from unittest.mock import MagicMock

import pytest

from afancontrol.config import FanName
from afancontrol.fans import Fans
from afancontrol.pwmfan import BaseFanPWMRead
from afancontrol.pwmfannorm import PWMFanNorm, PWMValueNorm
from afancontrol.report import Report


@pytest.fixture
def report():
    return MagicMock(spec=Report)


@pytest.mark.parametrize("is_fan_failing", [False, True])
def test_smoke(report, is_fan_failing):
    fan = MagicMock(spec=PWMFanNorm)
    fans = Fans(fans={FanName("test"): fan}, readonly_fans={}, report=report)

    fan.set = lambda pwm_norm: int(255 * pwm_norm)
    fan.get_speed.return_value = 0 if is_fan_failing else 942
    fan.is_pwm_stopped = BaseFanPWMRead.is_pwm_stopped

    with fans:
        assert 1 == fan.__enter__.call_count
        fans.check_speeds()
        fans.set_all_to_full_speed()
        fans.set_fan_speeds({FanName("test"): PWMValueNorm(0.42)})
        assert fan.get_speed.call_count == 1
        if is_fan_failing:
            assert fans._failed_fans == {"test"}
            assert fans._stopped_fans == set()
        else:
            assert fans._failed_fans == set()
            assert fans._stopped_fans == set()

    assert 1 == fan.__exit__.call_count


def test_set_fan_speeds(report):
    mocked_fans = OrderedDict(
        [
            (FanName("test1"), MagicMock(spec=PWMFanNorm)),
            (FanName("test2"), MagicMock(spec=PWMFanNorm)),
            (FanName("test3"), MagicMock(spec=PWMFanNorm)),
            (FanName("test4"), MagicMock(spec=PWMFanNorm)),
        ]
    )

    for fan in mocked_fans.values():
        fan.set.return_value = 240
        fan.get_speed.return_value = 942
        fan.is_pwm_stopped = BaseFanPWMRead.is_pwm_stopped

    fans = Fans(fans=mocked_fans, readonly_fans={}, report=report)
    with fans:
        fans._ensure_fan_is_failing(FanName("test2"), Exception("test"))
        fans.set_fan_speeds(
            {
                FanName("test1"): PWMValueNorm(0.42),
                FanName("test2"): PWMValueNorm(0.42),
                FanName("test3"): PWMValueNorm(0.42),
                FanName("test4"): PWMValueNorm(0.42),
            }
        )
        assert [1, 0, 1, 1] == [f.set.call_count for f in mocked_fans.values()]
