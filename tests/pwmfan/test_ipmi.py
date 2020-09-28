from unittest.mock import patch

import pytest

from afancontrol.pwmfan import FanValue, FreeIPMIFanSpeed


@pytest.fixture
def ipmi_sensors_output():
    return """
ID,Name,Type,Reading,Units,Event
17,FAN1,Fan,1400.00,RPM,'OK'
18,FAN2,Fan,1800.00,RPM,'OK'
19,FAN3,Fan,N/A,RPM,N/A
20,FAN4,Fan,N/A,RPM,N/A
21,FAN5,Fan,N/A,RPM,N/A
22,FAN6,Fan,N/A,RPM,N/A
""".lstrip()


def test_fan_speed(ipmi_sensors_output):
    fan_speed = FreeIPMIFanSpeed("FAN2")
    with patch.object(FreeIPMIFanSpeed, "_call_ipmi_sensors") as mock_call:
        mock_call.return_value = ipmi_sensors_output
        assert fan_speed.get_speed() == FanValue(1800)


def test_fan_speed_na(ipmi_sensors_output):
    fan_speed = FreeIPMIFanSpeed("FAN3")
    with patch.object(FreeIPMIFanSpeed, "_call_ipmi_sensors") as mock_call:
        mock_call.return_value = ipmi_sensors_output
        with pytest.raises(ValueError):
            fan_speed.get_speed()


def test_fan_speed_unknown(ipmi_sensors_output):
    fan_speed = FreeIPMIFanSpeed("FAN30")
    with patch.object(FreeIPMIFanSpeed, "_call_ipmi_sensors") as mock_call:
        mock_call.return_value = ipmi_sensors_output
        with pytest.raises(RuntimeError):
            fan_speed.get_speed()
