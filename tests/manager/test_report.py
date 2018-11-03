from unittest.mock import call, patch

from afancontrol.manager import report
from afancontrol.manager.report import Report, exec_shell_command


def test_report_success():
    r = Report(r"printf '@%s' '%REASON%' '%MESSAGE%'")

    exec_shell_command_stdout = None

    def sensed_exec_shell_command(*args, **kwargs):
        nonlocal exec_shell_command_stdout
        exec_shell_command_stdout = exec_shell_command(*args, **kwargs)
        return exec_shell_command_stdout

    with patch.object(
        report, "exec_shell_command", wraps=sensed_exec_shell_command
    ) as mock_exec_shell_command:
        r.report("reason here", "message\nthere")
        assert mock_exec_shell_command.call_args == call(
            "printf '@%s' 'reason here' 'message\nthere'"
        )
        assert "@reason here@message\nthere" == exec_shell_command_stdout


def test_report_fail():
    r = Report("false")
    r.report("reason here", "message\nthere")
