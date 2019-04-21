from contextlib import ExitStack
from typing import Type
from unittest.mock import MagicMock, patch

import pytest

from afancontrol import fantest
from afancontrol.fantest import (
    CSVMeasurementsOutput,
    HumanMeasurementsOutput,
    MeasurementsOutput,
    main,
)
from afancontrol.pwmfan import PWMFan, PWMValue


def test_main():
    with ExitStack() as stack:
        mocked_fantest = stack.enter_context(patch.object(fantest, "fantest"))
        mocked_read_stdin = stack.enter_context(patch.object(fantest, "read_stdin"))
        mocked_read_stdin.side_effect = [
            "/sys/class/hwmon/hwmon0/device/pwm2",
            "/sys/class/hwmon/hwmon0/device/fan2_input",
            "human",
            "increase",
            "accurate",
        ]
        main()

        assert mocked_fantest.call_count == 1

        args, kwargs = mocked_fantest.call_args
        assert not args
        assert kwargs.keys() == {"fan", "pwm_step_size", "output"}
        assert kwargs["fan"] == PWMFan(
            "/sys/class/hwmon/hwmon0/device/pwm2",
            "/sys/class/hwmon/hwmon0/device/fan2_input",
        )
        assert kwargs["pwm_step_size"] == 5
        assert isinstance(kwargs["output"], HumanMeasurementsOutput)


@pytest.mark.parametrize("pwm_step_size", [5, -5])
@pytest.mark.parametrize("output_cls", [HumanMeasurementsOutput, CSVMeasurementsOutput])
def test_fantest(output_cls: Type[MeasurementsOutput], pwm_step_size: PWMValue):
    mocked_fan = MagicMock(spec=PWMFan)
    output = output_cls()

    with ExitStack() as stack:
        mocked_sleep = stack.enter_context(patch.object(fantest, "sleep"))
        mocked_fan.get_speed.return_value = 999

        fantest.fantest(fan=mocked_fan, pwm_step_size=pwm_step_size, output=output)

        assert mocked_fan.set.call_count == (255 // abs(pwm_step_size)) + 1
        assert mocked_fan.get_speed.call_count == (255 // abs(pwm_step_size))
        assert mocked_sleep.call_count == (255 // abs(pwm_step_size)) + 1

        if pwm_step_size > 0:
            # increase
            expected_set = [0] + list(range(0, 255, pwm_step_size))
        else:
            # decrease
            expected_set = [255] + list(range(255, 0, pwm_step_size))
        assert [pwm for (pwm,), _ in mocked_fan.set.call_args_list] == expected_set
