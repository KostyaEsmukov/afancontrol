import random
from time import sleep
from unittest.mock import MagicMock

import pytest
import requests

from afancontrol.config import FanName, TempName
from afancontrol.manager.fans import Fans
from afancontrol.manager.report import Report
from afancontrol.manager.trigger import Triggers
from afancontrol.metrics import PrometheusMetrics
from afancontrol.pwmfan import PWMFanNorm
from afancontrol.temp import TempCelsius, TempStatus


def test_prometheus_metrics():
    mocked_fan = MagicMock(spec=PWMFanNorm)()
    mocked_triggers = MagicMock(spec=Triggers)()
    mocked_report = MagicMock(spec=Report)()

    port = random.randint(20000, 50000)
    metrics = PrometheusMetrics("127.0.0.1:%s" % port)
    with metrics:
        resp = requests.get("http://127.0.0.1:%s/metrics" % port)
        assert resp.status_code == 200
        assert "is_threshold 0.0" in resp.text

        with metrics.measure_tick():
            sleep(0.01)

        resp = requests.get("http://127.0.0.1:%s/metrics" % port)
        assert resp.status_code == 200
        assert "tick_duration_count 1.0" in resp.text
        assert "tick_duration_sum 0." in resp.text

        mocked_triggers.panic_trigger.is_alerting = True
        mocked_triggers.threshold_trigger.is_alerting = False

        mocked_fan.pwm_line_start = 100
        mocked_fan.pwm_line_end = 240
        mocked_fan.get_speed.return_value = 999
        mocked_fan.get_raw.return_value = 142

        metrics.tick(
            temps={
                TempName("goodtemp"): TempStatus(
                    temp=TempCelsius(74.0),
                    min=TempCelsius(40.0),
                    max=TempCelsius(50.0),
                    panic=TempCelsius(60.0),
                    threshold=None,
                    is_panic=True,
                    is_threshold=False,
                ),
                TempName("failingtemp"): None,
            },
            fans=Fans(
                fans={FanName("test"): mocked_fan},
                fans_speed_check_interval=1.0,
                report=mocked_report,
            ),
            triggers=mocked_triggers,
        )

        resp = requests.get("http://127.0.0.1:%s/metrics" % port)
        assert resp.status_code == 200
        assert 'temperature_current{temp_name="failingtemp"} NaN' in resp.text
        assert 'temperature_current{temp_name="goodtemp"} 74.0' in resp.text
        assert 'temperature_is_failing{temp_name="failingtemp"} 1.0' in resp.text
        assert 'temperature_is_failing{temp_name="goodtemp"} 0.0' in resp.text
        assert 'fan_rpm{fan_name="test"} 999.0' in resp.text
        assert 'fan_pwm{fan_name="test"} 142.0' in resp.text
        assert 'fan_is_failing{fan_name="test"} 0.0' in resp.text
        assert "is_panic 1.0" in resp.text
        assert "is_threshold 0.0" in resp.text
        print(resp.text)

    with pytest.raises(IOError):
        requests.get("http://127.0.0.1:%s/metrics" % port)
