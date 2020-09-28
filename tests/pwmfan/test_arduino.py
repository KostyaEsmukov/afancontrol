import json
import socket
import threading
import traceback
from contextlib import ExitStack
from time import sleep
from typing import Dict

import pytest

from afancontrol.arduino import (
    ArduinoConnection,
    ArduinoName,
    ArduinoPin,
    SetPWMCommand,
    pyserial_available,
)
from afancontrol.pwmfan import (
    ArduinoFanPWMRead,
    ArduinoFanPWMWrite,
    ArduinoFanSpeed,
    PWMValue,
)

pytestmark = pytest.mark.skipif(
    not pyserial_available, reason="pyserial is not installed"
)


class DummyArduino:
    """Emulate an Arduino board, i.e. the other side of the pyserial connection.

    Slightly mimics the Arduino program `micro.ino`.
    """

    def __init__(self) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        listening_port = s.getsockname()[1]
        self.sock = s
        self.pyserial_url = "socket://127.0.0.1:%s" % listening_port
        self._lock = threading.Lock()
        self._loop_iteration_complete = threading.Event()
        self._first_loop_iteration_complete = threading.Event()
        self._disconnected = threading.Event()
        self._thread_error = threading.Event()
        self._is_connected = False
        self._inner_state_pwms = {"5": 255, "9": 255, "10": 255, "11": 255}
        self._inner_state_speeds = {"0": 0, "1": 0, "2": 0, "3": 0, "7": 0}

    def set_inner_state_pwms(self, pwms: Dict[str, int]) -> None:
        with self._lock:
            self._inner_state_pwms.update(pwms)
        if self.is_connected:
            self._loop_iteration_complete.clear()
            assert self._loop_iteration_complete.wait(5) is True

    def set_speeds(self, speeds: Dict[str, int]) -> None:
        with self._lock:
            self._inner_state_speeds.update(speeds)
        if self.is_connected:
            self._loop_iteration_complete.clear()
            assert self._loop_iteration_complete.wait(5) is True

    @property
    def inner_state_pwms(self):
        with self._lock:
            copy = self._inner_state_pwms.copy()
        return copy

    @property
    def is_connected(self):
        with self._lock:
            if not self._is_connected:
                return False
        assert self._first_loop_iteration_complete.wait(5) is True
        return True

    def wait_for_disconnected(self):
        assert self._disconnected.wait(5) is True

    def accept(self):
        client, _ = self.sock.accept()
        self.sock.close()  # Don't accept any more connections
        with self._lock:
            self._is_connected = True
        threading.Thread(target=self._thread_run, args=(client,), daemon=True).start()

    def _thread_run(self, sock):
        sock.settimeout(0.001)
        command_buffer = bytearray()
        try:
            while True:
                # The code in this loop mimics the `loop` function
                # in the `micro.ino` program.

                try:
                    command_buffer.extend(sock.recv(1024))
                except socket.timeout:
                    pass

                while len(command_buffer) >= 3:
                    command_raw = command_buffer[:3]
                    del command_buffer[:3]
                    command = SetPWMCommand.parse(command_raw)
                    with self._lock:
                        self._inner_state_pwms[str(command.pwm_pin)] = command.pwm

                sock.sendall(self._make_status())

                self._loop_iteration_complete.set()
                self._first_loop_iteration_complete.set()

                sleep(0.050)
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception:
            traceback.print_exc()
            self._thread_error.set()
        finally:
            with self._lock:
                self._is_connected = False
            sock.close()
            self._disconnected.set()

    def _make_status(self):
        with self._lock:
            status = {
                "fan_inputs": self._inner_state_speeds,
                "fan_pwm": self._inner_state_pwms,
            }
            return (json.dumps(status) + "\n").encode("ascii")

    def ensure_no_errors_in_thread(self):
        assert self._thread_error.is_set() is not True


@pytest.fixture
def dummy_arduino():
    return DummyArduino()


def test_smoke(dummy_arduino):
    conn = ArduinoConnection(ArduinoName("test"), dummy_arduino.pyserial_url)

    fan_speed = ArduinoFanSpeed(conn, tacho_pin=ArduinoPin(3))
    pwm_read = ArduinoFanPWMRead(conn, pwm_pin=ArduinoPin(9))
    pwm_write = ArduinoFanPWMWrite(conn, pwm_pin=ArduinoPin(9))

    dummy_arduino.set_inner_state_pwms({"9": 42})

    with ExitStack() as stack:
        assert not dummy_arduino.is_connected
        stack.enter_context(fan_speed)
        stack.enter_context(pwm_read)
        stack.enter_context(pwm_write)
        dummy_arduino.accept()
        assert dummy_arduino.is_connected

        dummy_arduino.set_speeds({"3": 1200})
        conn.wait_for_status()  # required only for synchronization in the tests
        assert fan_speed.get_speed() == 1200
        assert pwm_read.get() == 255
        assert dummy_arduino.inner_state_pwms["9"] == 255

        pwm_write.set(PWMValue(192))
        dummy_arduino.set_speeds({"3": 998})
        conn.wait_for_status()  # required only for synchronization in the tests
        assert fan_speed.get_speed() == 998
        assert pwm_read.get() == 192
        assert dummy_arduino.inner_state_pwms["9"] == 192

    dummy_arduino.wait_for_disconnected()
    assert dummy_arduino.inner_state_pwms["9"] == 255
    assert not dummy_arduino.is_connected
    dummy_arduino.ensure_no_errors_in_thread()
