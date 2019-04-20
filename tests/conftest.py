import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from afancontrol.exec import exec_shell_command


@pytest.fixture
def temp_path():
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield Path(tmpdirname).resolve()


@pytest.fixture
def sense_exec_shell_command():
    exec_shell_command_stdout = []

    def sensed_exec_shell_command(*args, **kwargs):
        exec_shell_command_stdout.append(exec_shell_command(*args, **kwargs))
        return exec_shell_command_stdout[-1]

    def get_stdout():
        try:
            return exec_shell_command_stdout[:]
        finally:
            exec_shell_command_stdout.clear()

    @contextmanager
    def _sense_exec_shell_command(module):
        with patch.object(
            module, "exec_shell_command", wraps=sensed_exec_shell_command
        ) as mock_exec_shell_command:
            yield mock_exec_shell_command, get_stdout

    return _sense_exec_shell_command
