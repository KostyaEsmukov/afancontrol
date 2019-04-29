import subprocess

import pytest

from afancontrol.exec import exec_shell_command


def test_exec_shell_command_successful():
    assert "42\n" == exec_shell_command("echo 42")


def test_exec_shell_command_ignores_stderr():
    assert "42\n" == exec_shell_command("echo 111 >&2; echo 42")


def test_exec_shell_command_erroneous():
    with pytest.raises(subprocess.SubprocessError):
        exec_shell_command("echo 42 && false")


def test_exec_shell_command_raises_for_unicode():
    with pytest.raises(ValueError):
        exec_shell_command("echo привет")


def test_exec_shell_command_expands_glob(temp_path):
    (temp_path / "sda").write_text("")
    (temp_path / "sdb").write_text("")

    expected = "{0}/sda {0}/sdb\n".format(temp_path)
    assert expected == exec_shell_command('echo "%s/sd"?' % temp_path)
