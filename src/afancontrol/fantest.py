import abc
import sys
from time import sleep
from typing import Optional

import click

from afancontrol.arduino import (
    DEFAULT_BAUDRATE,
    ArduinoConnection,
    ArduinoName,
    ArduinoPin,
)
from afancontrol.pwmfan import (
    ArduinoFanPWMRead,
    ArduinoFanPWMWrite,
    ArduinoFanSpeed,
    FanInputDevice,
    FanValue,
    LinuxFanPWMRead,
    LinuxFanPWMWrite,
    LinuxFanSpeed,
    PWMDevice,
    PWMValue,
    ReadWriteFan,
)

# Time to wait before measuring fan speed after setting a PWM value.
STEP_INTERVAL_SECONDS = 2

# Time to wait before starting the test right after resetting the fan
# (i.e. setting it to full speed).
FAN_RESET_INTERVAL_SECONDS = 7

EXIT_CODE_CTRL_C = 130  # https://stackoverflow.com/a/1101969

HELP_FAN_TYPE = (
    "Linux -- a standard PWM fan connected to a motherboard; "
    "Arduino -- a PWM fan connected to an Arduino board."
)

HELP_LINUX_PWM_FILE = (
    "PWM file for a Linux PWM fan, e.g. `/sys/class/hwmon/hwmon0/device/pwm2`."
)
HELP_LINUX_FAN_INPUT_FILE = (
    "Fan input (tachometer) file for a Linux PWM fan, "
    "e.g. `/sys/class/hwmon/hwmon0/device/fan2_input`."
)

HELP_ARDUINO_SERIAL_URL = "URL for the Arduino's Serial port"
HELP_ARDUINO_BAUDRATE = "Arduino Serial connection baudrate"
HELP_ARDUINO_PWM_PIN = (
    "Arduino Board pin where the target fan's PWM wire is connected to."
)
HELP_ARDUINO_TACHO_PIN = (
    "Arduino Board pin where the target fan's tachometer wire is connected to."
)

HELP_OUTPUT_FORMAT = (
    "Output format for the measurements. `csv` data could be used "
    "to make a plot using a spreadsheet program like MS Excel."
)
HELP_TEST_DIRECTION = (
    "The default test is to stop the fan and then gracefully increase its speed. "
    "You might want to reverse it, i.e. run the fan at full speed and then start "
    "decreasing the speed. This would allow you to test the fan without fully "
    "stopping it, if you abort the test with Ctrl+C when the speed becomes too low."
)
HELP_PWM_STEP_SIZE = (
    "A single step size for the PWM value. `accurate` equals to 5 and provides "
    "more accurate results, but is a slower option. `fast` equals to 25 and completes "
    "faster."
)


