from pathlib import Path
from unittest.mock import Mock

import pytest

from afancontrol.arduino import (
    ArduinoConnection,
    ArduinoName,
    ArduinoPin,
    ArduinoPWMFan,
    pyserial_available,
)
from afancontrol.config import (
    Actions,
    AlertCommands,
    DaemonCLIConfig,
    DaemonConfig,
    FanName,
    FanSpeedModifier,
    FansTempsRelation,
    MappingName,
    ParsedConfig,
    TempName,
    TriggerConfig,
    parse_config,
)
from afancontrol.pwmfan import (
    FanInputDevice,
    LinuxPWMFan,
    PWMDevice,
    PWMFanNorm,
    PWMValue,
)
from afancontrol.temp import FileTemp, HDDTemp, TempCelsius


@pytest.fixture
def pkg_conf():
    return Path(__file__).parents[1] / "pkg" / "afancontrol.conf"


@pytest.fixture
def example_conf():
    return Path(__file__).parents[0] / "data" / "afancontrol-example.conf"


def path_from_str(contents: str) -> Path:
    p = Mock(spec=Path)
    p.read_text.return_value = contents
    return p


@pytest.mark.skipif(not pyserial_available, reason="pyserial is not installed")
def test_pkg_conf(pkg_conf: Path):
    daemon_cli_config = DaemonCLIConfig(
        pidfile=None, logfile=None, exporter_listen_host=None
    )

    parsed = parse_config(pkg_conf, daemon_cli_config)
    assert parsed == ParsedConfig(
        daemon=DaemonConfig(
            pidfile="/var/run/afancontrol.pid",
            logfile="/var/log/afancontrol.log",
            interval=5,
            exporter_listen_host=None,
        ),
        report_cmd=(
            'printf "Subject: %s\nTo: %s\n\n%b" '
            '"afancontrol daemon report: %REASON%" root "%MESSAGE%" | sendmail -t'
        ),
        triggers=TriggerConfig(
            global_commands=Actions(
                panic=AlertCommands(enter_cmd=None, leave_cmd=None),
                threshold=AlertCommands(enter_cmd=None, leave_cmd=None),
            ),
            temp_commands={
                TempName("mobo"): Actions(
                    panic=AlertCommands(enter_cmd=None, leave_cmd=None),
                    threshold=AlertCommands(enter_cmd=None, leave_cmd=None),
                )
            },
        ),
        fans={
            FanName("hdd"): PWMFanNorm(
                LinuxPWMFan(
                    PWMDevice("/sys/class/hwmon/hwmon0/device/pwm2"),
                    FanInputDevice("/sys/class/hwmon/hwmon0/device/fan2_input"),
                ),
                pwm_line_start=PWMValue(100),
                pwm_line_end=PWMValue(240),
                never_stop=False,
            )
        },
        temps={
            TempName("mobo"): FileTemp(
                "/sys/class/hwmon/hwmon0/device/temp1_input",
                min=TempCelsius(30.0),
                max=TempCelsius(40.0),
                panic=None,
                threshold=None,
            )
        },
        mappings={
            MappingName("1"): FansTempsRelation(
                temps=[TempName("mobo")],
                fans=[FanSpeedModifier(fan=FanName("hdd"), modifier=0.6)],
            )
        },
    )


