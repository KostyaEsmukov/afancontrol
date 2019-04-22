from unittest.mock import call

from afancontrol import report
from afancontrol.report import Report


def test_report_success(sense_exec_shell_command):
    r = Report(r"printf '@%s' '%REASON%' '%MESSAGE%'")

    with sense_exec_shell_command(report) as (mock_exec_shell_command, get_stdout):
        r.report("reason here", "message\nthere")
        assert mock_exec_shell_command.call_args == call(
            "printf '@%s' 'reason here' 'message\nthere'"
        )
        assert ["@reason here@message\nthere"] == get_stdout()


def test_report_fail_does_not_raise():
    r = Report("false")
    r.report("reason here", "message\nthere")
