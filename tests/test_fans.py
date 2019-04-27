from unittest.mock import MagicMock

import pytest

from afancontrol.config import FanName
from afancontrol.fans import Fans
from afancontrol.pwmfan import BasePWMFan, PWMFanNorm, PWMValueNorm
from afancontrol.report import Report


@pytest.fixture
def report():
    return MagicMock(spec=Report)


@pytest.mark.parametrize("is_fan_failing", [False, True])
def test_smoke(report, is_fan_failing):
    fan = MagicMock(spec=PWMFanNorm)
    fans = Fans({FanName("test"): fan}, report=report)

    fan.set = lambda pwm_norm: int(255 * pwm_norm)
    fan.get_speed.return_value = 0 if is_fan_failing else 942
    fan.is_pwm_stopped = BasePWMFan.is_pwm_stopped

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