@pytest.mark.skipif(not pyserial_available, reason="pyserial is not installed")
def test_example_conf(example_conf: Path):
    daemon_cli_config = DaemonCLIConfig(
        pidfile=None, logfile=None, exporter_listen_host=None
    )

    parsed = parse_config(example_conf, daemon_cli_config)
    assert parsed == ParsedConfig(
        daemon=DaemonConfig(
            pidfile="/var/run/afancontrol.pid",
            logfile="/var/log/afancontrol.log",
            exporter_listen_host="127.0.0.1:8083",
            interval=5,
        ),
        report_cmd=(
            'printf "Subject: %s\nTo: %s\n\n%b" '
            '"afancontrol daemon report: %REASON%" root "%MESSAGE%" | sendmail -t'
        ),
        triggers=TriggerConfig(
            global_commands=Actions(
                panic=AlertCommands(enter_cmd=None, leave_cmd=None),
                threshold=AlertCommands(enter_cmd=None, leave_cmd=None),
            ),
            temp_commands={
                TempName("hdds"): Actions(
                    panic=AlertCommands(enter_cmd=None, leave_cmd=None),
                    threshold=AlertCommands(enter_cmd=None, leave_cmd=None),
                ),
                TempName("mobo"): Actions(
                    panic=AlertCommands(enter_cmd=None, leave_cmd=None),
                    threshold=AlertCommands(enter_cmd=None, leave_cmd=None),
                ),
            },
        ),
        fans={
            FanName("cpu"): PWMFanNorm(
                LinuxPWMFan(
                    PWMDevice("/sys/class/hwmon/hwmon0/device/pwm1"),
                    FanInputDevice("/sys/class/hwmon/hwmon0/device/fan1_input"),
                ),
                pwm_line_start=PWMValue(100),
                pwm_line_end=PWMValue(240),
                never_stop=True,
            ),
            FanName("hdd"): PWMFanNorm(
                LinuxPWMFan(
                    PWMDevice("/sys/class/hwmon/hwmon0/device/pwm2"),
                    FanInputDevice("/sys/class/hwmon/hwmon0/device/fan2_input"),
                ),
                pwm_line_start=PWMValue(100),
                pwm_line_end=PWMValue(240),
                never_stop=False,
            ),
            FanName("my_arduino_fan"): PWMFanNorm(
                ArduinoPWMFan(
                    ArduinoConnection(
                        ArduinoName("mymicro"),
                        "/dev/ttyACM0",  # linux
                        # "/dev/cu.usbmodem14201",  # macos
                        baudrate=115200,
                        status_ttl=5,
                    ),
                    pwm_pin=ArduinoPin(9),
                    tacho_pin=ArduinoPin(3),
                ),
                pwm_line_start=PWMValue(100),
                pwm_line_end=PWMValue(240),
                never_stop=True,
            ),
        },
        temps={
            TempName("hdds"): HDDTemp(
                "/dev/sd?",
                min=TempCelsius(35.0),
                max=TempCelsius(48.0),
                panic=TempCelsius(55.0),
                threshold=None,
                hddtemp_bin="hddtemp",
            ),
            TempName("mobo"): FileTemp(
                "/sys/class/hwmon/hwmon0/device/temp1_input",
                min=TempCelsius(30.0),
                max=TempCelsius(40.0),
                panic=None,
                threshold=None,
            ),
        },
        mappings={
            MappingName("1"): FansTempsRelation(
                temps=[TempName("mobo"), TempName("hdds")],
                fans=[
                    FanSpeedModifier(fan=FanName("cpu"), modifier=1.0),
                    FanSpeedModifier(fan=FanName("hdd"), modifier=0.6),
                    FanSpeedModifier(fan=FanName("my_arduino_fan"), modifier=0.222),
                ],
            ),
            MappingName("2"): FansTempsRelation(
                temps=[TempName("hdds")],
                fans=[FanSpeedModifier(fan=FanName("hdd"), modifier=1.0)],
            ),
        },
    )


def test_minimal_config() -> None:
    daemon_cli_config = DaemonCLIConfig(
        pidfile=None, logfile=None, exporter_listen_host=None
    )

    config = """
[daemon]

[actions]

[temp:mobo]
type = file
path = /sys/class/hwmon/hwmon0/device/temp1_input

[fan: case]
pwm = /sys/class/hwmon/hwmon0/device/pwm2
fan_input = /sys/class/hwmon/hwmon0/device/fan2_input

[mapping:1]
fans = case*0.6,
temps = mobo
"""
    parsed = parse_config(path_from_str(config), daemon_cli_config)
    assert parsed == ParsedConfig(
        daemon=DaemonConfig(
            pidfile="/var/run/afancontrol.pid",
            logfile=None,
            exporter_listen_host=None,
            interval=5,
        ),
        report_cmd=(
            'printf "Subject: %s\nTo: %s\n\n%b" '
            '"afancontrol daemon report: %REASON%" root "%MESSAGE%" | sendmail -t'
        ),
        triggers=TriggerConfig(
            global_commands=Actions(
                panic=AlertCommands(enter_cmd=None, leave_cmd=None),
                threshold=AlertCommands(enter_cmd=None, leave_cmd=None),
            ),
            temp_commands={
                TempName("mobo"): Actions(
                    panic=AlertCommands(enter_cmd=None, leave_cmd=None),
                    threshold=AlertCommands(enter_cmd=None, leave_cmd=None),
                )
            },
        ),
        fans={
            FanName("case"): PWMFanNorm(
                LinuxPWMFan(
                    PWMDevice("/sys/class/hwmon/hwmon0/device/pwm2"),
                    FanInputDevice("/sys/class/hwmon/hwmon0/device/fan2_input"),
                ),
                pwm_line_start=PWMValue(100),
                pwm_line_end=PWMValue(240),
                never_stop=True,
            )
        },
        temps={
            TempName("mobo"): FileTemp(
                "/sys/class/hwmon/hwmon0/device/temp1_input",
                min=None,
                max=None,
                panic=None,
                threshold=None,
            )
        },
        mappings={
            MappingName("1"): FansTempsRelation(
                temps=[TempName("mobo")],
                fans=[FanSpeedModifier(fan=FanName("case"), modifier=0.6)],
            )
        },
    )
