import json
import queue
import struct
import threading
from timeit import default_timer
from typing import TYPE_CHECKING, Any, Dict, NewType, Optional

from afancontrol.configparser import ConfigParserSection
from afancontrol.logger import logger

if TYPE_CHECKING:
    from afancontrol.pwmfan.base import PWMValue

try:
    from serial import serial_for_url
    from serial.threaded import LineReader, ReaderThread

    pyserial_available = True
except ImportError:
    LineReader = object
    ReaderThread = object

    pyserial_available = False

ArduinoName = NewType("ArduinoName", str)
ArduinoPin = NewType("ArduinoPin", int)

DEFAULT_BAUDRATE = 115200
DEFAULT_STATUS_TTL = 5


class ArduinoConnection:
    def __init__(
        self,
        name: ArduinoName,
        serial_url: str,
        *,
        baudrate: int = DEFAULT_BAUDRATE,
        status_ttl: int = DEFAULT_STATUS_TTL
    ) -> None:
        if not pyserial_available:
            raise RuntimeError(
                "`pyserial` is not installed. "
                "Run `pip install 'afancontrol[arduino]'`."
            )
        self.name = name
        self.url = serial_url
        self.baudrate = baudrate
        self.status_ttl = status_ttl
        self._reader_thread = _AutoRetriedReaderThread(
            lambda: _StatusProtocol(self), url=serial_url, baudrate=baudrate
        )
        self._context_manager_depth = 0
        self._status: Optional[Dict[str, Dict[str, int]]] = None
        self._status_clock: Optional[float] = None
        self._status_lock = threading.Lock()
        self._status_event = threading.Event()

    @classmethod
    def from_configparser(
        cls, section: ConfigParserSection[ArduinoName]
    ) -> "ArduinoConnection":
        return cls(
            name=section.name,
            serial_url=section["serial_url"],
            baudrate=section.getint("baudrate", fallback=DEFAULT_BAUDRATE),
            status_ttl=section.getint("status_ttl", fallback=DEFAULT_STATUS_TTL),
        )

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return (
                self.name == other.name
                and self.url == other.url
                and self.baudrate == other.baudrate
                and self.status_ttl == other.status_ttl
            )

        return NotImplemented

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return "%s(%r, %r, baudrate=%r, status_ttl=%r)" % (
            type(self).__name__,
            self.name,
            self.url,
            self.baudrate,
            self.status_ttl,
        )

    def __enter__(self):  # reentrant
        if self._context_manager_depth == 0:
            self._reader_thread.__enter__()
        self._context_manager_depth += 1
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self._context_manager_depth -= 1
        if self._context_manager_depth == 0:
            return self._reader_thread.__exit__(exc_type, exc_value, exc_tb)
        return None

    def _clock(self):
        return default_timer()

    def _incoming_message(self, message: Dict[str, Any]) -> None:
        # Called by the pyserial Protocol `_StatusProtocol`.
        if "error" in message:
            logger.warning("Received an error from Arduino %s: %r", self.url, message)
        else:
            self._update_status(message)

    def _update_status(self, status: Dict[str, Dict[str, int]]) -> None:
        with self._status_lock:
            self._status = status
            self._status_clock = self._clock()
        self._status_event.set()

    @property
    def is_connected(self) -> bool:
        try:
            with self._status_lock:
                self._ensure_status_is_valid()
        except Exception:
            return False
        else:
            return True

    def get_rpm(self, pin: ArduinoPin) -> int:
        if self._status is None:
            self.wait_for_status()
        with self._status_lock:
            self._ensure_status_is_valid()
            assert self._status is not None
            return int(self._status["fan_inputs"][str(pin)])

    def get_pwm(self, pin: ArduinoPin) -> int:
        if self._status is None:
            self.wait_for_status()
        with self._status_lock:
            self._ensure_status_is_valid()
            assert self._status is not None
            return int(self._status["fan_pwm"][str(pin)])

    def _ensure_status_is_valid(self):
        if self._status is None:
            raise RuntimeError("No status from the Arduino board at %s" % self.url)
        assert self._status_clock is not None
        status_age = self._clock() - self._status_clock
        if status_age > self.status_ttl:
            self._reader_thread.check_connection()
            raise RuntimeError(
                "The last received status from the Arduino board "
                "at %s was too long ago: %s seconds" % (self.url, status_age)
            )

    @property
    def status_age_seconds(self) -> float:
        with self._status_lock:
            if self._status_clock is None:
                return float("nan")
            return self._clock() - self._status_clock

    def set_pwm(self, pin: ArduinoPin, pwm: "PWMValue") -> None:
        command = SetPWMCommand(pwm_pin=pin, pwm=pwm).to_bytes()
        transport = self._reader_thread.transport
        try:
            transport.write(command)
            transport.flush()
        except Exception:
            self._reader_thread.check_connection()
            raise

    def wait_for_status(self) -> None:
        self._status_event.clear()
        if self._status_event.wait(self.status_ttl) is not True:
            raise RuntimeError(
                "Timed out waiting for the status from Arduino board at %s" % self.url
            )


