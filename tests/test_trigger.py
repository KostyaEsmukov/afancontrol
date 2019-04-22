from unittest.mock import MagicMock, call

import pytest

from afancontrol import trigger
from afancontrol.config import Actions, AlertCommands, TempName, TriggerConfig
from afancontrol.report import Report
from afancontrol.temp import TempCelsius, TempStatus
from afancontrol.trigger import PanicTrigger, ThresholdTrigger, Triggers


@pytest.fixture
def report():
    return MagicMock(spec=Report)


def test_panic_on_empty_temp(report, sense_exec_shell_command):
    t = PanicTrigger(
        global_commands=AlertCommands(
            enter_cmd="printf '@%s' enter", leave_cmd="printf '@%s' leave"
        ),
        temp_commands={
            TempName("mobo"): AlertCommands(
                enter_cmd=None, leave_cmd="printf '@%s' mobo leave"
            )
        },
        report=report,
    )

    with sense_exec_shell_command(trigger) as (mock_exec_shell_command, get_stdout):
        with t:
            assert not t.is_alerting
            assert 0 == mock_exec_shell_command.call_count
            t.check({TempName("mobo"): None})
            assert t.is_alerting

            assert mock_exec_shell_command.call_args_list == [
                call("printf '@%s' enter")
            ]
            assert ["@enter"] == get_stdout()
            mock_exec_shell_command.reset_mock()

        assert not t.is_alerting
        assert mock_exec_shell_command.call_args_list == [
            call("printf '@%s' mobo leave"),
            call("printf '@%s' leave"),
        ]
        assert ["@mobo@leave", "@leave"] == get_stdout()


def test_threshold_on_empty_temp(report):
    t = ThresholdTrigger(
        global_commands=AlertCommands(enter_cmd=None, leave_cmd=None),
        temp_commands={TempName("mobo"): AlertCommands(enter_cmd=None, leave_cmd=None)},
        report=report,
    )
    with t:
        assert not t.is_alerting
        t.check({TempName("mobo"): None})
        assert not t.is_alerting
    assert not t.is_alerting


@pytest.mark.parametrize("cls", [ThresholdTrigger, PanicTrigger])
def test_good_temp(cls, report):
    t = cls(
        global_commands=AlertCommands(enter_cmd=None, leave_cmd=None),
        temp_commands=dict(mobo=AlertCommands(enter_cmd=None, leave_cmd=None)),
        report=report,
    )
    with t:
        assert not t.is_alerting
        t.check(
            dict(
                mobo=TempStatus(
                    temp=TempCelsius(34.0),
                    min=TempCelsius(40.0),
                    max=TempCelsius(50.0),
                    panic=TempCelsius(60.0),
                    threshold=None,
                    is_panic=False,
                    is_threshold=False,
                )
            )
        )
        assert not t.is_alerting


@pytest.mark.parametrize("cls", [ThresholdTrigger, PanicTrigger])
def test_bad_temp(cls, report, sense_exec_shell_command):
    t = cls(
        global_commands=AlertCommands(
            enter_cmd="printf '@%s' enter", leave_cmd="printf '@%s' leave"
        ),
        temp_commands=dict(
            mobo=AlertCommands(
                enter_cmd="printf '@%s' mobo enter", leave_cmd="printf '@%s' mobo leave"
            )
        ),
        report=report,
    )
    with sense_exec_shell_command(trigger) as (mock_exec_shell_command, get_stdout):
        with t:
            assert not t.is_alerting
            t.check(
                dict(
                    mobo=TempStatus(
                        temp=TempCelsius(70.0),
                        min=TempCelsius(40.0),
                        max=TempCelsius(50.0),
                        panic=TempCelsius(60.0),
                        threshold=TempCelsius(55.0),
                        is_panic=True,
                        is_threshold=True,
                    )
                )
            )
            assert t.is_alerting
            assert mock_exec_shell_command.call_args_list == [
                call("printf '@%s' mobo enter"),
                call("printf '@%s' enter"),
            ]
            assert ["@mobo@enter", "@enter"] == get_stdout()
            mock_exec_shell_command.reset_mock()

            t.check(
                dict(
                    mobo=TempStatus(
                        temp=TempCelsius(34.0),
                        min=TempCelsius(40.0),
                        max=TempCelsius(50.0),
                        panic=TempCelsius(60.0),
                        threshold=None,
                        is_panic=False,
                        is_threshold=False,
                    )
                )
            )
            assert not t.is_alerting
            assert mock_exec_shell_command.call_args_list == [
                call("printf '@%s' mobo leave"),
                call("printf '@%s' leave"),
            ]
            assert ["@mobo@leave", "@leave"] == get_stdout()
            mock_exec_shell_command.reset_mock()
        assert 0 == mock_exec_shell_command.call_count


def test_triggers_good_temp(report):
    t = Triggers(
        TriggerConfig(
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
        report=report,
    )
    with t:
        assert not t.is_alerting
        t.check(
            {
                TempName("mobo"): TempStatus(
                    temp=TempCelsius(34.0),
                    min=TempCelsius(40.0),
                    max=TempCelsius(50.0),
                    panic=TempCelsius(60.0),
                    threshold=None,
                    is_panic=False,
                    is_threshold=False,
                )
            }
        )
        assert not t.is_alerting
