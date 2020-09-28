from contextlib import ExitStack
from unittest.mock import MagicMock

import pytest

from afancontrol.pwmfan import (
    FanInputDevice,
    LinuxFanPWMRead,
    LinuxFanPWMWrite,
    LinuxFanSpeed,
    PWMDevice,
    PWMValue,
)
from afancontrol.pwmfannorm import PWMFanNorm


@pytest.fixture
def pwm_path(temp_path):
    # pwm = /sys/class/hwmon/hwmon0/pwm2
    pwm_path = temp_path / "pwm2"
    pwm_path.write_text("0\n")
    return pwm_path


@pytest.fixture
def pwm_enable_path(temp_path):
    pwm_enable_path = temp_path / "pwm2_enable"
    pwm_enable_path.write_text("0\n")
    return pwm_enable_path


@pytest.fixture
def fan_input_path(temp_path):
    # fan_input = /sys/class/hwmon/hwmon0/fan2_input
    fan_input_path = temp_path / "fan2_input"
    fan_input_path.write_text("1300\n")
    return fan_input_path


@pytest.fixture
def fan_speed(fan_input_path):
    return LinuxFanSpeed(fan_input=FanInputDevice(str(fan_input_path)))


@pytest.fixture
def pwm_read(pwm_path):
    return LinuxFanPWMRead(pwm=PWMDevice(str(pwm_path)))


@pytest.fixture
def pwm_write(pwm_path):
    pwm_write = LinuxFanPWMWrite(pwm=PWMDevice(str(pwm_path)))

    # We write to the pwm_enable file values without newlines,
    # but when they're read back, they might contain newlines.
    # This hack below is to simulate just that: the written values should
    # contain newlines.
    original_pwm_enable = pwm_write._pwm_enable
    pwm_enable = MagicMock(wraps=original_pwm_enable)
    pwm_enable.write_text = lambda text: original_pwm_enable.write_text(text + "\n")
    pwm_write._pwm_enable = pwm_enable

    return pwm_write


@pytest.fixture
def pwmfan_norm(fan_speed, pwm_read, pwm_write):
    return PWMFanNorm(
        fan_speed,
        pwm_read,
        pwm_write,
        pwm_line_start=PWMValue(100),
        pwm_line_end=PWMValue(240),
        never_stop=False,
    )


@pytest.mark.parametrize("pwmfan_fixture", ["fan_speed", "pwmfan_norm"])
def test_get_speed(pwmfan_fixture, fan_speed, pwmfan_norm, fan_input_path):
    fan = locals()[pwmfan_fixture]
    fan_input_path.write_text("721\n")
    assert 721 == fan.get_speed()


@pytest.mark.parametrize("pwmfan_fixture", ["pwm_write", "pwmfan_norm"])
@pytest.mark.parametrize("raises", [True, False])
def test_enter_exit(
    raises, pwmfan_fixture, pwm_write, pwmfan_norm, pwm_enable_path, pwm_path
):
    fan = locals()[pwmfan_fixture]

    class Exc(Exception):
        pass

    with ExitStack() as stack:
        if raises:
            stack.enter_context(pytest.raises(Exc))
        stack.enter_context(fan)

        assert "1" == pwm_enable_path.read_text().strip()
        assert "255" == pwm_path.read_text()

        value = dict(pwm_write=100, pwmfan_norm=0.39)[pwmfan_fixture]  # 100/255 ~= 0.39
        fan.set(value)

        assert "1" == pwm_enable_path.read_text().strip()
        assert "100" == pwm_path.read_text()

        if raises:
            raise Exc()

    assert "0" == pwm_enable_path.read_text().strip()
    assert "100" == pwm_path.read_text()  # `fancontrol` doesn't reset speed


def test_get_set_pwmfan(pwm_read, pwm_write, pwm_path):
    pwm_write.set(142)
    assert "142" == pwm_path.read_text()

    pwm_path.write_text("132\n")
    assert 132 == pwm_read.get()

    pwm_write.set_full_speed()
    assert "255" == pwm_path.read_text()

    with pytest.raises(ValueError):
        pwm_write.set(256)

    with pytest.raises(ValueError):
        pwm_write.set(-1)


def test_get_set_pwmfan_norm(pwmfan_norm, pwm_path):
    pwmfan_norm.set(0.42)
    assert "101" == pwm_path.read_text()

    pwm_path.write_text("132\n")
    assert pytest.approx(0.517, 0.01) == pwmfan_norm.get()

    pwmfan_norm.set_full_speed()
    assert "255" == pwm_path.read_text()

    assert 238 == pwmfan_norm.set(0.99)
    assert "238" == pwm_path.read_text()

    assert 255 == pwmfan_norm.set(1.0)
    assert "255" == pwm_path.read_text()

    assert 255 == pwmfan_norm.set(1.1)
    assert "255" == pwm_path.read_text()

    assert 0 == pwmfan_norm.set(-0.1)
    assert "0" == pwm_path.read_text()
