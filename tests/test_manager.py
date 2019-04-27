from contextlib import ExitStack
from unittest.mock import MagicMock, patch

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
from afancontrol.pwmfan import PWMFanNorm
from afancontrol.report import Report
from afancontrol.temp import FileTemp
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
            fans={FanName("case"): mocked_case_fan},
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

        mocked_triggers = manager.triggers  # type: MagicMock
        assert mocked_triggers.check.call_count == 1
        assert mocked_case_fan.__enter__.call_count == 1
        assert mocked_metrics.__enter__.call_count == 1
        assert mocked_metrics.tick.call_count == 1
    assert mocked_case_fan.__exit__.call_count == 1
    assert mocked_metrics.__exit__.call_count == 1