class SetPWMCommand:
    command = b"\xf1"

    def __init__(self, *, pwm_pin: ArduinoPin, pwm: "PWMValue") -> None:
        self.pwm_pin = pwm_pin
        self.pwm = pwm

    def __repr__(self):
        return "%s(pwm_pin=%r, pwm=%r)" % (type(self).__name__, self.pwm_pin, self.pwm)

    def to_bytes(self):
        return struct.pack("sBB", self.command, self.pwm_pin, self.pwm)

    @classmethod
    def parse(cls, b: bytes) -> "SetPWMCommand":
        command, pwm_pin, pwm = struct.unpack("sBB", b)
        if command != cls.command:
            raise ValueError(
                "Invalid command marker. Expected %r, got %r" % (cls.command, command)
            )
        return cls(pwm_pin=ArduinoPin(pwm_pin), pwm=pwm)


class _StatusProtocol(LineReader):
    TERMINATOR = b"\n"

    def __init__(self, arduino_connection: ArduinoConnection) -> None:
        super().__init__()
        self._arduino_connection = arduino_connection

    def handle_line(self, line: str) -> None:
        try:
            message = json.loads(line)
            self._arduino_connection._incoming_message(message)
        except Exception:  # `handle_line` should not raise exceptions
            logger.error(
                "Unable to parse the status line from Arduino as json: %r",
                line,
                exc_info=True,
            )


class _AutoRetriedReaderThread:
    _QUEUE_STOP = object()
    _QUEUE_CHECK = object()

    def __init__(self, protocol_factory, **serial_for_url_kwargs) -> None:
        self.protocol_factory = protocol_factory
        self.serial_for_url_kwargs = serial_for_url_kwargs
        self._reader_thread: Optional[ReaderThread] = None
        self._transport: Optional[ReaderThread] = None
        self._watchdog_thread: Optional[threading.Thread] = None
        self._watchdog_queue: queue.Queue[Any] = queue.Queue()

    def __enter__(self):  # reusable
        # TODO ?? maybe clean the _watchdog_queue?
        self._reader_thread, self._transport = self._new_reader_thread()
        self._watchdog_thread = threading.Thread(target=self._thread_run, daemon=True)
        self._watchdog_thread.start()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        assert self._reader_thread is not None
        assert self._watchdog_thread is not None
        self._watchdog_queue.put(self._QUEUE_STOP)
        self._watchdog_thread.join()
        self._reader_thread.close()
        self._reader_thread = None
        self._transport = None

    @property
    def transport(self):
        return self._transport

    def check_connection(self):
        self._watchdog_queue.put(self._QUEUE_CHECK)

    def _new_reader_thread(self):
        ser = serial_for_url(**self.serial_for_url_kwargs)
        thread = _ReaderThreadWithFlush(ser, self.protocol_factory)
        thread.start()
        transport, _ = thread.connect()
        return thread, transport

    def _thread_run(self):
        while True:
            item = self._watchdog_queue.get()
            try:
                if self._reader_thread is None:
                    break
                if item is self._QUEUE_STOP:
                    break
                elif item is self._QUEUE_CHECK:
                    if self._reader_thread.alive:
                        continue
                    try:
                        self._reader_thread.close()
                    except Exception:
                        logger.error(
                            "Unable to cleanly close the Serial connection",
                            exc_info=True,
                        )
                    self._reader_thread, self._transport = self._new_reader_thread()
            except Exception:  # `_thread_run` should not raise
                logger.error(
                    "Error in the Arduino connection watchdog thread", exc_info=True
                )
            finally:
                self._watchdog_queue.task_done()


class _ReaderThreadWithFlush(ReaderThread):
    def flush(self):
        with self._lock:
            self.serial.flush()

    def close(self):
        try:
            super().close()
        except Exception:
            # `super().close()` also calls `self.stop()` which might raise
            # and prevent `self.serial.close()` from being called.
            with self._lock:
                self.serial.close()
            raise
