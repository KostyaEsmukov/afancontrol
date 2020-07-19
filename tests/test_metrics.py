import random
import types
from time import sleep
from unittest.mock import MagicMock

import pytest
import requests

from afancontrol.config import FanName, TempName
from afancontrol.fans import Fans
from afancontrol.metrics import PrometheusMetrics, prometheus_available
from afancontrol.pwmfannorm import PWMFanNorm
from afancontrol.report import Report
from afancontrol.temp import TempCelsius, TempStatus
from afancontrol.temps import ObservedTempStatus
from afancontrol.trigger import Triggers


@pytest.fixture
def requests_session():
    # Ignore system proxies, see https://stackoverflow.com/a/28521696
    with requests.Session() as session:
        session.trust_env = False
        yield session


@pytest.mark.skipif(
    not prometheus_available, reason="prometheus_client is not installed"
)
def test_prometheus_metrics(requests_session):
    mocked_fan = MagicMock(spec=PWMFanNorm)()
    mocked_triggers = MagicMock(spec=Triggers)()
    mocked_report = MagicMock(spec=Report)()

    port = random.randint(20000, 50000)
    metrics = PrometheusMetrics("127.0.0.1:%s" % port)
    with metrics:
        resp = requests_session.get("http://127.0.0.1:%s/metrics" % port)
        assert resp.status_code == 200
        assert "is_threshold 0.0" in resp.text

        with metrics.measure_tick():
            sleep(0.01)

        resp = requests_session.get("http://127.0.0.1:%s/metrics" % port)
        assert resp.status_code == 200
        assert "tick_duration_count 1.0" in resp.text
        assert "tick_duration_sum 0." in resp.text

        mocked_triggers.panic_trigger.is_alerting = True
        mocked_triggers.threshold_trigger.is_alerting = False

        mocked_fan.pwm_line_start = 100
        mocked_fan.pwm_line_end = 240
        mocked_fan.get_speed.return_value = 999
        mocked_fan.get_raw.return_value = 142
        mocked_fan.get = types.MethodType(PWMFanNorm.get, mocked_fan)
        mocked_fan.pwm_read.max_pwm = 255

        metrics.tick(
            temps={
                TempName("goodtemp"): ObservedTempStatus(
                    filtered=TempStatus(
                        temp=TempCelsius(74.0),
                        min=TempCelsius(40.0),
                        max=TempCelsius(50.0),
                        panic=TempCelsius(60.0),
                        threshold=None,
                        is_panic=True,
                        is_threshold=False,
                    ),
                    raw=TempStatus(
                        temp=TempCelsius(72.0),
                        min=TempCelsius(40.0),
                        max=TempCelsius(50.0),
                        panic=TempCelsius(60.0),
                        threshold=None,
                        is_panic=True,
                        is_threshold=False,
                    ),
                ),
                TempName("failingtemp"): ObservedTempStatus(filtered=None, raw=None),
            },
            fans=Fans(
                fans={FanName("test"): mocked_fan},
                readonly_fans={},
                report=mocked_report,
            ),
            triggers=mocked_triggers,
            arduino_connections={},
        )

        resp = requests_session.get("http://127.0.0.1:%s/metrics" % port)
        assert resp.status_code == 200
        print(resp.text)
        assert 'temperature_current{temp_name="failingtemp"} NaN' in resp.text
        assert 'temperature_current_raw{temp_name="failingtemp"} NaN' in resp.text
        assert 'temperature_current{temp_name="goodtemp"} 74.0' in resp.text
        assert 'temperature_current_raw{temp_name="goodtemp"} 72.0' in resp.text
        assert 'temperature_is_failing{temp_name="failingtemp"} 1.0' in resp.text
        assert 'temperature_is_failing{temp_name="goodtemp"} 0.0' in resp.text
        assert 'fan_rpm{fan_name="test"} 999.0' in resp.text
        assert 'fan_pwm{fan_name="test"} 142.0' in resp.text
        assert 'fan_pwm_normalized{fan_name="test"} 0.556' in resp.text
        assert 'fan_is_failing{fan_name="test"} 0.0' in resp.text
        assert "is_panic 1.0" in resp.text
        assert "is_threshold 0.0" in resp.text
        assert "last_metrics_tick_seconds_ago 0." in resp.text

    with pytest.raises(IOError):
        requests_session.get("http://127.0.0.1:%s/metrics" % port)


@pytest.mark.skipif(
    not prometheus_available, reason="prometheus_client is not installed"
)
def test_prometheus_faulty_fans_dont_break_metrics_collection(requests_session):
    mocked_fan = MagicMock(spec=PWMFanNorm)()
    mocked_triggers = MagicMock(spec=Triggers)()
    mocked_report = MagicMock(spec=Report)()

    port = random.randint(20000, 50000)
    metrics = PrometheusMetrics("127.0.0.1:%s" % port)
    with metrics:
        mocked_triggers.panic_trigger.is_alerting = False
        mocked_triggers.threshold_trigger.is_alerting = False

        mocked_fan.pwm_line_start = 100
        mocked_fan.pwm_line_end = 240
        mocked_fan.get_speed.side_effect = IOError
        mocked_fan.get_raw.side_effect = IOError

        # Must not raise despite the PWMFan methods raising above:
        metrics.tick(
            temps={
                TempName("failingtemp"): ObservedTempStatus(filtered=None, raw=None)
            },
            fans=Fans(
                fans={FanName("test"): mocked_fan},
                readonly_fans={},
                report=mocked_report,
            ),
            triggers=mocked_triggers,
            arduino_connections={},
        )

        resp = requests_session.get("http://127.0.0.1:%s/metrics" % port)
        assert resp.status_code == 200
        assert 'fan_pwm_line_start{fan_name="test"} 100.0' in resp.text
        assert 'fan_pwm_line_end{fan_name="test"} 240.0' in resp.text
        assert 'fan_rpm{fan_name="test"} NaN' in resp.text
        assert 'fan_pwm{fan_name="test"} NaN' in resp.text
        assert 'fan_pwm_normalized{fan_name="test"} NaN' in resp.text
        assert 'fan_is_failing{fan_name="test"} 0.0' in resp.text
        assert "is_panic 0.0" in resp.text
        assert "is_threshold 0.0" in resp.text
