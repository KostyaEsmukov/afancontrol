from unittest.mock import MagicMock, call

import pytest

from afancontrol.config import Actions, AlertCommands, TriggerConfig
from afancontrol.manager import trigger
from afancontrol.manager.report import Report
from afancontrol.manager.trigger import PanicTrigger, ThresholdTrigger, Triggers
from afancontrol.temp import TempStatus


@pytest.fixture
def report():
    return MagicMock(spec=Report)


def test_panic_on_empty_temp(report, sense_exec_shell_command):
    t = PanicTrigger(
        global_commands=AlertCommands(
            enter_cmd="printf '@%s' enter", leave_cmd="printf '@%s' leave"
        ),
        temp_commands=dict(
            mobo=AlertCommands(enter_cmd=None, leave_cmd="printf '@%s' mobo leave")
        ),
        report=report,
    )

    with sense_exec_shell_command(trigger) as (mock_exec_shell_command, get_stdout):
        with t:
            assert not t.is_alerting
            assert 0 == mock_exec_shell_command.call_count
            t.check(dict(mobo=None))
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
        temp_commands=dict(mobo=AlertCommands(enter_cmd=None, leave_cmd=None)),
        report=report,
    )
    with t:
        assert not t.is_alerting
        t.check(dict(mobo=None))
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
                    temp=34.0,
                    min=40.0,
                    max=50.0,
                    panic=60.0,
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
                        temp=70.0,
                        min=40.0,
                        max=50.0,
                        panic=60.0,
                        threshold=55.0,
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
                        temp=34.0,
                        min=40.0,
                        max=50.0,
                        panic=60.0,
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
            temp_commands=dict(
                mobo=Actions(
                    panic=AlertCommands(enter_cmd=None, leave_cmd=None),
                    threshold=AlertCommands(enter_cmd=None, leave_cmd=None),
                )
            ),
        ),
        report=report,
    )
    with t:
        assert not t.is_alerting
        t.check(
            dict(
                mobo=TempStatus(
                    temp=34.0,
                    min=40.0,
                    max=50.0,
                    panic=60.0,
                    threshold=None,
                    is_panic=False,
                    is_threshold=False,
                )
            )
        )
        assert not t.is_alerting
