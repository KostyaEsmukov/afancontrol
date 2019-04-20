from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

import afancontrol.manager.manager
from afancontrol.config import (
    Actions,
    AlertCommands,
    FanSpeedModifier,
    FansTempsRelation,
    TriggerConfig,
)
from afancontrol.manager.manager import Manager
from afancontrol.manager.report import Report
from afancontrol.manager.trigger import Triggers
from afancontrol.pwmfan import PWMFanNorm
from afancontrol.temp import FileTemp


@pytest.fixture
def report():
    return MagicMock(spec=Report)


def test_manager(report):
    mocked_case_fan = MagicMock(spec=PWMFanNorm)()
    mocked_mobo_temp = MagicMock(spec=FileTemp)()
    with ExitStack() as stack:
        stack.enter_context(
            patch.object(afancontrol.manager.manager, "Triggers", spec=Triggers)
        )

        manager = Manager(
            fans={"case": mocked_case_fan},
            temps={"mobo": mocked_mobo_temp},
            mappings={
                "1": FansTempsRelation(
                    temps=["mobo"], fans=[FanSpeedModifier(fan="case", modifier=0.6)]
                )
            },
            report=report,
            triggers_config=TriggerConfig(
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
            fans_speed_check_interval=1.0,
        )

        stack.enter_context(manager)

        manager.tick()

        mocked_triggers = manager.triggers
        assert mocked_triggers.check.call_count == 1
        assert mocked_case_fan.__enter__.call_count == 1
    assert mocked_case_fan.__exit__.call_count == 1
