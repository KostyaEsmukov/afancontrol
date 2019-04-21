import abc
import sys
from time import sleep
from typing import Iterable, Optional

from afancontrol.pwmfan import FanInputDevice, FanValue, PWMDevice, PWMFan, PWMValue

# Time to wait before measuring fan speed after setting a PWM value.
STEP_INTERVAL_SECONDS = 2

# Time to wait before starting the test right after resetting the fan
# (i.e. setting it to full speed).
FAN_RESET_INTERVAL_SECONDS = 7

EXIT_CODE_CTRL_C = 130  # https://stackoverflow.com/a/1101969


def main():
    print(
        """afancontrol_fantest

This program tests how changing the PWM value of a fan affects its speed.

In the beginning the fan would be stopped (by setting it to a minimum PWM value),
and then the PWM value would be increased in small steps, while also
measuring the speed as reported by the fan.

This data would help you to find the effective range of values
for the `pwm_line_start` and `pwm_line_end` settings where the correlation
between PWM and fan speed is close to linear. Usually its
`pwm_line_start = 100` and `pwm_line_end = 240`, but it is individual
for each fan. The allowed range for a PWM value is from 0 to 255.

Note that the fan would be stopped for some time during the test. If you'll
feel nervous, press Ctrl+C to stop the test and return the fan to full speed.

Before starting the test ensure that no fan control software is currently
controlling the fan you're going to test.

"""
    )
    try:
        pwm = read_stdin("PWM file of the fan")
        fan_input = read_stdin("fan_input file of the fan")

        print(
            """
Select an output format for the measurements.

`csv` data could be used to make a plot using something like MS Excel.
"""
        )
        out_format = read_stdin("Output format", ["human", "csv"], "human")
        output = dict(human=HumanMeasurementsOutput(), csv=CSVMeasurementsOutput())[
            out_format
        ]

        print(
            """
The default test is to stop the fan and then gracefully increase its speed.
You might want to reverse it, i.e. run the fan at full and then start
decreasing the speed. This would allow you to test the fan without fully
stopping it, if you abort the test with Ctrl+C when the speed becomes too low.
"""
        )
        direction = read_stdin("Test direction? ", ["increase", "decrease"], "increase")

        print(
            """
Choose a single step size for the PWM value. `accurate` equals 5 and provides
more accurate results, but is a slower options. `fast` equals 25 and completes
faster.
"""
        )
        pwm_step_size_alias = read_stdin(
            "PWM %s step size" % direction, ["accurate", "fast"], "accurate"
        )
        pwm_step_size = dict(accurate=PWMValue(5), fast=PWMValue(25))[
            pwm_step_size_alias
        ]
        if direction == "decrease":
            pwm_step_size = PWMValue(
                pwm_step_size * -1  # a bad PWM value, to be honest
            )

        fan = PWMFan(pwm=PWMDevice(pwm), fan_input=FanInputDevice(fan_input))
    except KeyboardInterrupt:
        print("")
        sys.exit(EXIT_CODE_CTRL_C)

    try:
        fantest(fan=fan, pwm_step_size=pwm_step_size, output=output)
    except KeyboardInterrupt:
        print("Fan has been returned to full speed")
        sys.exit(EXIT_CODE_CTRL_C)


def fantest(fan: PWMFan, pwm_step_size: PWMValue, output: "MeasurementsOutput") -> None:
    with fan:
        start = PWMFan.min_pwm
        stop = PWMFan.max_pwm
        if pwm_step_size > 0:
            print("Testing increase with step %s" % pwm_step_size)
            print("Waiting %s seconds for fan to stop..." % FAN_RESET_INTERVAL_SECONDS)
        else:
            start, stop = stop, start
            print("Testing decrease with step %s" % pwm_step_size)
            print(
                "Waiting %s seconds for fan to run in full speed..."
                % FAN_RESET_INTERVAL_SECONDS
            )

        fan.set(start)
        sleep(FAN_RESET_INTERVAL_SECONDS)

        print(output.header())

        prev_rpm = None
        for pwm_value in range(start, stop, pwm_step_size):
            fan.set(PWMValue(pwm_value))
            sleep(STEP_INTERVAL_SECONDS)
            rpm = fan.get_speed()

            rpm_delta = None  # Optional[FanValue]
            if prev_rpm is not None:
                rpm_delta = rpm - prev_rpm
            prev_rpm = rpm

            print(
                output.data_row(pwm=PWMValue(pwm_value), rpm=rpm, rpm_delta=rpm_delta)
            )

        print("Test is complete, returning fan to full speed")


class MeasurementsOutput(abc.ABC):
    @abc.abstractmethod
    def header(self) -> str:
        pass

    @abc.abstractmethod
    def data_row(
        self, pwm: PWMValue, rpm: FanValue, rpm_delta: Optional[FanValue]
    ) -> str:
        pass


class HumanMeasurementsOutput(MeasurementsOutput):
    def header(self) -> str:
        return """PWM -- PWM value;
RPM -- fan speed (as reported by the fan);
DELTA -- RPM increase since the last step."""

    def data_row(
        self, pwm: PWMValue, rpm: FanValue, rpm_delta: Optional[FanValue]
    ) -> str:
        return "PWM %s RPM %s DELTA %s" % (
            str(pwm).rjust(3),
            str(rpm).rjust(4),
            str(rpm_delta if rpm_delta is not None else "n/a").rjust(4),
        )


class CSVMeasurementsOutput(MeasurementsOutput):
    def header(self) -> str:
        return "pwm;rpm;rpm_delta"

    def data_row(
        self, pwm: PWMValue, rpm: FanValue, rpm_delta: Optional[FanValue]
    ) -> str:
        return "%s;%s;%s" % (pwm, rpm, rpm_delta if rpm_delta is not None else "")


def read_stdin(
    prompt: str, values: Optional[Iterable[str]] = None, default: Optional[str] = None
) -> str:
    if values is None:
        v = ""
    else:
        v = " (%s)" % ", ".join(values)

    if default is None:
        d = ""
    else:
        d = " [%s]" % default

    p = "%s%s%s: " % (prompt, v, d)

    while True:
        r = input(p)
        r = r.strip()

        if not r:
            if default is not None:
                r = default
            else:
                continue

        if values is None:
            break
        else:
            if r in values:
                break

    return r


if __name__ == "__main__":
    main()
