import threading
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from afancontrol import app
from afancontrol.app import PidFile, Signals, main


def test_main_smoke(temp_path):
    pwm_path = temp_path / "pwm" / "pwm2"
    pwm_enable_path = temp_path / "pwm" / "pwm2_enable"
    pwm_faninput_path = temp_path / "pwm" / "fan2_input"
    pwm_path.parents[0].mkdir(parents=True)
    pwm_path.write_text("100")
    pwm_enable_path.write_text("0")
    pwm_faninput_path.write_text("999")

    config_path = temp_path / "afancontrol.cfg"
    config_path.write_text(
        """
[daemon]
hddtemp = true

[actions]

[temp:mobo]
type = file
path = /fake/sys/class/hwmon/hwmon0/device/temp1_input

[fan: case]
pwm = %(pwm_path)s
fan_input = %(pwm_faninput_path)s

[mapping:1]
fans = case*0.6,
temps = mobo
"""
        % dict(pwm_path=pwm_path, pwm_faninput_path=pwm_faninput_path)
    )

    with ExitStack() as stack:
        args = MagicMock()
        args.test = False
        args.daemon = False
        args.verbose = True
        args.config = str(config_path)
        args.pidfile = str(temp_path / "afancontrol.pid")
        args.logfile = str(temp_path / "afancontrol.log")

        stack.enter_context(patch.object(app, "parse_args", return_value=args))
        mocked_tick = stack.enter_context(patch.object(app.Manager, "tick"))
        stack.enter_context(patch.object(app, "signal"))
        stack.enter_context(
            patch.object(app.Signals, "wait_for_term_queued", return_value=True)
        )

        main()

        assert mocked_tick.call_count == 1


def test_pidfile_not_existing(temp_path):
    pidpath = temp_path / "test.pid"
    pidfile = PidFile(str(pidpath))

    with pidfile:
        pidfile.save_pid(42)
        assert "42" == pidpath.read_text()

    assert not pidpath.exists()


def test_pidfile_existing_raises(temp_path):
    pidpath = temp_path / "test.pid"
    pidfile = PidFile(str(pidpath))
    pidpath.write_text("42")

    with pytest.raises(RuntimeError):
        with pidfile:
            pytest.fail("Should not be reached")

    assert pidpath.exists()


def test_signals():
    s = Signals()

    assert False is s.wait_for_term_queued(0.001)

    threading.Timer(0.01, lambda: s.sigterm(None, None)).start()
    assert True is s.wait_for_term_queued(1e6)
