from contextlib import ExitStack
from typing import cast
from unittest.mock import MagicMock, patch, sentinel

import pytest

import afancontrol.manager
from afancontrol.config import (
    Actions,
    AlertCommands,
    FanName,
    FanSpeedModifier,
    FansTempsRelation,
    MappingName,
    TempName,
    TriggerConfig,
)
from afancontrol.manager import Manager
from afancontrol.metrics import Metrics
from afancontrol.pwmfannorm import PWMFanNorm, PWMValueNorm
from afancontrol.report import Report
from afancontrol.temp import FileTemp, TempCelsius, TempStatus
from afancontrol.trigger import Triggers


@pytest.fixture
def report():
    return MagicMock(spec=Report)


def test_manager(report):
    mocked_case_fan = MagicMock(spec=PWMFanNorm)()
    mocked_mobo_temp = MagicMock(spec=FileTemp)()
    mocked_metrics = MagicMock(spec=Metrics)()

    with ExitStack() as stack:
        stack.enter_context(
            patch.object(afancontrol.manager, "Triggers", spec=Triggers)
        )

        manager = Manager(
            arduino_connections={},
            fans={FanName("case"): mocked_case_fan},
            readonly_fans={},
            temps={TempName("mobo"): mocked_mobo_temp},
            mappings={
                MappingName("1"): FansTempsRelation(
                    temps=[TempName("mobo")],
                    fans=[FanSpeedModifier(fan=FanName("case"), modifier=0.6)],
                )
            },
            report=report,
            triggers_config=TriggerConfig(
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
            metrics=mocked_metrics,
        )

        stack.enter_context(manager)

        manager.tick()

        mocked_triggers = cast(MagicMock, manager.triggers)
        assert mocked_triggers.check.call_count == 1
        assert mocked_case_fan.__enter__.call_count == 1
        assert mocked_metrics.__enter__.call_count == 1
        assert mocked_metrics.tick.call_count == 1
    assert mocked_case_fan.__exit__.call_count == 1
    assert mocked_metrics.__exit__.call_count == 1


@pytest.mark.parametrize(
    "temps, mappings, expected_fan_speeds",
    [
        (
            {
                TempName("cpu"): TempStatus(
                    min=TempCelsius(30),
                    max=TempCelsius(50),
                    temp=TempCelsius((50 - 30) * 0.42 + 30),
                    panic=None,
                    threshold=None,
                    is_panic=False,
                    is_threshold=False,
                ),
                TempName("hdd"): None,  # a failing sensor
            },
            {
                MappingName("all"): FansTempsRelation(
                    temps=[TempName("cpu"), TempName("hdd")],
                    fans=[FanSpeedModifier(fan=FanName("rear"), modifier=1.0)],
                )
            },
            {FanName("rear"): PWMValueNorm(1.0)},
        ),
        (
            {
                TempName("cpu"): TempStatus(
                    min=TempCelsius(30),
                    max=TempCelsius(50),
                    temp=TempCelsius((50 - 30) * 0.42 + 30),
                    panic=None,
                    threshold=None,
                    is_panic=False,
                    is_threshold=False,
                )
            },
            {
                MappingName("all"): FansTempsRelation(
                    temps=[TempName("cpu")],
                    fans=[FanSpeedModifier(fan=FanName("rear"), modifier=1.0)],
                )
            },
            {FanName("rear"): PWMValueNorm(0.42)},
        ),
        (
            {
                TempName("cpu"): TempStatus(
                    min=TempCelsius(30),
                    max=TempCelsius(50),
                    temp=TempCelsius((50 - 30) * 0.42 + 30),
                    panic=None,
                    threshold=None,
                    is_panic=False,
                    is_threshold=False,
                )
            },
            {
                MappingName("all"): FansTempsRelation(
                    temps=[TempName("cpu")],
                    fans=[FanSpeedModifier(fan=FanName("rear"), modifier=0.6)],
                )
            },
            {FanName("rear"): PWMValueNorm(0.42 * 0.6)},
        ),
        (
            {
                TempName("cpu"): TempStatus(
                    min=TempCelsius(30),
                    max=TempCelsius(50),
                    temp=TempCelsius((50 - 30) * 0.42 + 30),
                    panic=None,
                    threshold=None,
                    is_panic=False,
                    is_threshold=False,
                ),
                TempName("mobo"): TempStatus(
                    min=TempCelsius(30),
                    max=TempCelsius(50),
                    temp=TempCelsius((50 - 30) * 0.52 + 30),
                    panic=None,
                    threshold=None,
                    is_panic=False,
                    is_threshold=False,
                ),
                TempName("hdd"): TempStatus(
                    min=TempCelsius(30),
                    max=TempCelsius(50),
                    temp=TempCelsius((50 - 30) * 0.12 + 30),
                    panic=None,
                    threshold=None,
                    is_panic=False,
                    is_threshold=False,
                ),
            },
            {
                MappingName("all"): FansTempsRelation(
                    temps=[TempName("cpu"), TempName("mobo"), TempName("hdd")],
                    fans=[FanSpeedModifier(fan=FanName("rear"), modifier=1.0)],
                )
            },
            {FanName("rear"): PWMValueNorm(0.52)},
        ),
        (
            {
                TempName("cpu"): TempStatus(
                    min=TempCelsius(30),
                    max=TempCelsius(50),
                    temp=TempCelsius((50 - 30) * 0.42 + 30),
                    panic=None,
                    threshold=None,
                    is_panic=False,
                    is_threshold=False,
                ),
                TempName("mobo"): TempStatus(
                    min=TempCelsius(30),
                    max=TempCelsius(50),
                    temp=TempCelsius((50 - 30) * 0.52 + 30),
                    panic=None,
                    threshold=None,
                    is_panic=False,
                    is_threshold=False,
                ),
                TempName("hdd"): TempStatus(
                    min=TempCelsius(30),
                    max=TempCelsius(50),
                    temp=TempCelsius((50 - 30) * 0.12 + 30),
                    panic=None,
                    threshold=None,
                    is_panic=False,
                    is_threshold=False,
                ),
            },
            {
                MappingName("1"): FansTempsRelation(
                    temps=[TempName("cpu"), TempName("hdd")],
                    fans=[FanSpeedModifier(fan=FanName("rear"), modifier=1.0)],
                ),
                MappingName("2"): FansTempsRelation(
                    temps=[TempName("mobo"), TempName("hdd")],
                    fans=[FanSpeedModifier(fan=FanName("rear"), modifier=0.6)],
                ),
            },
            {FanName("rear"): PWMValueNorm(0.42)},
        ),
    ],
)
def test_fan_speeds(report, temps, mappings, expected_fan_speeds):
    mocked_case_fan = MagicMock(spec=PWMFanNorm)()
    mocked_mobo_temp = MagicMock(spec=FileTemp)()
    mocked_metrics = MagicMock(spec=Metrics)()

    with ExitStack() as stack:
        stack.enter_context(
            patch.object(afancontrol.manager, "Triggers", spec=Triggers)
        )

        manager = Manager(
            arduino_connections={},
            fans={fan_name: mocked_case_fan for fan_name in expected_fan_speeds.keys()},
            readonly_fans={},
            temps={temp_name: mocked_mobo_temp for temp_name in temps.keys()},
            mappings=mappings,
            report=report,
            triggers_config=sentinel.some_triggers_config,
            metrics=mocked_metrics,
        )

        stack.enter_context(manager)

        assert expected_fan_speeds == pytest.approx(
            dict(manager._map_temps_to_fan_speeds(temps))
        )
