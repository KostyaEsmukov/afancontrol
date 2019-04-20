from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest

from afancontrol import config
from afancontrol.config import (
    Actions,
    AlertCommands,
    DaemonCLIConfig,
    DaemonConfig,
    FanSpeedModifier,
    FansTempsRelation,
    ParsedConfig,
    TriggerConfig,
    parse_config,
)
from afancontrol.pwmfan import PWMFanNorm
from afancontrol.temp import FileTemp, HDDTemp


@pytest.fixture
def example_conf():
    return Path(__file__).parents[1] / "afancontrol.cfg"


@pytest.fixture
def mock_hddtemp_version():
    with patch.object(config, "exec_shell_command") as mock_exec_shell_command:
        yield mock_exec_shell_command
        assert mock_exec_shell_command.call_args_list == [call("hddtemp --version")]


def path_from_str(contents: str) -> Path:
    p = Mock(spec=Path)
    p.read_text.return_value = contents
    return p


def test_example_conf(example_conf: Path, mock_hddtemp_version):
    daemon_cli_config = DaemonCLIConfig(pidfile=None, logfile=None)

    parsed = parse_config(example_conf, daemon_cli_config)
    assert parsed == ParsedConfig(
        daemon=DaemonConfig(
            pidfile="/var/run/afancontrol.pid",
            logfile="/var/log/afancontrol.log",
            interval=5,
            fans_speed_check_interval=3,
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
                "hdds": Actions(
                    panic=AlertCommands(enter_cmd=None, leave_cmd=None),
                    threshold=AlertCommands(enter_cmd=None, leave_cmd=None),
                ),
                "mobo": Actions(
                    panic=AlertCommands(enter_cmd=None, leave_cmd=None),
                    threshold=AlertCommands(enter_cmd=None, leave_cmd=None),
                ),
            },
        ),
        fans={
            "cpu": PWMFanNorm(
                "/sys/class/hwmon/hwmon0/device/pwm1",
                "/sys/class/hwmon/hwmon0/device/fan1_input",
                pwm_line_start=100,
                pwm_line_end=240,
                never_stop=True,
            ),
            "hdd": PWMFanNorm(
                "/sys/class/hwmon/hwmon0/device/pwm2",
                "/sys/class/hwmon/hwmon0/device/fan2_input",
                pwm_line_start=100,
                pwm_line_end=240,
                never_stop=False,
            ),
        },
        temps={
            "hdds": HDDTemp(
                "/dev/sd?",
                min=35.0,
                max=48.0,
                panic=55.0,
                threshold=None,
                hddtemp_bin="hddtemp",
            ),
            "mobo": FileTemp(
                "/sys/class/hwmon/hwmon0/device/temp1_input",
                min=30.0,
                max=40.0,
                panic=None,
                threshold=None,
            ),
        },
        mappings={
            "1": FansTempsRelation(
                temps=["mobo", "hdds"],
                fans=[
                    FanSpeedModifier(fan="cpu", modifier=1.0),
                    FanSpeedModifier(fan="hdd", modifier=0.6),
                ],
            ),
            "2": FansTempsRelation(
                temps=["hdds"], fans=[FanSpeedModifier(fan="hdd", modifier=1.0)]
            ),
        },
    )


def test_minimal_config(mock_hddtemp_version):
    daemon_cli_config = DaemonCLIConfig(pidfile=None, logfile=None)

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
            interval=5,
            fans_speed_check_interval=3,
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
                "mobo": Actions(
                    panic=AlertCommands(enter_cmd=None, leave_cmd=None),
                    threshold=AlertCommands(enter_cmd=None, leave_cmd=None),
                )
            },
        ),
        fans={
            "case": PWMFanNorm(
                "/sys/class/hwmon/hwmon0/device/pwm2",
                "/sys/class/hwmon/hwmon0/device/fan2_input",
                pwm_line_start=100,
                pwm_line_end=240,
                never_stop=True,
            )
        },
        temps={
            "mobo": FileTemp(
                "/sys/class/hwmon/hwmon0/device/temp1_input",
                min=None,
                max=None,
                panic=None,
                threshold=None,
            )
        },
        mappings={
            "1": FansTempsRelation(
                temps=["mobo"], fans=[FanSpeedModifier(fan="case", modifier=0.6)]
            )
        },
    )