@click.command()
@click.option(
    "--fan-type",
    help="FAN type. %s" % HELP_FAN_TYPE,
    default="linux",
    type=click.Choice(["linux", "arduino"]),
    prompt="\n%s\nFAN type (linux, arduino)" % HELP_FAN_TYPE,
    # `show_choices` is supported since click 7.0
    show_default=True,
)
@click.option(
    "--linux-fan-pwm",
    help=HELP_LINUX_PWM_FILE,
    type=click.Path(exists=True, dir_okay=False),
)
@click.option(
    "--linux-fan-input",
    help=HELP_LINUX_FAN_INPUT_FILE,
    type=click.Path(exists=True, dir_okay=False),
)
@click.option("--arduino-serial-url", help=HELP_ARDUINO_SERIAL_URL, type=str)
@click.option(
    "--arduino-baudrate",
    help=HELP_ARDUINO_BAUDRATE,
    type=int,
    default=DEFAULT_BAUDRATE,
    show_default=True,
)
@click.option("--arduino-pwm-pin", help=HELP_ARDUINO_PWM_PIN, type=int)
@click.option("--arduino-tacho-pin", help=HELP_ARDUINO_TACHO_PIN, type=int)
@click.option(
    "-f",
    "--output-format",
    help=HELP_OUTPUT_FORMAT,
    default="human",
    type=click.Choice(["human", "csv"]),
    prompt="\n%s\nOutput format (human, csv)" % HELP_OUTPUT_FORMAT,
    show_default=True,
)
@click.option(
    "-d",
    "--direction",
    help=HELP_TEST_DIRECTION,
    default="increase",
    type=click.Choice(["increase", "decrease"]),
    prompt="\n%s\nTest direction (increase decrease)" % HELP_TEST_DIRECTION,
    show_default=True,
)
@click.option(
    "-s",
    "--pwm-step-size",
    help=HELP_PWM_STEP_SIZE,
    default="accurate",
    type=click.Choice(["accurate", "fast"]),
    prompt="\n%s\nPWM step size (accurate fast)" % HELP_PWM_STEP_SIZE,
    show_default=True,
)
def fantest(
    *,
    fan_type: str,
    linux_fan_pwm: Optional[str],
    linux_fan_input: Optional[str],
    arduino_serial_url: Optional[str],
    arduino_baudrate: int,
    arduino_pwm_pin: Optional[int],
    arduino_tacho_pin: Optional[int],
    output_format: str,
    direction: str,
    pwm_step_size: str
) -> None:
    """The PWM fan testing program.

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
    try:
        if fan_type == "linux":
            if not linux_fan_pwm:
                linux_fan_pwm = click.prompt(
                    "\n%s\nPWM file" % HELP_LINUX_PWM_FILE,
                    type=click.Path(exists=True, dir_okay=False),
                )

            if not linux_fan_input:
                linux_fan_input = click.prompt(
                    "\n%s\nFan input file" % HELP_LINUX_FAN_INPUT_FILE,
                    type=click.Path(exists=True, dir_okay=False),
                )

            assert linux_fan_pwm is not None
            assert linux_fan_input is not None
            fan = ReadWriteFan(
                fan_speed=LinuxFanSpeed(FanInputDevice(linux_fan_input)),
                pwm_read=LinuxFanPWMRead(PWMDevice(linux_fan_pwm)),
                pwm_write=LinuxFanPWMWrite(PWMDevice(linux_fan_pwm)),
            )
        elif fan_type == "arduino":
            if not arduino_serial_url:
                arduino_serial_url = click.prompt(
                    "\n%s\nArduino Serial url" % HELP_ARDUINO_SERIAL_URL, type=str
                )

                # typeshed currently specifies `Optional[str]` for `default`,
                # see https://github.com/python/typeshed/blob/5acc22d82aa01005ea47ef64f31cad7e16e78450/third_party/2and3/click/termui.pyi#L34  # noqa
                # however the click docs say that `default` can be of any type,
                # see https://click.palletsprojects.com/en/7.x/prompts/#input-prompts
                # Hence the `type: ignore`.
                arduino_baudrate = click.prompt(  # type: ignore
                    "\n%s\nBaudrate" % HELP_ARDUINO_BAUDRATE,
                    type=int,
                    default=str(arduino_baudrate),
                    show_default=True,
                )
            if not arduino_pwm_pin and arduino_pwm_pin != 0:
                arduino_pwm_pin = click.prompt(
                    "\n%s\nArduino PWM pin" % HELP_ARDUINO_PWM_PIN, type=int
                )
            if not arduino_tacho_pin and arduino_tacho_pin != 0:
                arduino_tacho_pin = click.prompt(
                    "\n%s\nArduino Tachometer pin" % HELP_ARDUINO_TACHO_PIN, type=int
                )

            assert arduino_serial_url is not None
            arduino_connection = ArduinoConnection(
                name=ArduinoName("_fantest"),
                serial_url=arduino_serial_url,
                baudrate=arduino_baudrate,
            )
            assert arduino_pwm_pin is not None
            assert arduino_tacho_pin is not None
            fan = ReadWriteFan(
                fan_speed=ArduinoFanSpeed(
                    arduino_connection, tacho_pin=ArduinoPin(arduino_tacho_pin)
                ),
                pwm_read=ArduinoFanPWMRead(
                    arduino_connection, pwm_pin=ArduinoPin(arduino_pwm_pin)
                ),
                pwm_write=ArduinoFanPWMWrite(
                    arduino_connection, pwm_pin=ArduinoPin(arduino_pwm_pin)
                ),
            )
        else:
            raise AssertionError(
                "unreachable if the `fan_type`'s allowed `values` are in sync"
            )

        output = {"human": HumanMeasurementsOutput(), "csv": CSVMeasurementsOutput()}[
            output_format
        ]
        pwm_step_size_value = {"accurate": PWMValue(5), "fast": PWMValue(25)}[
            pwm_step_size
        ]
        if direction == "decrease":
            pwm_step_size_value = PWMValue(
                pwm_step_size_value * -1  # a bad PWM value, to be honest
            )
    except KeyboardInterrupt:
        click.echo("")
        sys.exit(EXIT_CODE_CTRL_C)

    try:
        run_fantest(fan=fan, pwm_step_size=pwm_step_size_value, output=output)
    except KeyboardInterrupt:
        click.echo("Fan has been returned to full speed")
        sys.exit(EXIT_CODE_CTRL_C)


def run_fantest(
    fan: ReadWriteFan, pwm_step_size: PWMValue, output: "MeasurementsOutput"
) -> None:
    with fan.fan_speed, fan.pwm_read, fan.pwm_write:
        start = fan.pwm_read.min_pwm
        stop = fan.pwm_read.max_pwm
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

        fan.pwm_write.set(start)
        sleep(FAN_RESET_INTERVAL_SECONDS)

        print(output.header())

        prev_rpm = None
        for pwm_value in range(start, stop, pwm_step_size):
            fan.pwm_write.set(PWMValue(pwm_value))
            sleep(STEP_INTERVAL_SECONDS)
            rpm = fan.fan_speed.get_speed()

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
